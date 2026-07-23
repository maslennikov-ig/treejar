from __future__ import annotations

import asyncio
import uuid
from collections.abc import Mapping
from typing import Any

import httpx

from src.core.config import settings
from src.integrations.crm.base import CRMProvider
from src.integrations.zoho_oauth import (
    ZOHO_OAUTH_LOCK_POLL_ATTEMPTS,
    ZOHO_OAUTH_LOCK_POLL_INTERVAL_SECONDS,
    ZOHO_OAUTH_REFRESH_LOCK_TTL_SECONDS,
    ZOHO_OAUTH_REFRESH_TIMEOUT_SECONDS,
    ZohoOAuthError,
    parse_zoho_oauth_response,
    release_zoho_oauth_lock,
    zoho_oauth_transport_error,
)


def _attribution_path_value(
    attribution: Mapping[str, Any],
    source_path: str,
) -> str | None:
    value: Any = attribution
    for part in source_path.split("."):
        if not isinstance(value, Mapping):
            return None
        value = value.get(part)

    if value is None:
        return None
    text = str(value).strip()
    return text or None


def apply_zoho_attribution_mapping(
    payload: Mapping[str, Any],
    attribution: Mapping[str, Any] | None,
    field_mapping: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Apply only explicitly configured source/UTM fields to a Zoho payload.

    Without a client-confirmed mapping policy this function intentionally returns
    the original payload unchanged, avoiding guessed Zoho custom field names.
    """
    mapped_payload = dict(payload)
    if not attribution or not field_mapping:
        return mapped_payload

    for source_path, zoho_field in field_mapping.items():
        if not zoho_field:
            continue
        value = _attribution_path_value(attribution, source_path)
        if value:
            mapped_payload[zoho_field] = value

    return mapped_payload


class ZohoCRMClient(CRMProvider):
    """Zoho CRM API client implementing CRMProvider protocol."""

    def __init__(self, redis_client: Any) -> None:
        """Initialize the Zoho CRM client.

        Args:
            redis_client: Redis connection dependency for caching the OAuth token.
        """
        self.redis = redis_client
        self.base_url = settings.zoho_crm_api_url

        # We use a single httpx AsyncClient for the instance to pool connections
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(30.0),
        )

    async def _ensure_token(self) -> str:
        """Get the current access token, refreshing if necessary via Redis lock."""
        token_key = "zoho_crm:access_token"
        lock_key = "zoho_crm:access_token:lock"
        lock_owner = uuid.uuid4().hex

        # 1. Try to get existing token
        token = await self.redis.get(token_key)
        if token:
            return token if isinstance(token, str) else token.decode("utf-8")

        # 2. Acquire lock (race condition protection)
        acquired = await self.redis.set(
            lock_key,
            lock_owner,
            ex=ZOHO_OAUTH_REFRESH_LOCK_TTL_SECONDS,
            nx=True,
        )

        if not acquired:
            # Wait for another worker to refresh the token
            for _ in range(ZOHO_OAUTH_LOCK_POLL_ATTEMPTS):
                await asyncio.sleep(ZOHO_OAUTH_LOCK_POLL_INTERVAL_SECONDS)
                token = await self.redis.get(token_key)
                if token:
                    return token if isinstance(token, str) else token.decode("utf-8")

            raise ZohoOAuthError("lock_timeout", retryable=True)

        try:
            # 3. We have the lock, check token again just in case
            token = await self.redis.get(token_key)
            if token:
                return token if isinstance(token, str) else token.decode("utf-8")

            # 4. Refresh token
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.post(
                        f"{settings.zoho_crm_accounts_url}/oauth/v2/token",
                        data={
                            "refresh_token": settings.zoho_crm_refresh_token,
                            "client_id": settings.zoho_crm_client_id,
                            "client_secret": settings.zoho_crm_client_secret,
                            "grant_type": "refresh_token",
                        },
                        timeout=ZOHO_OAUTH_REFRESH_TIMEOUT_SECONDS,
                    )
                except httpx.RequestError as exc:
                    raise zoho_oauth_transport_error() from exc

                token_response = parse_zoho_oauth_response(response)
                await self.redis.set(
                    token_key,
                    token_response.access_token,
                    ex=token_response.cache_ttl_seconds,
                )
                return token_response.access_token

        finally:
            # 5. Release lock
            await release_zoho_oauth_lock(
                self.redis,
                lock_key=lock_key,
                owner_token=lock_owner,
            )

    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> httpx.Response:
        """Make an authenticated request to Zoho CRM API with retries."""
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
                    await self.redis.delete("zoho_crm:access_token")
                    if attempt < max_retries:
                        continue

                # For Zoho CRM, a 204 No Content often means "no results found" in search
                if response.status_code == 204:
                    return response

                response.raise_for_status()
                return response

            except httpx.HTTPStatusError as e:
                # Zoho sometimes returns 429 Too Many Requests
                if e.response.status_code == 429 and attempt < max_retries:
                    await asyncio.sleep(2**attempt)  # 2s, 4s...
                    continue
                raise

            except (httpx.TimeoutException, httpx.NetworkError):
                if attempt < max_retries:
                    await asyncio.sleep(2**attempt)
                    continue
                raise

        raise RuntimeError("Unreachable")

    async def find_contact_by_phone(self, phone: str) -> dict[str, Any] | None:
        """Find a contact by phone number."""
        # Zoho CRM v7 search endpoint
        response = await self._request(
            "GET", "/Contacts/search", params={"phone": phone}
        )

        if response.status_code == 204:
            return None

        data = response.json()
        if "data" in data and len(data["data"]) > 0:
            return dict(data["data"][0])

        return None

    async def create_contact(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create a new contact."""
        # Zoho expects data in the 'data' array payload
        payload = {"data": [data]}
        response = await self._request("POST", "/Contacts", json=payload)

        resp_data = response.json()
        if "data" in resp_data and len(resp_data["data"]) > 0:
            # Returns the created record info, typically id and status
            return dict(resp_data["data"][0])
        return dict(resp_data)

    async def create_deal(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create a new deal/opportunity."""
        payload = {"data": [data]}
        response = await self._request("POST", "/Deals", json=payload)

        resp_data = response.json()
        if "data" in resp_data and len(resp_data["data"]) > 0:
            return dict(resp_data["data"][0])
        return dict(resp_data)

    async def update_deal(self, deal_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """Update an existing deal."""
        payload = {"data": [data]}
        response = await self._request("PUT", f"/Deals/{deal_id}", json=payload)

        resp_data = response.json()
        if "data" in resp_data and len(resp_data["data"]) > 0:
            return dict(resp_data["data"][0])
        return dict(resp_data)

    async def get_deal_status(self, deal_id: str) -> dict[str, Any] | None:
        """Get deal details including current stage.

        Args:
            deal_id: Zoho CRM Deal ID.

        Returns:
            Deal data dict with Stage field, or None if not found.
        """
        response = await self._request("GET", f"/Deals/{deal_id}")

        if response.status_code == 204:
            return None

        data = response.json()
        if "data" in data and len(data["data"]) > 0:
            return dict(data["data"][0])

        return None

    async def __aenter__(self) -> ZohoCRMClient:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        await self.close()

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self.client.aclose()
