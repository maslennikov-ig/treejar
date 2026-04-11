from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping
from typing import Any

import httpx

from src.core.config import settings
from src.integrations.inventory.base import InventoryProvider

logger = logging.getLogger(__name__)


def _normalize_phone(value: str | None) -> str | None:
    digits = "".join(ch for ch in value or "" if ch.isdigit())
    if not digits:
        return None
    return f"+{digits}"


def _phone_digits(value: str | None) -> str:
    return "".join(ch for ch in value or "" if ch.isdigit())


def _phones_equivalent(left: str | None, right: str | None) -> bool:
    left_digits = _phone_digits(left)
    right_digits = _phone_digits(right)
    if not left_digits or not right_digits:
        return False
    if left_digits == right_digits:
        return True

    shorter, longer = sorted((left_digits, right_digits), key=len)
    return len(shorter) >= 7 and longer.endswith(shorter)


def _coerce_inventory_contact(raw_contact: Any) -> dict[str, Any] | None:
    if not isinstance(raw_contact, Mapping):
        return None

    contact = dict(raw_contact)
    contact_id = contact.get("contact_id")
    if contact_id is None:
        return None

    contact["contact_id"] = str(contact_id)

    if "contact_type" in contact and contact["contact_type"] is not None:
        contact["contact_type"] = str(contact["contact_type"])
    if "status" in contact and contact["status"] is not None:
        contact["status"] = str(contact["status"])

    contact_persons = contact.get("contact_persons")
    if isinstance(contact_persons, list):
        contact["contact_persons"] = [
            dict(person) for person in contact_persons if isinstance(person, Mapping)
        ]

    return contact


def _is_active_customer(contact: Mapping[str, Any]) -> bool:
    contact_type = str(contact.get("contact_type") or "").strip().lower()
    if contact_type and contact_type != "customer":
        return False

    status = str(contact.get("status") or "").strip().lower()
    return not (status and status != "active")


def _contact_phone_values(contact: Mapping[str, Any]) -> list[str]:
    values: list[str] = []

    for key in ("phone", "mobile"):
        value = contact.get(key)
        if isinstance(value, str) and value.strip():
            values.append(value)

    contact_persons = contact.get("contact_persons")
    if isinstance(contact_persons, list):
        for person in contact_persons:
            if not isinstance(person, Mapping):
                continue
            for key in ("phone", "mobile"):
                value = person.get(key)
                if isinstance(value, str) and value.strip():
                    values.append(value)

    return values


