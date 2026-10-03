from __future__ import annotations

import asyncio
import contextlib
import email.utils
import json
import logging
import math
import time
import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from datetime import UTC, datetime
from typing import Any, NotRequired, TypedDict

import httpx
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, ValidationError

from src.core.config import settings
from src.integrations.inventory.base import InventoryProvider
from src.integrations.inventory.stock_state import (
    COOLDOWN_SCRIPT,
    StockMetrics,
    StockState,
    StockStore,
)
from src.integrations.zoho_oauth import (
    ZOHO_OAUTH_LOCK_POLL_ATTEMPTS,
    ZOHO_OAUTH_LOCK_POLL_INTERVAL_SECONDS,
    ZOHO_OAUTH_REFRESH_LOCK_TTL_SECONDS,
    ZOHO_OAUTH_REFRESH_TIMEOUT_SECONDS,
    ZohoOAuthError,
    parse_zoho_oauth_response,
    release_zoho_oauth_lock,
    report_rejected_zoho_credentials,
    zoho_oauth_transport_error,
)
from src.llm.inventory_read import InventoryReadUnavailable

logger = logging.getLogger(__name__)

# tj-uz6j.9. Zoho enforces its request quota per organisation, so a 429 can be
# caused by traffic this worker does not own. After one, every Treejar process
# stops calling Zoho Inventory for a short cooldown instead of hammering it.
ZOHO_RATE_LIMIT_COOLDOWN_KEY = "zoho:inventory:rate_limited_until"
_RATE_LIMIT_DEFAULT_COOLDOWN_SECONDS = 30.0
# Zoho's org block can last 30 minutes. Do not retry every five minutes while
# Retry-After still forbids requests; bound abnormal values to one day.
_RATE_LIMIT_MAX_COOLDOWN_SECONDS = 86400.0
# Longest single wait a request will sit through before retrying a read; a
# longer Retry-After ends the request at once and leaves the cooldown in place.
_RATE_LIMIT_MAX_INLINE_WAIT_SECONDS = 8.0
_RATE_LIMIT_INLINE_WAIT_BUDGET_SECONDS = 10.0
# Identical reads inside one client lifetime (one customer turn) reuse the
# first answer; any write clears them.
_READ_CACHE_TTL_SECONDS = 60.0
_READ_CACHE_MAX_ENTRIES = 128
_process_rate_limited_until = 0.0

# tj-4qtv. Customer-facing stock always comes from Zoho Inventory, but asking
# Zoho once per SKU on every product search ran the shared organisation quota
# into 429s (live 2026-09-24). Every process now reads one shared snapshot of
# the active item list from Redis and only asks Zoho live for SKUs the
# snapshot cannot answer with a number.
ZOHO_STOCK_SNAPSHOT_KEY = "zoho:inventory:stock_snapshot:v1"
ZOHO_STOCK_SNAPSHOT_LOCK_KEY = "zoho:inventory:stock_snapshot:lock"
# The worker job rebuilds the snapshot this often (tj-3vz5).
STOCK_SNAPSHOT_FRESH_SECONDS = 300.0
# Served without a refresh up to this age, so a customer turn never waits for
# one while the job runs; past it the snapshot has expired from Redis.
STOCK_SNAPSHOT_STALE_SECONDS = 3600.0
# Covers a full refresh including the bounded inline 429 waits of each page.
STOCK_SNAPSHOT_LOCK_TTL_SECONDS = 120
STOCK_SNAPSHOT_PAGE_SIZE = 200
# 50 x 200 items; the organisation had about 2,100 active items in 2026.
STOCK_SNAPSHOT_MAX_PAGES = 50
_STOCK_SNAPSHOT_FIELDS = (
    "item_id",
    "sku",
    "name",
    "description",
    "status",
    "stock_on_hand",
    "available_stock",
    "actual_available_stock",
    "rate",
    "unit",
    "last_modified_time",
)
# Zoho holds duplicate items whose SKUs differ only in case or in Cyrillic
# letters that look like Latin ones ("CH 240 V black" / "CH 240 V Black").
_SKU_HOMOGLYPHS = str.maketrans(
    "\u0410\u0412\u0421\u0415\u041d\u0406\u041a\u041c\u041e\u0420\u0422\u0425\u0423"
    "\u0430\u0435\u043e\u0440\u0441\u0443\u0445\u0456",
    "ABCEHIKMOPTXYaeopcyxi",
)


class ZohoRateLimitError(httpx.HTTPStatusError):
    """Zoho Inventory refused a request with 429, or a cooldown is active.

    A subclass of HTTPStatusError with status 429, so existing handlers keep
    working. A 429 means Zoho did not process the request.
    """

    def __init__(
        self,
        message: str,
        *,
        request: httpx.Request,
        response: httpx.Response,
        retry_after_seconds: float | None,
        local_cooldown: bool = False,
    ) -> None:
        super().__init__(message, request=request, response=response)
        self.retry_after_seconds = retry_after_seconds
        self.local_cooldown = local_cooldown


def parse_retry_after(value: str | None, *, now: float | None = None) -> float | None:
    """Seconds to wait from a Retry-After header (delay-seconds or HTTP-date)."""
    raw = (value or "").strip()
    if not raw:
        return None
    if raw.isascii() and raw.isdigit() and len(raw) <= 8:
        return float(raw)
    try:
        parsed = email.utils.parsedate_to_datetime(raw)
    except (TypeError, ValueError, IndexError):
        return None
    if parsed is None or parsed.tzinfo is None:
        return None
    return max(parsed.timestamp() - (time.time() if now is None else now), 0.0)


def reset_rate_limit_cooldown() -> None:
    """Forget the in-process cooldown (tests and operator tooling)."""
    global _process_rate_limited_until
    _process_rate_limited_until = 0.0


