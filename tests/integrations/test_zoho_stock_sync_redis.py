"""Race/crash acceptance against a disposable real Redis, not an atomicity mock."""

from __future__ import annotations

import asyncio
import time
from typing import Any
from unittest.mock import patch

import httpx
import pytest
from tests.stock_sync_support import (
    client_with_transport,
    item,
    page,
    seed,
)

from src.integrations.inventory.stock_state import (
    LOCK_KEY,
    STATE_KEY,
    StockState,
    StockStore,
)
from src.integrations.inventory.zoho_inventory import (
    ZOHO_RATE_LIMIT_COOLDOWN_KEY,
    ZohoInventoryClient,
)


async def test_expired_writer_cannot_commit_or_release_new_owner(
    stock_redis: Any,
) -> None:
    state = await seed(stock_redis)
    store = StockStore(stock_redis)
    owner = await store.acquire()
    _, old_raw = await store.read()
    await stock_redis.pexpire(LOCK_KEY, 1)
    await asyncio.sleep(0.01)
    replacement = await store.acquire()
    newer = StockState(
        items=state.items,
        observed=state.observed,
        coverage=time.time(),
        full_at=time.time(),
    )
    assert await store.commit(replacement, old_raw, newer)
    before = await stock_redis.get(STATE_KEY)
    assert not await store.commit(owner, old_raw, state)
    with pytest.raises(RuntimeError, match="lease lost"):
        await store.renew(owner)
    await store.release(owner)
    assert await stock_redis.get(LOCK_KEY) == replacement
    assert await stock_redis.get(STATE_KEY) == before
    await store.release(replacement)


async def test_full_delta_share_one_lock_through_publication(
    stock_redis: Any, eligible: Any
) -> None:
    await seed(stock_redis)
    entered, finish = asyncio.Event(), asyncio.Event()
    calls = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        entered.set()
        await finish.wait()
        assert await stock_redis.get(LOCK_KEY)
        return httpx.Response(200, json=page([item("A", 8)]))

    full = client_with_transport(stock_redis, handler)
    delta = client_with_transport(stock_redis, handler)
    task = asyncio.create_task(full.refresh_stock_snapshot())
    await entered.wait()
    assert await delta.refresh_stock_snapshot(incremental=True) is None
    assert len(calls) == 1
    finish.set()
    assert await task
    assert await stock_redis.get(LOCK_KEY) is None
    assert (await full.stock_store.read())[0].items["id-A"]["stock_on_hand"] == 8
    await full.close()
    await delta.close()


async def test_fresh_read_fences_late_sync_and_source_observation(
    stock_redis: Any, eligible: Any
) -> None:
    await seed(stock_redis)
    entered, finish = asyncio.Event(), asyncio.Event()

    async def handler(request: httpx.Request) -> httpx.Response:
        entered.set()
        await finish.wait()
        return httpx.Response(200, json=page([item("A", 99)]))

    client = client_with_transport(stock_redis, handler)
    task = asyncio.create_task(client.refresh_stock_snapshot(incremental=True))
    await entered.wait()
    observed_at = time.time() + 1
    assert await client.stock_store.update_fresh([(item("A", 2), observed_at)])
    after_fresh = await stock_redis.get(STATE_KEY)
    finish.set()
    assert await task is None
    assert await stock_redis.get(STATE_KEY) == after_fresh
    assert await client.stock_store.update_fresh([(item("A", 99), observed_at - 1)])
    state, _ = await client.stock_store.read()
    assert state.items["id-A"]["stock_on_hand"] == 2
    assert state.observed["id-A"] == observed_at
    await client.close()


