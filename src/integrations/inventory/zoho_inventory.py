from __future__ import annotations

import asyncio
from typing import Any

import httpx

from src.core.config import settings
from src.integrations.inventory.base import InventoryProvider


class ZohoInventoryClient(InventoryProvider):
    """Zoho Inventory API client implementing InventoryProvider protocol."""

    def __init__(self, redis_client: Any) -> None:
        """Initialize the Zoho Inventory client.
        
        Args:
            redis_client: Redis connection dependency for caching the OAuth token.
        """
        self.redis = redis_client
        self.base_url = settings.zoho_inventory_api_url
        self.org_id = settings.zoho_inventory_org_id

        # We use a single httpx AsyncClient for the instance to pool connections
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(30.0),
        )

    async def _ensure_token(self) -> str:
        """Get the current access token, refreshing if necessary via Redis lock."""
        token_key = "zoho:access_token"
        lock_key = "zoho:access_token:lock"

        # 1. Try to get existing token
        token = await self.redis.get(token_key)
        if token:
            return token.decode("utf-8")

        # 2. Acquire lock (race condition protection)
        # Try to set lock with EX=10s, NX=True (only if not exists)
        acquired = await self.redis.set(lock_key, "1", ex=10, nx=True)

        if not acquired:
            # Wait for another worker to refresh the token
            for _ in range(20):  # Wait up to 10 seconds (20 * 0.5s)
                await asyncio.sleep(0.5)
                token = await self.redis.get(token_key)
                if token:
                    return token.decode("utf-8")

            raise RuntimeError("Timeout waiting for Zoho token refresh lock")

        try:
            # 3. We have the lock, check token again just in case
            token = await self.redis.get(token_key)
            if token:
                return token.decode("utf-8")

            # 4. Refresh token
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://accounts.zoho.eu/oauth/v2/token",
                    data={
                        "refresh_token": settings.zoho_inventory_refresh_token,
                        "client_id": settings.zoho_inventory_client_id,
                        "client_secret": settings.zoho_inventory_client_secret,
                        "grant_type": "refresh_token",
                    },
                    timeout=15.0,
                )
                response.raise_for_status()
                data = response.json()

                new_token = data["access_token"]
                expires_in = int(data.get("expires_in", 3600))

                # Cache token with TTL = expires_in - 60 seconds (buffer)
                ttl = max(10, expires_in - 60)
                await self.redis.set(token_key, new_token, ex=ttl)

                return new_token

        finally:
            # 5. Release lock
            await self.redis.delete(lock_key)

    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> httpx.Response:
        """Make an authenticated request to Zoho Inventory API with retries."""
        params = params or {}
        params["organization_id"] = self.org_id

        # Retry mechanism (3 attempts with backoff)
        max_retries = 3

        for attempt in range(1, max_retries + 1):
            token = await self._ensure_token()
            headers = {"Authorization": f"Zoho-oauthtoken {token}"}

            try:
                response = await self.client.request(
                    method=method,
                    url=path,
                    params=params,
                    json=json,
                    headers=headers,
                )

                # If Unauthorized, token might be invalid/expired, force refresh next time
                if response.status_code == 401:
                    await self.redis.delete("zoho:access_token")
                    if attempt < max_retries:
                        continue

                response.raise_for_status()
                return response

            except httpx.HTTPStatusError as e:
                # Zoho sometimes returns 429 Too Many Requests
                if e.response.status_code == 429 and attempt < max_retries:
                    await asyncio.sleep(2 ** attempt)  # 2s, 4s...
                    continue
                raise

            except (httpx.TimeoutException, httpx.NetworkError):
                if attempt < max_retries:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise

        raise RuntimeError("Unreachable")


    async def get_items(self, page: int = 1, per_page: int = 200) -> dict[str, Any]:
        """Fetch a page of active items from Zoho Inventory.
        
        Returns the raw dict containing 'items' and 'page_context'.
        """
        response = await self._request(
            "GET",
            "/items",
            params={
                "page": page,
                "per_page": per_page,
                "status": "active",
                "cf_end_product": "true",
            }
        )
        return dict(response.json())


    async def get_stock(self, sku: str) -> dict[str, Any] | None:
        """Get stock level for a specific SKU using search_text.
        
        Returns the item dictionary if found, None otherwise.
        """
        response = await self._request("GET", "/items", params={"search_text": sku})
        data = response.json()

        items = data.get("items", [])

        # Exact match check because search_text is a partial match
        for item in items:
            if item.get("sku") == sku:
                return dict(item)

        return None

    async def get_stock_bulk(self, skus: list[str]) -> list[dict[str, Any]]:
        """Get stock levels for multiple SKUs.
        
        Zoho API doesn't support bulk search by SKU efficiently,
        so we batch individual requests concurrently.
        """
        # Run concurrent requests to get stock for each sku
        tasks = [self.get_stock(sku) for sku in skus]
        results = await asyncio.gather(*tasks)

        # Filter out None results
        return [res for res in results if res is not None]

    async def create_sale_order(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create a sale order / quotation. (To be implemented fully later)."""
        response = await self._request("POST", "/salesorders", json=data)
        return dict(response.json())

    async def get_sale_order(self, order_id: str) -> dict[str, Any] | None:
        """Get sale order details including PDF URL. (To be implemented fully later)."""
        try:
            response = await self._request("GET", f"/salesorders/{order_id}")
            return dict(response.json())
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self.client.aclose()