def _sku_match_key(sku: str) -> str:
    return " ".join(sku.translate(_SKU_HOMOGLYPHS).casefold().split())


def has_numeric_stock(item: Mapping[str, Any]) -> bool:
    """Whether Zoho reported an actual stock_on_hand number for the item."""
    value = item.get("stock_on_hand")
    if value is None or isinstance(value, bool):
        return False
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def select_stock_item(
    sku: str, items: Iterable[Mapping[str, Any]]
) -> dict[str, Any] | None:
    """Pick the Zoho item for a SKU among candidates.

    An exact SKU wins, then a match that differs only in case or look-alike
    Cyrillic letters; within each, an item with a numeric stock_on_hand is
    preferred over one without.
    """
    candidates = [item for item in items if isinstance(item, Mapping)]
    exact = [item for item in candidates if item.get("sku") == sku]
    key = _sku_match_key(sku)
    loose = [
        item
        for item in candidates
        if isinstance(item.get("sku"), str) and _sku_match_key(item["sku"]) == key
    ]
    for group in (
        [item for item in exact if has_numeric_stock(item)],
        [item for item in loose if has_numeric_stock(item)],
        exact,
        loose,
    ):
        if group:
            return dict(group[0])
    return None


def _stock_identity_group(
    sku: str, candidates: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    exact = [row for row in candidates if row["sku"] == sku]
    for group in (
        [row for row in exact if has_numeric_stock(row)],
        [row for row in candidates if has_numeric_stock(row)],
        exact,
        candidates,
    ):
        if group:
            return group
    return []


def _stock_snapshot_record(raw_item: Any) -> dict[str, Any] | None:
    if not isinstance(raw_item, Mapping):
        return None
    sku = raw_item.get("sku")
    if not isinstance(sku, str) or not sku.strip():
        return None
    return {name: raw_item[name] for name in _STOCK_SNAPSHOT_FIELDS if name in raw_item}


@dataclass
class StockSnapshot:
    """Minimal Zoho item fields keyed by exact SKU, built at ``as_of``."""

    as_of: float
    items: dict[str, dict[str, Any]]
    _by_key: dict[str, list[dict[str, Any]]] = dataclass_field(
        default_factory=dict, init=False, repr=False
    )

    _by_item_id: dict[str, dict[str, Any]] = dataclass_field(
        default_factory=dict, init=False, repr=False
    )

    def __post_init__(self) -> None:
        for item in self.items.values():
            key = _sku_match_key(str(item.get("sku", "")))
            self._by_key.setdefault(key, []).append(item)
            item_id = str(item.get("item_id") or "").strip()
            if item_id:
                self._by_item_id[item_id] = item

    def age_seconds(self, now: float | None = None) -> float:
        return (time.time() if now is None else now) - self.as_of

    def lookup(self, sku: str) -> dict[str, Any] | None:
        """The item for a SKU, stamped with the snapshot time, or None."""
        exact = self.items.get(sku)
        candidates = [exact] if exact is not None else []
        candidates.extend(self._by_key.get(_sku_match_key(sku), ()))
        item = select_stock_item(sku, candidates)
        if item is None:
            return None
        item.setdefault(
            "stock_as_of", datetime.fromtimestamp(self.as_of, UTC).isoformat()
        )
        return item

    def lookup_item_id(self, item_id: str) -> dict[str, Any] | None:
        """The item with a Zoho item_id, stamped with the snapshot time, or None."""
        item = self._by_item_id.get(item_id.strip())
        if item is None:
            return None
        item.setdefault(
            "stock_as_of", datetime.fromtimestamp(self.as_of, UTC).isoformat()
        )
        return item

    def to_json(self) -> str:
        return json.dumps({"as_of": self.as_of, "items": self.items})

    @classmethod
    def from_raw(cls, raw: Any) -> StockSnapshot | None:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="ignore")
        if not isinstance(raw, str):
            return None
        try:
            data = json.loads(raw)
        except ValueError:
            return None
        if not isinstance(data, dict):
            return None
        as_of = data.get("as_of")
        items = data.get("items")
        if (
            not isinstance(as_of, (int, float))
            or not math.isfinite(as_of)
            or isinstance(as_of, bool)
            or not isinstance(items, dict)
        ):
            return None
        return cls(
            as_of=float(as_of),
            items={
                str(sku): dict(item)
                for sku, item in items.items()
                if isinstance(item, dict)
            },
        )


def contact_lists_only_other_phones(
    contact: Mapping[str, Any], phone: str | None
) -> bool:
    """Whether the contact lists phones and none of them is the given phone."""
    phones = _contact_phone_values(contact)
    return bool(phones) and not any(
        _phones_equivalent(candidate, phone) for candidate in phones
    )


class ZohoContactAddressPayload(TypedDict):
    address: str


class ZohoContactPersonPayload(TypedDict):
    first_name: str
    phone: str
    mobile: str
    is_primary_contact: bool
    last_name: NotRequired[str]
    email: NotRequired[str]


class ZohoInventoryContactPayload(TypedDict):
    contact_name: str
    contact_type: str
    contact_persons: list[ZohoContactPersonPayload]
    company_name: NotRequired[str]
    billing_address: NotRequired[ZohoContactAddressPayload]
    shipping_address: NotRequired[ZohoContactAddressPayload]


class ZohoSaleOrderLineItemPayload(TypedDict):
    item_id: str
    quantity: int
    rate: float
    description: str


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


def _normalize_contact_name(value: str | None) -> str:
    return " ".join((value or "").split()).casefold()