def _contact_email_values(contact: Mapping[str, Any]) -> list[str]:
    values: list[str] = []

    email = contact.get("email")
    if isinstance(email, str) and email.strip():
        values.append(email)

    contact_persons = contact.get("contact_persons")
    if isinstance(contact_persons, list):
        for person in contact_persons:
            if not isinstance(person, Mapping):
                continue
            value = person.get("email")
            if isinstance(value, str) and value.strip():
                values.append(value)

    return values


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
            return token if isinstance(token, str) else token.decode("utf-8")

        # 2. Acquire lock (race condition protection)
        # Try to set lock with EX=10s, NX=True (only if not exists)
        acquired = await self.redis.set(lock_key, "1", ex=10, nx=True)

        if not acquired:
            # Wait for another worker to refresh the token
            for _ in range(20):  # Wait up to 10 seconds (20 * 0.5s)
                await asyncio.sleep(0.5)
                token = await self.redis.get(token_key)
                if token:
                    return token if isinstance(token, str) else token.decode("utf-8")

            raise RuntimeError("Timeout waiting for Zoho token refresh lock")

        try:
            # 3. We have the lock, check token again just in case
            token = await self.redis.get(token_key)
            if token:
                return token if isinstance(token, str) else token.decode("utf-8")

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

                return str(new_token)

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
        params = dict(params) if params else {}
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
                    await asyncio.sleep(2**attempt)  # 2s, 4s...
                    continue
                raise

            except (httpx.TimeoutException, httpx.NetworkError):
                if attempt < max_retries:
                    await asyncio.sleep(2**attempt)
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
                # Treejar-specific custom field: filters only end products (not raw materials)
                "cf_end_product": "true",
            },
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
        so we batch individual requests concurrently with a semaphore
        to avoid hitting Zoho rate limits.
        """
        sem = asyncio.Semaphore(5)  # max 5 concurrent requests to Zoho

        async def _fetch(sku: str) -> dict[str, Any] | None:
            async with sem:
                return await self.get_stock(sku)

        results = await asyncio.gather(*[_fetch(sku) for sku in skus])
        return [res for res in results if res is not None]

    async def get_item(self, item_id: str) -> dict[str, Any] | None:
        """Get a specific item by Zoho Inventory item_id."""
        try:
            response = await self._request("GET", f"/items/{item_id}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

        data = response.json()
        item = data.get("item")
        if isinstance(item, dict):
            return dict(item)
        if isinstance(data, dict):
            return dict(data)
        return None

    async def search_contacts(self, **filters: Any) -> list[dict[str, Any]]:
        """Search contacts using Zoho Inventory list-contacts filters."""
        params = {
            key: value for key, value in filters.items() if value not in (None, "")
        }
        params.setdefault("per_page", 200)
        response = await self._request("GET", "/contacts", params=params)
        data = response.json()

        contacts = data.get("contacts", [])
        if not isinstance(contacts, list):
            return []

        return [
            contact
            for raw_contact in contacts
            if (contact := _coerce_inventory_contact(raw_contact)) is not None
        ]

    async def get_contact(self, contact_id: str) -> dict[str, Any] | None:
        """Get a specific contact by Zoho Inventory contact_id."""
        try:
            response = await self._request("GET", f"/contacts/{contact_id}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

        data = response.json()
        contact = _coerce_inventory_contact(data.get("contact"))
        if contact is not None:
            return contact
        if isinstance(data, Mapping):
            return dict(data)
        return None

    async def _first_accessible_customer(
        self, contacts: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        for candidate in contacts:
            if not _is_active_customer(candidate):
                continue

            contact_id = str(candidate.get("contact_id") or "").strip()
            if not contact_id:
                continue

            contact = await self.get_contact(contact_id)
            if contact is None or not _is_active_customer(contact):
                continue

            return contact

        return None

    async def find_customer_by_phone(self, phone: str) -> dict[str, Any] | None:
        """Find an accessible active customer using normalized phone matching."""
        normalized_phone = _normalize_phone(phone)
        digits = _phone_digits(phone)
        if not normalized_phone or not digits:
            return None

        query_values: list[tuple[str, str]] = [("phone", normalized_phone)]
        if digits != normalized_phone:
            query_values.append(("phone", digits))
        if len(digits) > 7:
            query_values.append(("phone_contains", digits[-10:]))

        seen_queries: set[tuple[str, str]] = set()
        for field, value in query_values:
            query = (field, value)
            if query in seen_queries:
                continue
            seen_queries.add(query)

            contacts = await self.search_contacts(
                filter_by="Status.Active", **{field: value}
            )
            matched_contacts = [
                contact
                for contact in contacts
                if any(
                    _phones_equivalent(candidate_phone, normalized_phone)
                    for candidate_phone in _contact_phone_values(contact)
                )
            ]
            contact = await self._first_accessible_customer(matched_contacts)
            if contact is not None:
                return contact

        return None

    async def find_customer_by_email(self, email: str) -> dict[str, Any] | None:
        """Find an accessible active customer by email address."""
        normalized_email = email.strip().casefold()
        if not normalized_email:
            return None

        contacts = await self.search_contacts(
            filter_by="Status.Active", email=email.strip()
        )
        exact_matches = [
            contact
            for contact in contacts
            if any(
                candidate_email.strip().casefold() == normalized_email
                for candidate_email in _contact_email_values(contact)
            )
        ]
        return await self._first_accessible_customer(exact_matches)

    async def create_contact(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create a contact/customer in Zoho Inventory."""
        response = await self._request("POST", "/contacts", json=data)
        payload = response.json()

        contact = _coerce_inventory_contact(payload.get("contact"))
        if contact is not None:
            return contact
        if isinstance(payload, Mapping):
            return dict(payload)
        return {}

    async def create_sale_order(
        self, customer_id: str, items: list[dict[str, Any]], status: str = "draft"
    ) -> dict[str, Any]:
        """Create a sale order / quotation in Zoho Inventory."""
        data = {
            "customer_id": customer_id,
            "line_items": items,
            "status": status,
        }
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

    async def get_sale_order_status(self, order_id: str) -> dict[str, Any] | None:
        """Get sale order status summary.

        Args:
            order_id: Zoho Inventory Sale Order ID.

        Returns:
            Normalized dict with status fields, or None if not found.
        """
        raw = await self.get_sale_order(order_id)
        if not raw:
            return None

        so = raw.get("salesorder", raw)
        return {
            "salesorder_id": so.get("salesorder_id", ""),
            "salesorder_number": so.get("salesorder_number", ""),
            "status": so.get("status", ""),
            "shipment_date": so.get("shipment_date", ""),
            "delivery_method": so.get("delivery_method", ""),
            "total": so.get("total", 0.0),
            "customer_name": so.get("customer_name", ""),
        }

    async def get_item_image(
        self,
        item_id: str,
    ) -> tuple[bytes, str] | None:
        """Download a product image from Zoho Inventory.

        Zoho stores images behind OAuth-protected URLs. This method uses
        the authenticated client to download and return raw image bytes.

        Args:
            item_id: The Zoho Inventory item_id (NOT sku).

        Returns:
            Tuple of (image_bytes, content_type) or None if no image.
        """
        try:
            response = await self._request("GET", f"/items/{item_id}/image")
            ct = response.headers.get("content-type", "image/png")
            if response.status_code == 200 and len(response.content) > 0:
                return response.content, ct
        except httpx.HTTPStatusError:
            pass
        return None

    async def __aenter__(self) -> ZohoInventoryClient:
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
