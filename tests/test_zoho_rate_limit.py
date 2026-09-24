"""Zoho Inventory 429 handling in the client (tj-uz6j.9).

Production 2026-09-23: a shared-org Zoho quota answered 429, the client retried
blindly, and a duplicate-name fallback kept paging contacts into the limit.
"""

from __future__ import annotations

import json
import time
from typing import Any
from unittest.mock import ANY, AsyncMock, patch

import httpx
import pytest

from src.integrations.inventory.zoho_inventory import (
    ZOHO_RATE_LIMIT_COOLDOWN_KEY,
    ZOHO_STOCK_SNAPSHOT_KEY,
    ZOHO_STOCK_SNAPSHOT_LOCK_KEY,
    ZohoInventoryClient,
    ZohoRateLimitError,
    parse_retry_after,
)


class _FakeRedis:
    def __init__(
        self,
        values: dict[str, Any] | None = None,
        *,
        snapshot_lock_held: bool = True,
    ) -> None:
        # By default another worker holds the stock snapshot refresh lock and
        # no snapshot is stored, so stock reads take the live path these
        # rate-limit tests exercise. The snapshot tests below free the lock.
        self.values: dict[str, Any] = {"zoho:access_token": b"token"}
        if snapshot_lock_held:
            self.values[ZOHO_STOCK_SNAPSHOT_LOCK_KEY] = b"another-worker"
        self.values.update(values or {})
        self.set_calls: list[tuple[str, Any, Any]] = []

    async def get(self, key: str) -> Any:
        return self.values.get(key)

    async def set(self, key: str, value: Any, ex: Any = None, nx: bool = False) -> bool:
        if nx and key in self.values:
            return False
        self.set_calls.append((key, value, ex))
        self.values[key] = value
        return True

    async def delete(self, key: str) -> None:
        self.values.pop(key, None)

    async def eval(self, script: str, numkeys: int, key: str, owner: str) -> int:
        if self.values.get(key) == owner:
            del self.values[key]
            return 1
        return 0


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
    with patch.object(client, "_live_stock", AsyncMock(return_value=None)) as get:
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


# ---------------------------------------------------------------------------
# tj-4qtv: shared stock snapshot. Live 2026-09-24, every product search asked
# Zoho once per SKU, the org quota answered 429, and one failed SKU failed the
# whole bulk read, so customers were told stock was "unconfirmed".
# ---------------------------------------------------------------------------


def _snapshot_value(items: list[dict[str, Any]], *, age: float) -> str:
    return json.dumps(
        {
            "as_of": time.time() - age,
            "items": {item["sku"]: item for item in items},
        }
    )


def _item(sku: str, stock: Any) -> dict[str, Any]:
    return {"item_id": f"id-{sku}", "sku": sku, "stock_on_hand": stock, "rate": 10.0}


def _stored_snapshot(redis: _FakeRedis) -> dict[str, Any]:
    return dict(json.loads(redis.values[ZOHO_STOCK_SNAPSHOT_KEY]))


async def test_snapshot_is_built_from_paged_items_and_serves_later_reads() -> None:
    redis = _FakeRedis(snapshot_lock_held=False)
    client = _client(redis)
    page_one = _response(
        200,
        json={
            "items": [
                {**_item("A", 3), "name": "Chair A", "extra_field": "dropped"},
                {"name": "no sku"},
            ],
            "page_context": {"has_more_page": True},
        },
    )
    page_two = _response(
        200,
        json={"items": [_item("B", 0)], "page_context": {"has_more_page": False}},
    )
    request = AsyncMock(side_effect=[page_one, page_two])
    with patch.object(client.client, "request", request):
        item = await client.get_stock("A")
        assert await client.get_stock_bulk(["B", "A"]) == [
            {**_item("B", 0), "stock_as_of": ANY},
            {**_item("A", 3), "name": "Chair A", "stock_as_of": ANY},
        ]

    assert item is not None
    assert item["stock_on_hand"] == 3
    assert "extra_field" not in item
    assert request.await_count == 2
    pages = [call.kwargs["params"] for call in request.await_args_list]
    assert [params["page"] for params in pages] == [1, 2]
    assert all(params["per_page"] == 200 for params in pages)
    assert all(params["status"] == "active" for params in pages)
    assert all("cf_end_product" not in params for params in pages)
    stored = _stored_snapshot(redis)
    assert sorted(stored["items"]) == ["A", "B"]
    assert stored["as_of"] == pytest.approx(time.time(), abs=5)
    snapshot_set = next(c for c in redis.set_calls if c[0] == ZOHO_STOCK_SNAPSHOT_KEY)
    assert snapshot_set[2] == 3600
    assert ZOHO_STOCK_SNAPSHOT_LOCK_KEY not in redis.values
    await client.close()