def _contact_name_values(contact: Mapping[str, Any]) -> list[str]:
    values: list[str] = []

    for key in ("contact_name", "company_name", "first_name", "last_name"):
        value = contact.get(key)
        if isinstance(value, str) and value.strip():
            values.append(value)

    contact_persons = contact.get("contact_persons")
    if isinstance(contact_persons, list):
        for person in contact_persons:
            if not isinstance(person, Mapping):
                continue

            for key in ("first_name", "last_name"):
                value = person.get(key)
                if isinstance(value, str) and value.strip():
                    values.append(value)

            first = str(person.get("first_name") or "").strip()
            last = str(person.get("last_name") or "").strip()
            full_name = " ".join(part for part in (first, last) if part)
            if full_name:
                values.append(full_name)

    return values


class _ZohoSaleOrder(BaseModel):
    model_config = ConfigDict(extra="allow")

    salesorder_id: str = Field(
        default="",
        validation_alias=AliasChoices("salesorder_id", "sales_order_id"),
    )
    salesorder_number: str = Field(
        default="",
        validation_alias=AliasChoices("salesorder_number", "sales_order_number"),
    )
    status: str = ""
    shipment_date: str = ""
    delivery_method: str = ""
    total: float = 0.0
    customer_name: str = ""


class _ZohoSaleOrderEnvelope(BaseModel):
    model_config = ConfigDict(extra="allow")

    saleorder: _ZohoSaleOrder | None = Field(
        default=None,
        validation_alias=AliasChoices("saleorder", "salesorder", "sales_order"),
    )


def _dump_model(model: BaseModel) -> dict[str, Any]:
    data = model.model_dump()
    if model.model_extra:
        data.update(model.model_extra)
    return data


