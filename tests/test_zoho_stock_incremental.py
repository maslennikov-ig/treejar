"""Paged hybrid synchronization and cache lifecycle, with real local Redis."""

from __future__ import annotations

import json
import time
from datetime import datetime
from typing import Any

import httpx
import pytest

from src.core.config import settings
from src.integrations.inventory.stock_state import LEGACY_KEY, STATE_KEY
from tests.stock_sync_support import (
    client_with_transport,
    item,
    page,
    seed,
)


@pytest.mark.parametrize("mutation", ["move", "delete"])
async def test_shifted_offset_pages_do_not_advance_coverage(
    stock_redis: Any, eligible: Any, mutation: str
) -> None:
    await seed(stock_redis)
    before = await stock_redis.get(STATE_KEY)
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        number = int(request.url.params["page"])
        if len(calls) == 1:
            rows = [item(str(i), i) for i in range(1, 201)]
        elif mutation == "move":
            rows = [item(str(i), i) for i in range(202, 401)] + [item("1", 1)]
        elif len(calls) == 2:
            rows = [item(str(i), i) for i in range(202, 401)]
        else:
            rows = (
                [item(str(i), i) for i in range(2, 202)]
                if number == 1
                else [item(str(i), i) for i in range(202, 401)]
            )
        return httpx.Response(200, json=page(rows, number == 1))

    client = client_with_transport(stock_redis, handler)
    assert await client.refresh_stock_snapshot(incremental=True) is None
    assert await stock_redis.get(STATE_KEY) == before
    assert len(calls) == (2 if mutation == "move" else 4)
    await client.close()


async def test_delta_zero_empty_overlap_and_cycle_start(
    stock_redis: Any, eligible: Any, monkeypatch: Any
) -> None:
    old = await seed(stock_redis)
    queries = []
    started = time.time() + 5
    monkeypatch.setattr(time, "time", lambda: started)

    def handler(request: httpx.Request) -> httpx.Response:
        queries.append(dict(request.url.params))
        return httpx.Response(
            200, json=page([item("A", 0), item("A", 0)] if len(queries) == 1 else [])
        )

    client = client_with_transport(stock_redis, handler)
    assert await client.refresh_stock_snapshot(incremental=True)
    first, raw = await client.stock_store.read()
    assert first.coverage == started
    assert first.items["id-A"]["stock_on_hand"] == 0
    assert first.items["id-B"]["stock_on_hand"] == 5
    assert first.observed["id-B"] == old.observed["id-B"]
    assert (
        datetime.fromisoformat(
            queries[0]["last_modified_time"].replace("Z", "+00:00")
        ).timestamp()
        <= old.coverage - 120
    )
    assert "status" not in queries[0]
    assert queries[0]["sort_column"] == "last_modified_time"
    assert await client.refresh_stock_snapshot(incremental=True)
    second, _ = await client.stock_store.read()
    assert second.items == first.items
    assert second.observed == first.observed
    await client.close()


@pytest.mark.parametrize(
    "failure",
    [
        "http",
        "missing_items",
        "missing_context",
        "false_context",
        "bad_row",
        "error_code",
        "cap",
    ],
)
async def test_failed_page_keeps_exact_generation_and_cursor(
    stock_redis: Any, eligible: Any, monkeypatch: Any, failure: str
) -> None:
    await seed(stock_redis)
    before = await stock_redis.get(STATE_KEY)
    monkeypatch.setattr(
        "src.integrations.inventory.zoho_inventory.STOCK_SNAPSHOT_MAX_PAGES", 2
    )

    def handler(request: httpx.Request) -> httpx.Response:
        number = int(request.url.params["page"])
        if number == 1:
            return httpx.Response(200, json=page([item("A", 0)], True))
        malformed = {
            "missing_items": {"page_context": {"has_more_page": False}},
            "missing_context": {"items": []},
            "false_context": {"items": [], "page_context": {"has_more_page": "false"}},
            "bad_row": page([{"sku": "B"}]),
            "error_code": page([], code=44),
            "cap": page([], True),
        }
        return httpx.Response(
            400 if failure == "http" else 200, json=malformed.get(failure, {})
        )

    client = client_with_transport(stock_redis, handler)
    assert await client.refresh_stock_snapshot(incremental=True) is None
    assert await stock_redis.get(STATE_KEY) == before
    assert (
        await client.refresh_stock_snapshot(incremental=True) is None
    )  # restart repeats same boundary
    assert await stock_redis.get(STATE_KEY) == before
    await client.close()


