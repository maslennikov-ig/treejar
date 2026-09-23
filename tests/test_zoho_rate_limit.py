"""Zoho Inventory 429 handling in the client (tj-uz6j.9).

Production 2026-09-23: a shared-org Zoho quota answered 429, the client retried
blindly, and a duplicate-name fallback kept paging contacts into the limit.
"""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.integrations.inventory.zoho_inventory import (
    ZOHO_RATE_LIMIT_COOLDOWN_KEY,
    ZohoInventoryClient,
    ZohoRateLimitError,
    parse_retry_after,
)


class _FakeRedis:
    def __init__(self, values: dict[str, Any] | None = None) -> None:
        self.values: dict[str, Any] = {"zoho:access_token": b"token", **(values or {})}
        self.set_calls: list[tuple[str, Any, Any]] = []

    async def get(self, key: str) -> Any:
        return self.values.get(key)

    async def set(self, key: str, value: Any, ex: Any = None, nx: bool = False) -> bool:
        self.set_calls.append((key, value, ex))
        self.values[key] = value
        return True

    async def delete(self, key: str) -> None:
        self.values.pop(key, None)


def _response(
    status: int,
    *,
    method: str = "GET",
    json: Any = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    request = httpx.Request(method, "https://www.zohoapis.eu/inventory/v1/items")
    return httpx.Response(status, json=json, headers=headers or {}, request=request)


def _client(redis: _FakeRedis) -> ZohoInventoryClient:
    return ZohoInventoryClient(redis_client=redis)


@pytest.mark.asyncio
async def test_short_retry_after_is_honored_then_the_read_succeeds() -> None:
    client = _client(_FakeRedis())
    ok = _response(200, json={"items": [{"sku": "A", "stock_on_hand": 2}]})
    request = AsyncMock(side_effect=[_response(429, headers={"Retry-After": "3"}), ok])
    with (
        patch.object(client.client, "request", request),
        patch(
            "src.integrations.inventory.zoho_inventory.asyncio.sleep", AsyncMock()
        ) as sleep,
    ):
        item = await client.get_stock("A")
    assert item == {"sku": "A", "stock_on_hand": 2}
    sleep.assert_awaited_once_with(3.0)
    await client.close()


@pytest.mark.asyncio
async def test_long_retry_after_fails_fast_and_starts_a_shared_cooldown() -> None:
    redis = _FakeRedis()
    client = _client(redis)
    request = AsyncMock(return_value=_response(429, headers={"Retry-After": "45"}))
    with (
        patch.object(client.client, "request", request),
        patch(
            "src.integrations.inventory.zoho_inventory.asyncio.sleep", AsyncMock()
        ) as sleep,
    ):
        with pytest.raises(ZohoRateLimitError) as first:
            await client.get_stock("A")
        # The cooldown answers the next call without touching Zoho.
        with pytest.raises(ZohoRateLimitError) as second:
            await client.find_customer_by_name("Nadia")

    assert request.await_count == 1
    sleep.assert_not_awaited()
    assert first.value.response.status_code == 429
    assert isinstance(first.value, httpx.HTTPStatusError)
    assert first.value.retry_after_seconds == 45.0
    assert second.value.local_cooldown is True
    assert int(second.value.response.headers["retry-after"]) > 0
    key, deadline, ttl = redis.set_calls[-1]
    assert key == ZOHO_RATE_LIMIT_COOLDOWN_KEY
    assert ttl == 45
    assert float(deadline) > time.time() + 40
    await client.close()


@pytest.mark.asyncio
async def test_cooldown_started_by_another_process_is_respected() -> None:
    redis = _FakeRedis({ZOHO_RATE_LIMIT_COOLDOWN_KEY: f"{time.time() + 20:.3f}"})
    client = _client(redis)
    request = AsyncMock()
    with (
        patch.object(client.client, "request", request),
        pytest.raises(ZohoRateLimitError),
    ):
        await client.get_stock("A")
    request.assert_not_awaited()
    await client.close()


@pytest.mark.asyncio
async def test_expired_or_foreign_cooldown_values_do_not_block() -> None:
    ok = _response(200, json={"items": []})
    for stored in (f"{time.time() - 5:.3f}", b"not-a-deadline"):
        client = _client(_FakeRedis({ZOHO_RATE_LIMIT_COOLDOWN_KEY: stored}))
        with patch.object(client.client, "request", AsyncMock(return_value=ok)):
            assert await client.get_stock("A") is None
        await client.close()


@pytest.mark.asyncio
async def test_write_429_is_not_retried_and_is_typed() -> None:
    client = _client(_FakeRedis())
    request = AsyncMock(return_value=_response(429, method="POST"))
    with (
        patch.object(client.client, "request", request),
        patch("src.integrations.inventory.zoho_inventory.asyncio.sleep", AsyncMock()),
        pytest.raises(ZohoRateLimitError) as raised,
    ):
        await client.create_contact({"contact_name": "Nadia"})
    assert request.await_count == 1
    assert raised.value.retry_after_seconds is None
    await client.close()


@pytest.mark.asyncio
async def test_repeat_reads_in_one_client_are_served_once_and_writes_clear_them() -> (
    None
):
    client = _client(_FakeRedis())
    item_page = _response(200, json={"items": [{"sku": "A", "stock_on_hand": 1}]})
    contact = _response(200, method="POST", json={"contact": {"contact_id": "c-1"}})
    request = AsyncMock(side_effect=[item_page, contact, item_page])
    with patch.object(client.client, "request", request):
        await client.get_stock("A")
        await client.get_stock("A")
        assert request.await_count == 1
        await client.create_contact({"contact_name": "Nadia"})
        await client.get_stock("A")
    assert request.await_count == 3
    await client.close()


@pytest.mark.asyncio
async def test_bulk_stock_asks_once_per_distinct_sku() -> None:
    client = _client(_FakeRedis())
    with patch.object(client, "get_stock", AsyncMock(return_value=None)) as get:
        await client.get_stock_bulk(["A", "B", "A", "A"])
    assert sorted(call.args[0] for call in get.await_args_list) == ["A", "B"]
    await client.close()


def test_retry_after_accepts_seconds_and_http_dates() -> None:
    assert parse_retry_after("12") == 12.0
    http_date = "Wed, 23 Sep 2026 16:21:00 GMT"
    assert parse_retry_after(http_date, now=1790180400.0) == 60.0
    assert parse_retry_after(http_date, now=4_000_000_000.0) == 0.0
    assert parse_retry_after("soon") is None
    assert parse_retry_after(None) is None