def extract_sale_order_data(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {}

    try:
        envelope = _ZohoSaleOrderEnvelope.model_validate(payload)
    except ValidationError:
        envelope = None

    if envelope and envelope.saleorder is not None:
        return _dump_model(envelope.saleorder)

    if any(
        key in payload
        for key in (
            "salesorder_id",
            "sales_order_id",
            "salesorder_number",
            "sales_order_number",
            "status",
        )
    ):
        try:
            return _dump_model(_ZohoSaleOrder.model_validate(payload))
        except ValidationError:
            return {}

    return {}


def normalize_sale_order_response(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {}

    normalized = dict(payload)
    saleorder = extract_sale_order_data(payload)
    if saleorder:
        normalized["saleorder"] = saleorder
    return normalized


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
        self.stock_store = StockStore(redis_client)
        self.metrics = StockMetrics(redis_client)

        # We use a single httpx AsyncClient for the instance to pool connections
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(30.0),
        )
        self._read_cache: dict[
            tuple[str, tuple[tuple[str, str], ...]], tuple[float, httpx.Response]
        ] = {}

    async def _ensure_token(self) -> str:
        """Get the current access token, refreshing if necessary via Redis lock."""
        token_key = "zoho:access_token"
        lock_key = "zoho:access_token:lock"
        lock_owner = uuid.uuid4().hex

        # 1. Try to get existing token
        token = await self.redis.get(token_key)
        if token:
            return token if isinstance(token, str) else token.decode("utf-8")

        # 2. Acquire lock (race condition protection)
        # Keep the lock alive longer than the refresh request timeout.
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
                        "https://accounts.zoho.eu/oauth/v2/token",
                        data={
                            "refresh_token": settings.zoho_inventory_refresh_token,
                            "client_id": settings.zoho_inventory_client_id,
                            "client_secret": settings.zoho_inventory_client_secret,
                            "grant_type": "refresh_token",
                        },
                        timeout=ZOHO_OAUTH_REFRESH_TIMEOUT_SECONDS,
                    )
                except httpx.RequestError as exc:
                    raise zoho_oauth_transport_error() from exc

                try:
                    token_response = parse_zoho_oauth_response(response)
                except ZohoOAuthError as exc:
                    if exc.kind == "invalid_credentials":
                        await report_rejected_zoho_credentials(
                            self.redis, service="inventory"
                        )
                    raise
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

    async def _cooldown_remaining(self) -> float:
        """Seconds left in a process- or Redis-wide Zoho rate-limit cooldown."""
        now = time.time()
        remaining = _process_rate_limited_until - now
        try:
            raw = await self.redis.get(ZOHO_RATE_LIMIT_COOLDOWN_KEY)
        except Exception:
            raw = None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="ignore")
        if isinstance(raw, str):
            with contextlib.suppress(ValueError):
                remaining = max(remaining, float(raw) - now)
        return max(remaining, 0.0)

    async def _start_cooldown(self, seconds: float) -> float:
        global _process_rate_limited_until
        seconds = min(max(seconds, 1.0), _RATE_LIMIT_MAX_COOLDOWN_SECONDS)
        deadline = time.time() + seconds
        _process_rate_limited_until = max(_process_rate_limited_until, deadline)
        try:
            stored = await self.redis.eval(
                COOLDOWN_SCRIPT, 1, ZOHO_RATE_LIMIT_COOLDOWN_KEY, deadline, time.time()
            )
            _process_rate_limited_until = max(
                _process_rate_limited_until, float(stored)
            )
        except Exception:
            logger.warning("Could not share the Zoho rate-limit cooldown via Redis")
        return seconds

    def _cooldown_error(
        self, method: str, path: str, remaining: float
    ) -> ZohoRateLimitError:
        request = httpx.Request(method, f"{self.base_url}{path}")
        retry_after = str(max(math.ceil(remaining), 1))
        response = httpx.Response(
            429, headers={"Retry-After": retry_after}, request=request
        )
        return ZohoRateLimitError(
            "Zoho Inventory rate-limit cooldown is active",
            request=request,
            response=response,
            retry_after_seconds=float(retry_after),
            local_cooldown=True,
        )

    def _read_cache_key(
        self, method: str, path: str, params: Mapping[str, Any]
    ) -> tuple[str, tuple[tuple[str, str], ...]] | None:
        if method.upper() != "GET" or path.endswith("/image"):
            return None
        return path, tuple(sorted((str(k), str(v)) for k, v in params.items()))

    async def _send_with_read_limit(
        self,
        *,
        method: str,
        path: str,
        params: dict[str, Any],
        payload: dict[str, Any] | None,
        headers: dict[str, str],
        operation: str,
        attempt: int,
    ) -> httpx.Response:
        """Two owned read slots per organization across app and worker."""
        owner = uuid.uuid4().hex
        slot: str | None = None
        if method.upper() in {"GET", "HEAD", "OPTIONS"}:
            for _ in range(20):
                for number in range(2):
                    key = f"zoho:inventory:read_slot:{number}"
                    if await self.redis.set(key, owner, nx=True, ex=35):
                        slot = key
                        break
                if slot:
                    break
                await asyncio.sleep(0.05)
            if slot is None:
                await self.metrics.record("skipped", operation, "read_slots_busy")
                raise InventoryReadUnavailable(status_code=None)
        try:
            remaining = await self._cooldown_remaining()
            if remaining > 0:
                await self.metrics.record("skipped", operation, "cooldown")
                raise self._cooldown_error(method, path, remaining)

            async def send() -> httpx.Response:
                await self.metrics.record(
                    "attempt",
                    operation,
                    "sent",
                    detail="retry" if attempt > 1 else "initial",
                )
                return await self.client.request(
                    method=method,
                    url=path,
                    params=params,
                    json=payload,
                    headers=headers,
                )

            if slot:
                try:
                    async with asyncio.timeout(30):
                        return await send()
                except TimeoutError as exc:
                    raise httpx.ReadTimeout(
                        "Inventory read deadline exceeded",
                        request=httpx.Request(method, f"{self.base_url}{path}"),
                    ) from exc
            return await send()
        except asyncio.CancelledError:
            await self.metrics.record("http", operation, "cancelled")
            raise
        finally:
            if slot:
                with contextlib.suppress(Exception):
                    await release_zoho_oauth_lock(
                        self.redis, lock_key=slot, owner_token=owner
                    )

    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        *,
        bypass_cache: bool = False,
        operation: str = "other",
    ) -> httpx.Response:
        """Make an authenticated request to Zoho Inventory API with retries."""
        params = dict(params) if params else {}
        params["organization_id"] = self.org_id
        if operation == "other":
            family = path.strip("/").split("/")[0]
            family = (
                family
                if family in {"items", "contacts", "salesorders", "itemdetails"}
                else "other"
            )
            operation = f"{family}_{'read' if method.upper() in {'GET', 'HEAD', 'OPTIONS'} else 'write'}"

        cache = self._read_cache
        cache_key = None if bypass_cache else self._read_cache_key(method, path, params)
        if cache_key is None:
            cache.clear()
        else:
            cached = cache.get(cache_key)
            if cached is not None and time.monotonic() - cached[0] < (
                _READ_CACHE_TTL_SECONDS
            ):
                await self.metrics.record("skipped", operation, "read_cache")
                return cached[1]

        remaining = await self._cooldown_remaining()
        if remaining > 0:
            logger.warning(
                "Zoho Inventory operation=%s skipped: rate-limit cooldown %.1fs",
                operation,
                remaining,
            )
            await self.metrics.record("skipped", operation, "cooldown")
            raise self._cooldown_error(method.upper(), path, remaining)

        # Retry mechanism (3 attempts with backoff)
        max_retries = 3
        retry_read = method.upper() in {"GET", "HEAD", "OPTIONS"}
        waited = 0.0

        for attempt in range(1, max_retries + 1):
            if attempt > 1:
                await self.metrics.record("retry", operation, "attempt")
            token = await self._ensure_token()
            headers = {"Authorization": f"Zoho-oauthtoken {token}"}

            try:
                response = await self._send_with_read_limit(
                    method=method,
                    path=path,
                    params=params,
                    payload=json,
                    headers=headers,
                    operation=operation,
                    attempt=attempt,
                )

                reason = "unknown"
                if response.status_code == 429:
                    with contextlib.suppress(ValueError, TypeError):
                        code = response.json().get("code")
                        reason = "minute" if code == 44 else "unknown"
                await self.metrics.record(
                    "http", operation, str(response.status_code), detail=reason
                )

                # If Unauthorized, token might be invalid/expired, force refresh next time
                if response.status_code == 401:
                    await self.redis.delete("zoho:access_token")
                    if attempt < max_retries:
                        continue

                response.raise_for_status()
                if cache_key is not None:
                    if len(cache) >= _READ_CACHE_MAX_ENTRIES:
                        cache.clear()
                    cache[cache_key] = (time.monotonic(), response)
                return response

            except httpx.HTTPStatusError as e:
                if e.response.status_code != 429:
                    raise
                if isinstance(e, ZohoRateLimitError) and e.local_cooldown:
                    raise
                retry_after = parse_retry_after(e.response.headers.get("retry-after"))
                wait = retry_after if retry_after is not None else float(2**attempt)
                if (
                    retry_read
                    and attempt < max_retries
                    and wait <= _RATE_LIMIT_MAX_INLINE_WAIT_SECONDS
                    and waited + wait <= _RATE_LIMIT_INLINE_WAIT_BUDGET_SECONDS
                ):
                    await self._start_cooldown(wait)
                    waited += wait
                    await asyncio.sleep(wait)
                    continue
                cooldown = (
                    retry_after
                    if retry_after is not None
                    else _RATE_LIMIT_DEFAULT_COOLDOWN_SECONDS
                )
                cooldown = await self._start_cooldown(cooldown)
                logger.warning(
                    "Zoho Inventory rate limit operation=%s after %d attempt(s); "
                    "cooldown %.0fs",
                    operation,
                    attempt,
                    cooldown,
                )
                raise ZohoRateLimitError(
                    "Zoho Inventory rate limited",
                    request=e.request,
                    response=e.response,
                    retry_after_seconds=retry_after,
                ) from e

            except (httpx.TimeoutException, httpx.NetworkError):
                await self.metrics.record("http", operation, "transport_error")
                if retry_read and attempt < max_retries:
                    await asyncio.sleep(2**attempt)
                    continue
                raise

        raise RuntimeError("Unreachable")

    async def get_items(
        self,
        page: int = 1,
        per_page: int = 200,
        *,
        end_products_only: bool = True,
    ) -> dict[str, Any]:
        """Fetch a page of active items from Zoho Inventory.

        Returns the raw dict containing 'items' and 'page_context'.
        """
        params: dict[str, Any] = {
            "page": page,
            "per_page": per_page,
            "status": "active",
        }
        if end_products_only:
            # Treejar-specific custom field: filters only end products (not raw materials)
            params["cf_end_product"] = "true"
        response = await self._request("GET", "/items", params=params)
        return dict(response.json())

    @staticmethod
    def incremental_eligible() -> bool:
        return bool(
            settings.zoho_stock_incremental_enabled
            and settings.zoho_stock_coverage_evidence.strip()
        )

    async def _read_stock_snapshot(self) -> tuple[StockSnapshot | None, bool]:
        try:
            state, raw = await self.stock_store.read()
            if state is not None:
                evidence = (
                    settings.zoho_stock_coverage_evidence
                    if self.incremental_eligible()
                    else ""
                )
                items = state.stock_items(evidence)
                return StockSnapshot(as_of=state.full_at or 0, items=items), True
            # Never reinterpret corrupt v2 as a new covered generation. Legacy
            # data is safe only at its original full observation time.
            legacy = await self.redis.get(ZOHO_STOCK_SNAPSHOT_KEY)
            snapshot = StockSnapshot.from_raw(legacy)
            return snapshot, not raw and (legacy is None or snapshot is not None)
        except Exception:
            logger.warning("Could not read Zoho stock state")
            return None, False

    async def _stock_snapshot(self) -> StockSnapshot | None:
        # Recovery is worker-owned. A customer never downloads the catalog.
        snapshot, _ = await self._read_stock_snapshot()
        return snapshot

    @staticmethod
    def _usable_stock(item: dict[str, Any] | None) -> bool:
        if (
            item is None
            or not has_numeric_stock(item)
            or item.get("status", "active") != "active"
        ):
            return False
        try:
            age = time.time() - datetime.fromisoformat(item["stock_as_of"]).timestamp()
            # ISO timestamps round floats to microseconds. Ignore that tiny
            # representation error, while rejecting genuinely future evidence.
            return -0.001 <= age < STOCK_SNAPSHOT_STALE_SECONDS
        except (KeyError, ValueError, TypeError):
            return False

    async def refresh_stock_snapshot(
        self, *, incremental: bool = False, startup: bool = False
    ) -> StockSnapshot | None:
        owner: str | None = None
        operation = "delta" if incremental and self.incremental_eligible() else "full"
        try:
            if await self._cooldown_remaining() > 0:
                await self.metrics.record("skipped", operation, "cooldown")
                return None
            owner = await self.stock_store.acquire()
            if owner is None:
                await self.metrics.record("skipped", operation, "lock")
                return None
            state, raw = await self.stock_store.read()
            started = time.time()
            eligible = self.incremental_eligible()
            if startup and state and state.coverage and state.full_at:
                freshness = (
                    state.coverage
                    if eligible
                    and state.coverage_evidence == settings.zoho_stock_coverage_evidence
                    else state.full_at
                )
                if 0 <= started - freshness < STOCK_SNAPSHOT_STALE_SECONDS:
                    await self.metrics.record("skipped", operation, "startup_fresh")
                    return None
            # A missing/unusable cursor or overdue reconciliation always needs
            # a complete baseline. No delta may be merged into a legacy file.
            delta = bool(
                incremental
                and eligible
                and state
                and state.coverage
                and state.full_at
                and started - state.full_at < 86400
            )
            operation = "delta" if delta else "full"
            previous = state if delta and state else StockState()
            boundary = (
                previous.coverage or started
            ) - settings.zoho_stock_overlap_seconds

            async def read_pages() -> tuple[dict[str, dict[str, Any]], int]:
                records: dict[str, dict[str, Any]] = {}
                previous_page_ids: set[str] = set()
                for page in range(1, STOCK_SNAPSHOT_MAX_PAGES + 1):
                    await self.stock_store.renew(owner)
                    params: dict[str, Any] = {
                        "page": page,
                        "per_page": STOCK_SNAPSHOT_PAGE_SIZE,
                    }
                    if delta:
                        # No status filter: deactivation and SKU changes must arrive.
                        params["last_modified_time"] = datetime.fromtimestamp(
                            boundary, UTC
                        ).strftime("%Y-%m-%dT%H:%M:%S%z")
                        params["sort_column"] = "last_modified_time"
                        params["sort_order"] = "A"
                    else:
                        params["status"] = "active"
                    response = await self._request(
                        "GET",
                        "/items",
                        params=params,
                        bypass_cache=True,
                        operation=operation,
                    )
                    data = response.json()
                    if (
                        not isinstance(data, dict)
                        or data.get("code", 0) != 0
                        or not isinstance(data.get("items"), list)
                    ):
                        raise ValueError("Invalid Zoho stock page")
                    context = data.get("page_context")
                    if not isinstance(context, dict) or not isinstance(
                        context.get("has_more_page"), bool
                    ):
                        raise ValueError("Missing Zoho stock continuation")
                    if context.get("page", page) != page:
                        raise ValueError("Wrong Zoho stock page")
                    page_ids: set[str] = set()
                    for row in data["items"]:
                        if (
                            not isinstance(row, dict)
                            or not isinstance(row.get("item_id"), str)
                            or not row["item_id"]
                            or not isinstance(row.get("sku"), str)
                        ):
                            raise ValueError("Invalid Zoho stock identity")
                        record = {k: row[k] for k in _STOCK_SNAPSHOT_FIELDS if k in row}
                        # Valid unknown quantities replace the old figure with
                        # unknown. They never silently preserve a stale number.
                        if row["item_id"] in previous_page_ids:
                            raise ValueError(
                                "Unstable stock pagination repeated an identity across pages"
                            )
                        page_ids.add(row["item_id"])
                        records[row["item_id"]] = record
                    previous_page_ids.update(page_ids)
                    await self.metrics.record("pages", operation, "processed")
                    await self.metrics.record(
                        "items", operation, "processed", count=len(data["items"])
                    )
                    if not context["has_more_page"]:
                        return records, page
                else:
                    raise ValueError("Stock page cap reached")

            records, pages = await read_pages()
            if delta and pages > 1:
                # Offset pages can shift after deletion as well as updates.
                # Verify the complete set twice; any change fails this cycle.
                # This safeguard does not replace the provider coverage gate.
                confirmation, _ = await read_pages()
                if confirmation != records:
                    raise ValueError("Stock pagination changed between complete reads")
            previous.items.update(records)
            previous.observed.update(dict.fromkeys(records, started))
            previous.coverage = started
            previous.coverage_evidence = (
                settings.zoho_stock_coverage_evidence if eligible else ""
            )
            previous.generation = uuid.uuid4().hex
            if delta:
                previous.delta_at = started
            else:
                previous.full_at = started
            snapshot = StockSnapshot(
                started, previous.stock_items(previous.coverage_evidence)
            )
            # v1 is a last-full rollback baseline, never relabelled by deltas.
            legacy_items: dict[str, dict[str, Any]] = {}
            for row in snapshot.items.values():
                sku = row["sku"]
                current = legacy_items.get(sku)
                if (
                    current is None
                    or not has_numeric_stock(current)
                    and has_numeric_stock(row)
                ):
                    legacy_items[sku] = row
            legacy = StockSnapshot(started, legacy_items).to_json() if not delta else ""
            await self.stock_store.renew(owner)
            if not await self.stock_store.commit(owner, raw, previous, legacy):
                raise RuntimeError("Stock generation changed before publication")
            await self.metrics.record("cycle", operation, "success")
            logger.info(
                "Zoho stock cycle operation=%s items=%d coverage_age=0",
                operation,
                len(previous.items),
            )
            return snapshot
        except Exception as exc:
            await self.metrics.record("cycle", operation, "failed")
            logger.warning(
                "Zoho stock cycle failed operation=%s error=%s; retained previous generation",
                operation,
                type(exc).__name__,
            )
            return None
        finally:
            if owner:
                with contextlib.suppress(Exception):
                    await self.stock_store.release(owner)

    async def get_stock(self, sku: str) -> dict[str, Any] | None:
        """Get the Zoho item carrying stock for a SKU.

        Served from the shared snapshot when it holds a numeric stock for the
        SKU; otherwise looked up live. Returns None if Zoho has no such SKU.
        """
        snapshot = await self._stock_snapshot()
        if snapshot is not None:
            item = snapshot.lookup(sku)
            if item is not None and self._usable_stock(item):
                return item
        return await self._live_stock(sku)

    async def _live_stock(self, sku: str) -> dict[str, Any] | None:
        response = await self._request("GET", "/items", params={"search_text": sku})
        data = response.json()

        items = data.get("items", [])
        if not isinstance(items, list):
            return None

        # search_text is a partial match, so pick the SKU match locally.
        item = select_stock_item(
            sku,
            (
                row
                for row in items
                if isinstance(row, Mapping) and row.get("status", "active") == "active"
            ),
        )
        if item is not None and not has_numeric_stock(item):
            return None
        return item

    async def get_stock_bulk(self, skus: list[str]) -> list[dict[str, Any]]:
        """Get stock levels for multiple SKUs.

        SKUs the snapshot answers with a number cost no Zoho call; the rest
        are looked up live, at most five at a time. One failed live lookup
        only drops that SKU. When nothing could be served and a live lookup
        raised, the first error is raised, so callers can still tell "Zoho is
        unavailable" from "these SKUs are not in Zoho".
        """
        unique_skus = list(dict.fromkeys(skus))
        snapshot = await self._stock_snapshot()
        served: list[dict[str, Any]] = []
        misses: list[str] = []
        for sku in unique_skus:
            item = snapshot.lookup(sku) if snapshot is not None else None
            if item is not None and self._usable_stock(item):
                served.append(item)
            else:
                misses.append(sku)
        if not misses:
            return served

        sem = asyncio.Semaphore(2)  # shared Redis slots bound all process reads too

        async def _fetch(sku: str) -> dict[str, Any] | None:
            async with sem:
                return await self._live_stock(sku)

        results = await asyncio.gather(
            *[_fetch(sku) for sku in misses], return_exceptions=True
        )
        errors: list[Exception] = []
        for _sku, result in zip(misses, results, strict=True):
            if isinstance(result, BaseException):
                if not isinstance(result, Exception):
                    raise result
                errors.append(result)
                logger.warning(
                    "Zoho live stock lookup failed (%s)",
                    type(result).__name__,
                )
            elif result is not None:
                served.append(result)
        if errors and not served:
            raise errors[0]
        return served

    async def _resolve_fresh_identity(self, sku: str) -> str:
        candidates: list[dict[str, Any]] = []
        for page in range(1, 3):
            response = await self._request(
                "GET",
                "/items",
                params={"search_text": sku, "page": page, "per_page": 200},
                bypass_cache=True,
                operation="fresh_resolve",
            )
            data = response.json()
            if (
                not isinstance(data, dict)
                or data.get("code", 0) != 0
                or not isinstance(data.get("items"), list)
            ):
                raise InventoryReadUnavailable(status_code=None)
            candidates.extend(
                row
                for row in data["items"]
                if isinstance(row, dict)
                and row.get("status", "active") == "active"
                and isinstance(row.get("sku"), str)
                and _sku_match_key(row["sku"]) == _sku_match_key(sku)
            )
            context = data.get("page_context")
            if not isinstance(context, dict) or not isinstance(
                context.get("has_more_page"), bool
            ):
                raise InventoryReadUnavailable(status_code=None)
            if not context["has_more_page"]:
                break
        else:
            raise InventoryReadUnavailable(status_code=None)
        matching = _stock_identity_group(sku, candidates)
        ids = {row.get("item_id") for row in matching}
        if (
            len(ids) != 1
            or not isinstance(next(iter(ids), None), str)
            or not next(iter(ids))
        ):
            await self.metrics.record("mapping", "fresh", "missing_or_ambiguous")
            raise InventoryReadUnavailable(status_code=None)
        return str(next(iter(ids)))

    async def get_stock_bulk_fresh(self, skus: list[str]) -> list[dict[str, Any]]:
        """Selected items only, bypassing both caches. Incomplete means defer.

        Without a measured bulk limit, use direct ID GETs; do not infer the
        bulk limit from the list page size. Rows are validated again after
        resolution, including renames and inactive items.
        """
        selected = list(dict.fromkeys(skus))
        try:
            state, _ = await self.stock_store.read()
        except Exception:
            state = None
        snapshot = StockSnapshot(0, state.items) if state else None
        identities: dict[str, str] = {}
        verified: list[tuple[dict[str, Any], float]] = []
        try:
            for sku in selected:
                candidates = [
                    row
                    for row in (state.items.values() if state else ())
                    if isinstance(row.get("sku"), str)
                    and _sku_match_key(row["sku"]) == _sku_match_key(sku)
                    and row.get("status", "active") == "active"
                ]
                group = _stock_identity_group(sku, candidates)
                ids = {row["item_id"] for row in group}
                if snapshot and len(ids) == 1:
                    identities[sku] = next(iter(ids))
                else:
                    identities[sku] = await self._resolve_fresh_identity(sku)
            item_ids = list(dict.fromkeys(identities.values()))
            size = (
                settings.zoho_stock_bulk_size
                if settings.zoho_stock_bulk_evidence
                else 0
            )
            by_id: dict[str, dict[str, Any]] = {}
            for start in range(0, len(item_ids), size or 1):
                chunk = item_ids[start : start + (size or 1)]
                observed_at = time.time()
                raw_rows: Any
                try:
                    response = await self._request(
                        "GET",
                        "/itemdetails" if size else f"/items/{chunk[0]}",
                        params={"item_ids": ",".join(chunk)} if size else None,
                        bypass_cache=True,
                        operation="fresh_bulk" if size else "fresh_item",
                    )
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code != 404:
                        raise
                    raw_rows = []  # Removed ID: resolve only selected SKUs below.
                    if not size and state and chunk[0] in state.items:
                        removed = dict(state.items[chunk[0]])
                        removed["status"] = "inactive"
                        verified.append((removed, observed_at))
                else:
                    data = response.json()
                    if not isinstance(data, dict) or data.get("code", 0) != 0:
                        raise InventoryReadUnavailable(status_code=None)
                    raw_rows = data.get("items") if size else [data.get("item")]
                if not isinstance(raw_rows, list):
                    raise InventoryReadUnavailable(status_code=None)
                for row in raw_rows:
                    if (
                        not isinstance(row, dict)
                        or row.get("item_id") not in chunk
                        or not isinstance(row.get("sku"), str)
                    ):
                        raise InventoryReadUnavailable(status_code=None)
                    item_id = row["item_id"]
                    if item_id in by_id:
                        raise InventoryReadUnavailable(status_code=None)
                    # Identity records are preserved even for an inactive or
                    # renamed item, preventing resurrection of old aliases.
                    record = {k: row[k] for k in _STOCK_SNAPSHOT_FIELDS if k in row}
                    verified.append((record, observed_at))
                    if row.get("status", "active") != "active" or not has_numeric_stock(
                        row
                    ):
                        continue
                    by_id[item_id] = {
                        **record,
                        "stock_as_of": datetime.fromtimestamp(
                            observed_at, UTC
                        ).isoformat(),
                    }
            result = []
            for sku in selected:
                row = by_id.get(identities[sku])
                if row is None or _sku_match_key(row["sku"]) != _sku_match_key(sku):
                    # A mapping can be renamed between reads. Resolve the
                    # selected SKU once, with no snapshot/direct fallback.
                    replacement = await self._resolve_fresh_identity(sku)
                    observed_at = time.time()
                    try:
                        response = await self._request(
                            "GET",
                            f"/items/{replacement}",
                            bypass_cache=True,
                            operation="fresh_item",
                        )
                    except httpx.HTTPStatusError as exc:
                        if exc.response.status_code == 404:
                            raise InventoryReadUnavailable(status_code=404) from exc
                        raise
                    data = response.json()
                    row = (
                        data.get("item")
                        if isinstance(data, dict) and data.get("code", 0) == 0
                        else None
                    )
                    if (
                        not isinstance(row, dict)
                        or row.get("item_id") != replacement
                        or not isinstance(row.get("sku"), str)
                        or _sku_match_key(row["sku"]) != _sku_match_key(sku)
                        or not has_numeric_stock(row)
                        or row.get("status", "active") != "active"
                    ):
                        raise InventoryReadUnavailable(status_code=None)
                    original_id = identities[sku]
                    if (
                        replacement != original_id
                        and state
                        and original_id in state.items
                        and not any(
                            record["item_id"] == original_id for record, _ in verified
                        )
                    ):
                        # Unique live SKU resolution replaced an omitted old
                        # mapping. Retire its cached alias in the same CAS;
                        # a confirmed rename/unknown row above already does so.
                        retired = dict(state.items[original_id])
                        retired["status"] = "inactive"
                        verified.append((retired, observed_at))
                    verified.append((row, observed_at))
                result.append(row)
            await self.metrics.record("fresh", "quotation", "complete")
            return result
        except Exception:
            await self.metrics.record("fresh", "quotation", "unavailable")
            raise
        finally:
            if verified:
                with contextlib.suppress(Exception):
                    await self.stock_store.update_fresh(verified)

    async def get_item(self, item_id: str) -> dict[str, Any] | None:
        """Get a specific item by Zoho Inventory item_id.

        Served from the shared snapshot when it holds a numeric stock for the
        item, like `get_stock`; otherwise looked up live. Every caller reads
        it for stock, so a Zoho rate limit must not hide a snapshot figure.
        """
        snapshot = await self._stock_snapshot()
        if snapshot is not None:
            item = snapshot.lookup_item_id(item_id)
            if item is not None and self._usable_stock(item):
                return item
        try:
            response = await self._request("GET", f"/items/{item_id}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

        data = response.json()
        item = data.get("item")
        if (
            isinstance(item, dict)
            and str(item.get("item_id", "")) == item_id
            and item.get("status", "active") == "active"
            and has_numeric_stock(item)
        ):
            return dict(item)
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
        self,
        contacts: list[dict[str, Any]],
        *,
        include_inactive: bool = False,
    ) -> dict[str, Any] | None:
        for candidate in contacts:
            candidate_status = str(candidate.get("status") or "").strip().lower()
            if not _is_active_customer(candidate) and not (
                include_inactive and candidate_status == "inactive"
            ):
                continue

            contact_id = str(candidate.get("contact_id") or "").strip()
            if not contact_id:
                continue

            contact = await self.get_contact(contact_id)
            contact_status = str((contact or {}).get("status") or "").strip().lower()
            if contact is None or (
                not _is_active_customer(contact)
                and not (include_inactive and contact_status == "inactive")
            ):
                continue

            return contact

        return None

    async def find_customer_by_phone(
        self,
        phone: str,
        *,
        include_inactive: bool = False,
    ) -> dict[str, Any] | None:
        """Find an exact customer by normalized phone matching."""
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
                filter_by=("Status.Inactive" if include_inactive else "Status.Active"),
                **{field: value},
            )
            matched_contacts = [
                contact
                for contact in contacts
                if any(
                    _phones_equivalent(candidate_phone, normalized_phone)
                    for candidate_phone in _contact_phone_values(contact)
                )
            ]
            contact = await self._first_accessible_customer(
                matched_contacts,
                include_inactive=include_inactive,
            )
            if contact is not None:
                return contact

        return None

    async def find_inactive_customer_by_phone(
        self, phone: str
    ) -> dict[str, Any] | None:
        """Find an exact inactive customer by normalized phone."""
        return await self.find_customer_by_phone(phone, include_inactive=True)

    async def find_customer_by_email(
        self,
        email: str,
        *,
        include_inactive: bool = False,
    ) -> dict[str, Any] | None:
        """Find an exact customer by email address."""
        normalized_email = email.strip().casefold()
        if not normalized_email:
            return None

        contacts = await self.search_contacts(
            filter_by="Status.Inactive" if include_inactive else "Status.Active",
            email=email.strip(),
        )
        exact_matches = [
            contact
            for contact in contacts
            if any(
                candidate_email.strip().casefold() == normalized_email
                for candidate_email in _contact_email_values(contact)
            )
        ]
        return await self._first_accessible_customer(
            exact_matches,
            include_inactive=include_inactive,
        )

    async def find_inactive_customer_by_email(
        self, email: str
    ) -> dict[str, Any] | None:
        """Find an exact inactive customer by email address."""
        return await self.find_customer_by_email(email, include_inactive=True)

    async def find_customer_by_name(self, name: str) -> dict[str, Any] | None:
        """Find an accessible active customer by exact normalized name.

        Zoho's name filters are not reliable enough for exact lookup in live data, so
        we paginate active contacts and compare locally.
        """
        normalized_name = _normalize_contact_name(name)
        if not normalized_name:
            return None

        page = 1
        per_page = 200

        while True:
            response = await self._request(
                "GET",
                "/contacts",
                params={
                    "filter_by": "Status.Active",
                    "page": page,
                    "per_page": per_page,
                },
            )
            data = response.json()
            raw_contacts = data.get("contacts", [])
            if not isinstance(raw_contacts, list):
                return None

            contacts = [
                contact
                for raw_contact in raw_contacts
                if (contact := _coerce_inventory_contact(raw_contact)) is not None
            ]
            if not contacts:
                return None

            exact_matches = [
                contact
                for contact in contacts
                if any(
                    _normalize_contact_name(candidate_name) == normalized_name
                    for candidate_name in _contact_name_values(contact)
                )
            ]
            matched = await self._first_accessible_customer(exact_matches)
            if matched is not None:
                return matched

            page_context = data.get("page_context")
            has_more_page = (
                bool(page_context.get("has_more_page"))
                if isinstance(page_context, Mapping)
                else False
            )
            if not has_more_page:
                return None

            page += 1

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

    async def activate_contact(self, contact_id: str) -> None:
        """Mark an existing Zoho Inventory contact active."""
        await self._request("POST", f"/contacts/{contact_id}/active")

    async def create_sale_order(
        self,
        customer_id: str,
        items: list[dict[str, Any]],
        status: str = "draft",
    ) -> dict[str, Any]:
        """Create a sale order / quotation in Zoho Inventory."""
        data = {
            "customer_id": customer_id,
            "line_items": items,
            "status": status,
        }
        response = await self._request("POST", "/salesorders", json=data)
        return normalize_sale_order_response(response.json())

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

        so = extract_sale_order_data(raw)
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