async def test_changes_during_paging_equal_timestamps_and_restart(
    stock_redis: Any, eligible: Any, monkeypatch: Any
) -> None:
    await seed(stock_redis)
    clock = [time.time() + 5]
    monkeypatch.setattr(time, "time", lambda: clock[0])
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(dict(request.url.params))
        number = int(request.url.params["page"])
        if len(calls) <= 4:
            clock[0] += 30
            return httpx.Response(
                200,
                json=page(
                    [
                        item(
                            "A" if number == 1 else "B",
                            number,
                            last_modified_time="2026-10-03T10:00:00Z",
                        )
                    ],
                    number == 1,
                ),
            )
        return httpx.Response(200, json=page([item("A", 9)]))

    client = client_with_transport(stock_redis, handler)
    started = clock[0]
    assert await client.refresh_stock_snapshot(incremental=True)
    state, _ = await client.stock_store.read()
    assert state.coverage == started  # not end of page 2
    await client.close()
    restarted = client_with_transport(stock_redis, handler)
    assert await restarted.refresh_stock_snapshot(incremental=True)
    assert (
        datetime.fromisoformat(
            calls[-1]["last_modified_time"].replace("Z", "+00:00")
        ).timestamp()
        <= started - 120
    )
    assert (await restarted.stock_store.read())[0].items["id-A"]["stock_on_hand"] == 9
    await restarted.close()


@pytest.mark.parametrize(
    "operation",
    ["fulfillment", "receipt", "adjustment", "return", "transfer", "creation", "edit"],
)
async def test_stock_operation_shapes_are_local_evidence_only(
    stock_redis: Any, eligible: Any, operation: str
) -> None:
    await seed(stock_redis)
    row = item("NEW" if operation == "creation" else "A", 7)
    client = client_with_transport(
        stock_redis, lambda request: httpx.Response(200, json=page([row]))
    )
    assert await client.refresh_stock_snapshot(incremental=True)
    state, _ = await client.stock_store.read()
    assert state.items[row["item_id"]]["stock_on_hand"] == 7
    await client.close()


async def test_rename_deactivate_remove_and_unknown_do_not_resurrect(
    stock_redis: Any, eligible: Any
) -> None:
    await seed(stock_redis)
    rows = [
        item("RENAMED", 3, item_id="id-A"),
        item("B", None, status="inactive"),
        item("NEW", None),
    ]
    client = client_with_transport(
        stock_redis, lambda request: httpx.Response(200, json=page(rows))
    )
    snapshot = await client.refresh_stock_snapshot(incremental=True)
    assert snapshot.lookup("A") is None
    assert snapshot.lookup("B") is None
    assert snapshot.lookup("RENAMED")["stock_on_hand"] == 3
    assert snapshot.lookup("NEW")["stock_on_hand"] is None
    client.client = httpx.AsyncClient(
        base_url="https://inventory.invalid",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=page([item("NEW", 0)]))
        ),
    )
    assert await client.refresh_stock_snapshot()
    state, _ = await client.stock_store.read()
    assert set(state.items) == {"id-NEW"}
    assert state.items["id-NEW"]["stock_on_hand"] == 0
    assert await stock_redis.ttl(STATE_KEY) >= 172790
    await client.close()


async def test_retained_idle_rows_coverage_and_degraded_hour_ceiling(
    stock_redis: Any, eligible: Any, monkeypatch: Any
) -> None:
    at = time.time()
    monkeypatch.setattr(time, "time", lambda: at)
    await seed(stock_redis)
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(dict(request.url.params))
        return httpx.Response(
            200,
            json=(
                page([])
                if "last_modified_time" in request.url.params
                else page([item("A", 10), item("B", 5)])
            )
            if "page" in request.url.params
            else {"items": [item("A", 2)]},
        )

    client = client_with_transport(stock_redis, handler)
    # More than 24h of synthetic coverage: daily full remains represented;
    # idle records are retained, while deltas validate unchanged coverage.
    for seconds in range(600, 25 * 3600, 600):
        monkeypatch.setattr(time, "time", lambda seconds=seconds: at + seconds)
        assert await client.refresh_stock_snapshot(incremental=True)
    current, _ = await client.stock_store.read()
    assert current.items["id-A"]["stock_on_hand"] == 10
    assert current.observed["id-A"] == at + 86400
    assert (await client.get_stock("A"))["stock_on_hand"] == 10
    count = len(calls)
    monkeypatch.setattr(time, "time", lambda: at + 26 * 3600)
    assert (await client.get_stock("A"))["stock_on_hand"] == 2
    assert len(calls) == count + 1
    assert "page" not in calls[-1]  # bounded direct read, no full catalog
    await client.close()