async def test_stale_snapshot_is_refreshed_by_the_lock_holder() -> None:
    redis = _FakeRedis(
        {ZOHO_STOCK_SNAPSHOT_KEY: _snapshot_value([_item("A", 1)], age=700)},
        snapshot_lock_held=False,
    )
    client = _client(redis)
    fresh_page = _response(
        200,
        json={"items": [_item("A", 9)], "page_context": {"has_more_page": False}},
    )
    request = AsyncMock(return_value=fresh_page)
    with patch.object(client.client, "request", request):
        item = await client.get_stock("A")
    assert item is not None and item["stock_on_hand"] == 9
    assert request.await_count == 1
    assert _stored_snapshot(redis)["items"]["A"]["stock_on_hand"] == 9
    assert ZOHO_STOCK_SNAPSHOT_LOCK_KEY not in redis.values
    await client.close()


async def test_fresh_snapshot_hit_makes_no_zoho_call() -> None:
    redis = _FakeRedis(
        {
            ZOHO_STOCK_SNAPSHOT_KEY: _snapshot_value(
                [_item("A", 4), _item("B", 0)], age=30
            )
        },
        snapshot_lock_held=False,
    )
    client = _client(redis)
    request = AsyncMock()
    with patch.object(client.client, "request", request):
        items = await client.get_stock_bulk(["A", "B", "A"])
        single = await client.get_stock("B")
    request.assert_not_awaited()
    assert [item["stock_on_hand"] for item in items] == [4, 0]
    assert single is not None and single["stock_on_hand"] == 0
    assert all(item["stock_as_of"] for item in items)
    assert not any(key == ZOHO_STOCK_SNAPSHOT_LOCK_KEY for key, *_ in redis.set_calls)
    await client.close()


async def test_stale_snapshot_is_served_while_another_worker_refreshes() -> None:
    redis = _FakeRedis(
        {ZOHO_STOCK_SNAPSHOT_KEY: _snapshot_value([_item("A", 5)], age=1200)}
    )
    client = _client(redis)
    request = AsyncMock()
    with patch.object(client.client, "request", request):
        item = await client.get_stock("A")
    request.assert_not_awaited()
    assert item is not None and item["stock_on_hand"] == 5
    assert redis.values[ZOHO_STOCK_SNAPSHOT_LOCK_KEY] == b"another-worker"
    await client.close()


async def test_snapshot_past_the_stale_window_falls_back_to_live_lookup() -> None:
    redis = _FakeRedis(
        {ZOHO_STOCK_SNAPSHOT_KEY: _snapshot_value([_item("A", 5)], age=4000)}
    )
    client = _client(redis)
    live = _response(200, json={"items": [_item("A", 2)]})
    request = AsyncMock(return_value=live)
    with patch.object(client.client, "request", request):
        item = await client.get_stock("A")
    assert item == _item("A", 2)
    assert request.await_args.kwargs["params"]["search_text"] == "A"
    await client.close()


async def test_refresh_hitting_a_429_keeps_the_previous_snapshot() -> None:
    old = _snapshot_value([_item("A", 5)], age=900)
    redis = _FakeRedis({ZOHO_STOCK_SNAPSHOT_KEY: old}, snapshot_lock_held=False)
    client = _client(redis)
    request = AsyncMock(return_value=_response(429, headers={"Retry-After": "45"}))
    with (
        patch.object(client.client, "request", request),
        patch("src.integrations.inventory.zoho_inventory.asyncio.sleep", AsyncMock()),
    ):
        item = await client.get_stock("A")
        # The cooldown the 429 started blocks the next refresh without a call.
        again = await client.get_stock("A")
    assert item is not None and item["stock_on_hand"] == 5
    assert again is not None and again["stock_on_hand"] == 5
    assert request.await_count == 1
    assert redis.values[ZOHO_STOCK_SNAPSHOT_KEY] == old
    assert ZOHO_STOCK_SNAPSHOT_LOCK_KEY not in redis.values
    await client.close()