async def test_redis_publication_failure_does_not_advance_cursor(
    stock_redis: Any, eligible: Any
) -> None:
    await seed(stock_redis)
    before = await stock_redis.get(STATE_KEY)
    original = stock_redis.eval

    async def fail_commit(script: str, *args: Any) -> Any:
        if "stock-generation-commit" in script:
            raise ConnectionError("synthetic publication interruption")
        return await original(script, *args)

    client = client_with_transport(
        stock_redis, lambda request: httpx.Response(200, json=page([item("A", 0)]))
    )
    with patch.object(stock_redis, "eval", fail_commit):
        assert await client.refresh_stock_snapshot(incremental=True) is None
    assert await stock_redis.get(STATE_KEY) == before
    assert await stock_redis.get(LOCK_KEY) is None
    assert await client.refresh_stock_snapshot(incremental=True)
    assert (await client.stock_store.read())[0].items["id-A"]["stock_on_hand"] == 0
    await client.close()


async def test_crash_cancel_retains_generation_and_releases_owned_lease(
    stock_redis: Any, eligible: Any
) -> None:
    await seed(stock_redis)
    before = await stock_redis.get(STATE_KEY)
    entered = asyncio.Event()

    async def handler(request: httpx.Request) -> httpx.Response:
        entered.set()
        await asyncio.Event().wait()
        raise AssertionError("unreachable")

    client = client_with_transport(stock_redis, handler)
    task = asyncio.create_task(client.refresh_stock_snapshot(incremental=True))
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert await stock_redis.get(STATE_KEY) == before
    assert await stock_redis.get(LOCK_KEY) is None
    await client.close()


async def test_concurrent_cooldown_only_extends_across_clients(
    stock_redis: Any,
) -> None:
    first, second = ZohoInventoryClient(stock_redis), ZohoInventoryClient(stock_redis)
    await asyncio.gather(first._start_cooldown(1800), second._start_cooldown(30))
    await second._start_cooldown(5)
    assert await stock_redis.ttl(ZOHO_RATE_LIMIT_COOLDOWN_KEY) >= 1798
    assert await first._cooldown_remaining() >= 1798
    assert await second._cooldown_remaining() >= 1798
    await first.close()
    await second.close()


async def test_shared_metrics_survive_new_process_client_and_exact_interval(
    stock_redis: Any, monkeypatch: Any
) -> None:
    now = int(time.time())
    monkeypatch.setattr(time, "time", lambda: now)
    first = client_with_transport(
        stock_redis, lambda request: httpx.Response(200, json=page([item()]))
    )
    assert await first.refresh_stock_snapshot()
    second = client_with_transport(
        stock_redis, lambda request: httpx.Response(200, json=page([]))
    )
    report = await second.metrics.report(now, now + 1)
    assert report["attempt|full|sent|initial"] == 1
    assert report["http|full|200|unknown"] == 1
    assert report["pages|full|processed|unknown"] == 1
    assert await second.metrics.report(now - 1, now) == {}
    await first.close()
    await second.close()


async def test_read_concurrency_is_shared_and_busy_calls_do_not_hit_http(
    stock_redis: Any,
) -> None:
    await seed(stock_redis, [item()])
    entered = asyncio.Event()
    release = asyncio.Event()
    active = [0]
    peak = [0]
    calls = [0]

    async def handler(request: httpx.Request) -> httpx.Response:
        calls[0] += 1
        active[0] += 1
        peak[0] = max(peak[0], active[0])
        if active[0] == 2:
            entered.set()
        await release.wait()
        active[0] -= 1
        return httpx.Response(200, json={"item": item("A", 2)})

    clients = [client_with_transport(stock_redis, handler) for _ in range(3)]
    tasks = [
        asyncio.create_task(client.get_stock_bulk_fresh(["A"]))
        for client in clients[:2]
    ]
    await entered.wait()
    from src.llm.inventory_read import InventoryReadUnavailable

    with pytest.raises(InventoryReadUnavailable):
        await clients[2].get_stock_bulk_fresh(["A"])
    assert calls[0] == 2 and peak[0] == 2
    release.set()
    await asyncio.gather(*tasks)
    assert not await stock_redis.exists(
        "zoho:inventory:read_slot:0", "zoho:inventory:read_slot:1"
    )
    for client in clients:
        await client.close()