@pytest.mark.parametrize("legacy", ["valid", "corrupt", "missing", "cursor_missing"])
async def test_migration_rollback_and_missing_cursor_bootstrap(
    stock_redis: Any, eligible: Any, monkeypatch: Any, legacy: str
) -> None:
    row = item("A", 4)
    if legacy == "valid":
        await stock_redis.set(
            LEGACY_KEY, json.dumps({"as_of": time.time(), "items": {"A": row}})
        )
    elif legacy == "corrupt":
        await stock_redis.set(STATE_KEY, "corrupt")
    elif legacy == "cursor_missing":
        old = await seed(stock_redis)
        old.coverage = None
        await stock_redis.set(STATE_KEY, old.to_json())
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(dict(request.url.params))
        return httpx.Response(200, json=page([row]))

    client = client_with_transport(stock_redis, handler)
    assert await client.refresh_stock_snapshot(incremental=True)
    assert "last_modified_time" not in calls[0]
    monkeypatch.setattr(settings, "zoho_stock_incremental_enabled", False)
    assert (await client.get_stock("A"))["stock_on_hand"] == 4
    # Older release reads the retained last-full v1 baseline.
    assert (
        json.loads(await stock_redis.get(LEGACY_KEY))["items"]["A"]["stock_on_hand"]
        == 4
    )
    await client.close()


async def test_gate_closed_startup_and_customer_bursts(
    stock_redis: Any, monkeypatch: Any
) -> None:
    monkeypatch.setattr(settings, "zoho_stock_incremental_enabled", True)
    monkeypatch.setattr(settings, "zoho_stock_coverage_evidence", "")
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(dict(request.url.params))
        return httpx.Response(200, json=page([item()]))

    client = client_with_transport(stock_redis, handler)
    assert not client.incremental_eligible()
    assert await client.refresh_stock_snapshot(incremental=True, startup=True)
    assert await client.refresh_stock_snapshot(incremental=True, startup=True) is None
    assert len(calls) == 1 and "last_modified_time" not in calls[0]
    for _ in range(100):
        assert (await client.get_stock("A"))["stock_on_hand"] == 10
    assert len(calls) == 1
    await client.close()


async def test_restart_with_retained_usable_state_does_not_download_full(
    stock_redis: Any, eligible: Any
) -> None:
    await seed(stock_redis, age=900)
    client = client_with_transport(
        stock_redis,
        lambda request: pytest.fail("Restart must leave recovery to scheduled jobs"),
    )
    assert await client.refresh_stock_snapshot(incremental=True, startup=True) is None
    assert await client.refresh_stock_snapshot(startup=True) is None
    await client.close()


@pytest.mark.parametrize("restore", [False, True])
def test_hybrid_schedule_registration_and_utc_slot(
    eligible: Any, monkeypatch: Any, restore: bool
) -> None:
    from src.worker import (
        WorkerSettings,
        build_worker_cron_jobs,
        build_worker_functions,
    )

    monkeypatch.setattr(settings, "test_channel_restore_mode", restore)
    crons = {job.coroutine.__name__: job for job in build_worker_cron_jobs()}
    delta, full = (
        crons["refresh_zoho_stock_delta"],
        crons["refresh_zoho_stock_snapshot"],
    )
    assert delta.minute == {1, 11, 21, 31, 41, 51}
    assert full.hour == {3} and full.minute == {17}
    assert not delta.run_at_startup and not full.run_at_startup
    assert WorkerSettings.timezone.utcoffset(None).total_seconds() == 0
    names = {
        getattr(function, "name", function.__name__ if callable(function) else "")
        for function in build_worker_functions()
    }
    assert {"refresh_zoho_stock_delta", "refresh_zoho_stock_snapshot"} <= names


@pytest.mark.parametrize("restore", [False, True])
async def test_worker_repeated_start_is_controlled(
    stock_redis: Any, eligible: Any, monkeypatch: Any, restore: bool
) -> None:
    from unittest.mock import AsyncMock, patch

    from src.worker import startup

    monkeypatch.setattr(settings, "test_channel_restore_mode", restore)
    monkeypatch.setattr(settings, "zoho_inventory_org_id", "synthetic-org")
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json=page([item()]), request=request)

    with (
        patch(
            "httpx.AsyncClient.request",
            AsyncMock(
                side_effect=lambda **kwargs: handler(
                    httpx.Request(
                        kwargs["method"],
                        "https://inventory.invalid/items",
                        params=kwargs["params"],
                    )
                )
            ),
        ),
        patch("src.worker.EmbeddingEngine.warmup_async", AsyncMock()),
    ):
        await startup({"redis": stock_redis})
        await startup({"redis": stock_redis})
    assert len(calls) == 1 and "last_modified_time" not in calls[0].url.params