async def test_unreadable_snapshot_goes_live_without_refreshing() -> None:
    redis = _FakeRedis({ZOHO_STOCK_SNAPSHOT_KEY: b"not json"}, snapshot_lock_held=False)
    client = _client(redis)
    request = AsyncMock(return_value=_response(200, json={"items": [_item("A", 1)]}))
    with patch.object(client.client, "request", request):
        assert await client.get_stock("A") == _item("A", 1)
    assert request.await_count == 1
    assert request.await_args.kwargs["params"]["search_text"] == "A"
    await client.close()


async def test_case_and_cyrillic_duplicates_prefer_the_item_with_stock() -> None:
    # Live 2026-09-24: 'CH 240 V black' had stock_on_hand None while
    # 'CH 240 V Black' had 12; the case-sensitive match picked the wrong one.
    cyrillic_sku = "СH 240 V white"  # leading Cyrillic Es
    snapshot = [
        _item("CH 240 V black", None),
        _item("CH 240 V Black", 12),
        _item(cyrillic_sku, 7),
    ]
    redis = _FakeRedis({ZOHO_STOCK_SNAPSHOT_KEY: _snapshot_value(snapshot, age=10)})
    client = _client(redis)
    live_duplicates = _response(
        200,
        json={"items": [_item("CH 240 V black", None), _item("CH 240 V Black", 12)]},
    )
    request = AsyncMock(return_value=live_duplicates)
    with patch.object(client.client, "request", request):
        black = await client.get_stock("CH 240 V black")
        white = await client.get_stock("CH 240 V White")
        request.assert_not_awaited()
        live = await client._live_stock("CH 240 V black")
    assert black is not None and black["sku"] == "CH 240 V Black"
    assert black["stock_on_hand"] == 12
    assert white is not None and white["stock_on_hand"] == 7
    assert live == _item("CH 240 V Black", 12)
    await client.close()


def _rate_limit_error() -> ZohoRateLimitError:
    response = _response(429, headers={"Retry-After": "30"})
    return ZohoRateLimitError(
        "rate limited",
        request=response.request,
        response=response,
        retry_after_seconds=30.0,
    )


async def test_bulk_serves_snapshot_hits_and_skips_a_failed_live_lookup() -> None:
    redis = _FakeRedis(
        {ZOHO_STOCK_SNAPSHOT_KEY: _snapshot_value([_item("A", 3)], age=10)}
    )
    client = _client(redis)

    async def live(sku: str) -> dict[str, Any] | None:
        if sku == "B":
            return _item("B", 1)
        raise _rate_limit_error()

    with patch.object(client, "_live_stock", AsyncMock(side_effect=live)) as lookup:
        items = await client.get_stock_bulk(["A", "B", "C"])
    assert sorted(call.args[0] for call in lookup.await_args_list) == ["B", "C"]
    assert [(item["sku"], item["stock_on_hand"]) for item in items] == [
        ("A", 3),
        ("B", 1),
    ]
    await client.close()


async def test_bulk_raises_the_first_error_when_nothing_could_be_served() -> None:
    client = _client(_FakeRedis())
    first = _rate_limit_error()

    async def live(sku: str) -> dict[str, Any] | None:
        if sku == "A":
            raise first
        if sku == "B":
            return None
        raise httpx.ReadTimeout("slow")

    with (
        patch.object(client, "_live_stock", AsyncMock(side_effect=live)),
        pytest.raises(ZohoRateLimitError) as raised,
    ):
        await client.get_stock_bulk(["A", "B", "C"])
    assert raised.value is first
    await client.close()


async def test_bulk_with_only_missing_skus_returns_empty() -> None:
    client = _client(_FakeRedis())
    with patch.object(client, "_live_stock", AsyncMock(return_value=None)):
        assert await client.get_stock_bulk(["A", "B"]) == []
    await client.close()
