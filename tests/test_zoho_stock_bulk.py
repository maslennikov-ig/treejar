"""Selected-only fresh reads, request budgets and quotation consumer acceptance."""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.core.config import settings
from src.llm.engine import QuotationItem, create_quotation
from src.llm.inventory_read import InventoryReadUnavailable
from tests.stock_sync_support import (
    client_with_transport,
    item,
    page,
    seed,
)
from tests.test_llm_quotation import _quotation_idempotency_context

pytestmark = pytest.mark.usefixtures("authorized_outbound_unit_path")


@pytest.mark.parametrize("bulk", [False, True])
async def test_deleted_id_remap_retires_old_discovery_quantity(
    stock_redis: Any, eligible: Any, monkeypatch: Any, bulk: bool
) -> None:
    await seed(stock_redis, [item("A", 10, item_id="old")])
    monkeypatch.setattr(settings, "zoho_stock_bulk_size", 2 if bulk else 0)
    paths = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path == "/items/old":
            return httpx.Response(404)
        if request.url.path == "/itemdetails":
            return httpx.Response(200, json={"items": []})
        row = item("A", 2, item_id="new")
        return httpx.Response(
            200, json=page([row]) if request.url.path == "/items" else {"item": row}
        )

    client = client_with_transport(stock_redis, handler)
    assert (await client.get_stock_bulk_fresh(["A"]))[0]["stock_on_hand"] == 2
    assert (await client.get_stock("A"))["stock_on_hand"] == 2
    assert paths == ["/itemdetails" if bulk else "/items/old", "/items", "/items/new"]
    assert (await client.stock_store.read())[0].items["old"]["status"] == "inactive"
    await client.close()


async def test_exact_unknown_alias_numeric_keeps_matching_contract(
    stock_redis: Any, eligible: Any
) -> None:
    await seed(
        stock_redis, [item("A", None, item_id="exact"), item("a", 2, item_id="alias")]
    )
    ids = []

    def handler(request: httpx.Request) -> httpx.Response:
        ids.append(request.url.params["item_ids"])
        return httpx.Response(200, json={"items": [item("a", 2, item_id="alias")]})

    client = client_with_transport(stock_redis, handler)
    assert (await client.get_stock_bulk_fresh(["A"]))[0]["item_id"] == "alias"
    assert ids == ["alias"]
    await client.close()


async def test_direct_inactive_item_is_unavailable(stock_redis: Any) -> None:
    client = client_with_transport(
        stock_redis,
        lambda request: httpx.Response(
            200, json={"item": item("A", 10, status="inactive")}
        ),
    )
    assert await client.get_item("id-A") is None
    await client.close()


async def test_quote_preserves_distinct_exact_skus_with_same_casefold() -> None:
    ctx, inventory, messaging = _quotation_idempotency_context()
    inventory.get_stock_bulk_fresh.return_value = [
        item("A", 5, item_id="first"),
        item("a", 5, item_id="second"),
    ]
    with (
        patch(
            "src.services.pdf.generator.generate_pdf", AsyncMock(return_value=b"pdf")
        ),
        patch("src.services.pdf.generator.render_quotation_html", return_value="html"),
    ):
        await create_quotation(
            ctx,
            [QuotationItem(sku="A", quantity=1), QuotationItem(sku="a", quantity=1)],
        )
    payload = inventory.create_sale_order.await_args.kwargs
    assert [row["item_id"] for row in payload["items"]] == ["first", "second"]
    assert messaging.send_media.await_count == 1


async def test_fresh_bulk_bypasses_both_caches_and_deduplicates_aliases(
    stock_redis: Any, eligible: Any
) -> None:
    await seed(stock_redis, [item("CH 240 V Black", 10, item_id="id-A")])
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(
            200, json={"code": 0, "items": [item("CH 240 V Black", 2, item_id="id-A")]}
        )

    client = client_with_transport(stock_redis, handler)
    # Prime the exact HTTP response cache with an old provider response.
    params = {"item_ids": "id-A", "organization_id": client.org_id}
    cache_key = client._read_cache_key("GET", "/itemdetails", params)
    client._read_cache[cache_key] = (
        time.monotonic(),
        httpx.Response(
            200, json={"items": [item("CH 240 V Black", 10, item_id="id-A")]}
        ),
    )
    assert (await client.get_stock("CH 240 V Black"))["stock_on_hand"] == 10
    rows = await client.get_stock_bulk_fresh(
        ["CH 240 V black", "СH 240 V Black", "CH 240 V black"]
    )
    assert [row["stock_on_hand"] for row in rows] == [2, 2]
    assert len(calls) == 1 and calls[0].url.path == "/itemdetails"
    assert calls[0].url.params["item_ids"] == "id-A"
    assert (await client.get_stock("CH 240 V Black"))["stock_on_hand"] == 2
    await client.close()


async def test_fresh_chunking_uses_measured_configuration(
    stock_redis: Any, eligible: Any
) -> None:
    rows = [item(str(i)) for i in range(5)]
    await seed(stock_redis, rows)
    chunks = []

    def handler(request: httpx.Request) -> httpx.Response:
        ids = request.url.params["item_ids"].split(",")
        chunks.append(ids)
        return httpx.Response(
            200, json={"items": [row for row in rows if row["item_id"] in ids]}
        )

    client = client_with_transport(stock_redis, handler)
    assert len(await client.get_stock_bulk_fresh([str(i) for i in range(5)])) == 5
    assert [len(chunk) for chunk in chunks] == [2, 2, 1]
    await client.close()


async def test_unmeasured_bulk_uses_direct_selected_id_only(
    stock_redis: Any, monkeypatch: Any
) -> None:
    await seed(stock_redis, [item()])
    monkeypatch.setattr(settings, "zoho_stock_bulk_size", 0)
    monkeypatch.setattr(settings, "zoho_stock_bulk_evidence", "")
    paths = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        return httpx.Response(200, json={"item": item("A", 2)})

    client = client_with_transport(stock_redis, handler)
    assert (await client.get_stock_bulk_fresh(["A"]))[0]["stock_on_hand"] == 2
    assert paths == ["/items/id-A"]
    await client.close()


@pytest.mark.parametrize(
    "shape",
    [
        "missing",
        "wrong_id",
        "unknown",
        "inactive",
        "bool",
        "infinite",
        "ambiguous",
        "renamed",
    ],
)
async def test_incomplete_bulk_never_uses_cached_quantity(
    stock_redis: Any, eligible: Any, shape: str
) -> None:
    await seed(stock_redis)
    by_shape = {
        "missing": [],
        "wrong_id": [item("A", 2, item_id="wrong")],
        "unknown": [item("A", None)],
        "inactive": [item("A", 2, status="inactive")],
        "bool": [item("A", True)],
        "infinite": [item("A", "inf")],
        "ambiguous": [item("A", 2), item("A", 3)],
        "renamed": [item("CHANGED", 2, item_id="id-A")],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/items":
            return httpx.Response(200, json=page([]))
        return httpx.Response(200, json={"items": by_shape[shape]})

    client = client_with_transport(stock_redis, handler)
    with pytest.raises(InventoryReadUnavailable):
        await client.get_stock_bulk_fresh(["A", "B"])
    await client.close()


async def test_unknown_and_renamed_mapping_resolves_bounded_exact_sku(
    stock_redis: Any, eligible: Any
) -> None:
    await seed(stock_redis, [item("A", 10)])
    paths = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path == "/items":
            return httpx.Response(200, json=page([item("NEW", 4), item("NEWER", 90)]))
        return httpx.Response(200, json={"items": [item("NEW", 4)]})

    client = client_with_transport(stock_redis, handler)
    assert (await client.get_stock_bulk_fresh(["NEW"]))[0]["stock_on_hand"] == 4
    assert paths == ["/items", "/itemdetails"]
    state, _ = await client.stock_store.read()
    assert state.items["id-NEW"]["stock_on_hand"] == 4
    await client.close()


async def test_quote_shortfall_uses_fresh_2_instead_of_cached_10(
    stock_redis: Any, eligible: Any
) -> None:
    await seed(stock_redis, [item("CHAIR-1", 10)])
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        requests.append(request)
        return httpx.Response(200, json={"items": [item("CHAIR-1", 2)]})

    client = client_with_transport(stock_redis, handler)
    ctx, inventory, messaging = _quotation_idempotency_context()
    ctx.deps.zoho_inventory = client
    assert (await client.get_stock("CHAIR-1"))["stock_on_hand"] == 10
    with patch("src.llm.engine.resolve_inventory_customer_id", AsyncMock()) as customer:
        result = await create_quotation(ctx, [QuotationItem(sku="CHAIR-1", quantity=5)])
    assert "Only 2 in stock" in result
    assert len(requests) == 1
    assert ctx.deps.stock_snapshots["chair-1"].available == 2
    from src.llm.quotation_completion import quotation_readiness

    assert not quotation_readiness(ctx.deps).consent_granted
    # Automatic completion or the same-turn model cannot reuse old consent.
    assert (
        await create_quotation(ctx, [QuotationItem(sku="CHAIR-1", quantity=5)])
        == result
    )
    ctx.deps.source_message_id = "unrelated-next-turn"
    assert (
        await create_quotation(ctx, [QuotationItem(sku="CHAIR-1", quantity=5)])
        == result
    )
    assert len(requests) == 1
    customer.assert_not_awaited()
    messaging.send_media.assert_not_awaited()
    await client.close()


@pytest.mark.parametrize("available", [2, 8])
async def test_actual_background_retry_freshly_reads_and_handles_shortfall(
    stock_redis: Any, eligible: Any, available: int
) -> None:
    from src.services import quotation_retry
    from tests.test_quotation_retry import _ArqRedis, _pending, _session

    await seed(stock_redis, [item("CHAIR-1", 10)])
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={"items": [item("CHAIR-1", available)]})

    client = client_with_transport(stock_redis, handler)
    ctx, inventory, messaging = _quotation_idempotency_context()
    ctx.deps.quotation_created = False
    inventory.get_stock_bulk_fresh.side_effect = client.get_stock_bulk_fresh
    conversation = ctx.deps.conversation
    conversation.metadata_["pending_quotation"] = _pending(
        items=[{"sku": "CHAIR-1", "quantity": 5}]
    )
    send, alert = AsyncMock(), AsyncMock()
    with (
        patch(
            "src.core.database.async_session_factory", lambda: _session(conversation)
        ),
        patch.object(quotation_retry, "_build_deps", lambda *args: ctx.deps),
        patch.object(quotation_retry, "_send_confirmation", send),
        patch.object(quotation_retry, "alert_managers_for_conversation", alert),
        patch(
            "src.services.pdf.generator.generate_pdf", AsyncMock(return_value=b"pdf")
        ),
        patch("src.services.pdf.generator.render_quotation_html", return_value="html"),
    ):
        result = await quotation_retry.retry_pending_quotation(
            {"redis": _ArqRedis()}, conversation.id
        )
        again = await quotation_retry.retry_pending_quotation(
            {"redis": _ArqRedis()}, conversation.id
        )
    assert result == ("stock_shortfall" if available == 2 else "created")
    assert again == "nothing_pending"
    assert len(calls) == 1
    assert inventory.create_sale_order.await_count == (0 if available == 2 else 1)
    assert messaging.send_media.await_count == (0 if available == 2 else 1)
    send.assert_awaited_once()
    if available == 2:
        assert "Only 2 in stock" in send.await_args.args[1]
    alert.assert_not_awaited()
    await client.close()


async def test_no_consent_or_sent_quote_performs_no_critical_read(
    stock_redis: Any, eligible: Any
) -> None:
    ctx, inventory, messaging = _quotation_idempotency_context()
    workflow = ctx.deps.conversation.metadata_["order_runtime"]["quote_workflow"]
    workflow["consent"] = "not_requested"
    result = await create_quotation(ctx, [QuotationItem(sku="CHAIR-1", quantity=1)])
    assert "only after" in result
    inventory.get_stock_bulk_fresh.assert_not_awaited()
    inventory.create_sale_order.assert_not_awaited()
    workflow["consent"] = "granted"
    with (
        patch(
            "src.services.pdf.generator.generate_pdf", AsyncMock(return_value=b"pdf")
        ),
        patch("src.services.pdf.generator.render_quotation_html", return_value="html"),
    ):
        await create_quotation(ctx, [QuotationItem(sku="CHAIR-1", quantity=1)])
        ctx.deps.source_message_id = "second-message"
        await create_quotation(ctx, [QuotationItem(sku="CHAIR-1", quantity=1)])
    assert inventory.get_stock_bulk_fresh.await_count == 1
    assert inventory.create_sale_order.await_count == 1


async def test_429_then_retry_fresh_and_create_once(
    stock_redis: Any, eligible: Any
) -> None:
    await seed(stock_redis, [item("CHAIR-1", 10)])
    ctx, inventory, messaging = _quotation_idempotency_context()
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        requests.append(request)
        return (
            httpx.Response(429, headers={"Retry-After": "1800"})
            if len(requests) == 1
            else httpx.Response(200, json={"items": [item("CHAIR-1", 2)]})
        )

    client = client_with_transport(stock_redis, handler)
    inventory.get_stock_bulk_fresh.side_effect = client.get_stock_bulk_fresh
    with (
        patch(
            "src.llm.quotation_deferral.alert_managers_for_conversation",
            AsyncMock(return_value=False),
        ),
        patch(
            "src.services.pdf.generator.generate_pdf", AsyncMock(return_value=b"pdf")
        ),
        patch("src.services.pdf.generator.render_quotation_html", return_value="html"),
    ):
        first = await create_quotation(ctx, [QuotationItem(sku="CHAIR-1", quantity=1)])
        assert "has not been sent" in first
        assert ctx.deps.conversation.metadata_["pending_quotation"]["items"]
        inventory.create_sale_order.assert_not_awaited()
        messaging.send_media.assert_not_awaited()
        await stock_redis.delete(
            "zoho:inventory:rate_limited_until"
        )  # task-owned test DB only
        from src.integrations.inventory.zoho_inventory import reset_rate_limit_cooldown

        reset_rate_limit_cooldown()
        ctx.deps.source_message_id = "later"
        await create_quotation(ctx, [QuotationItem(sku="CHAIR-1", quantity=1)])
        await create_quotation(ctx, [QuotationItem(sku="CHAIR-1", quantity=1)])
    assert len(requests) == 2
    assert inventory.create_sale_order.await_count == 1
    assert messaging.send_media.await_count == 1
    await client.close()


@pytest.mark.parametrize(
    "extra_pages,fresh_quotes,expected", [(0, 0, 157), (1, 0, 589), (0, 10, 167)]
)
async def test_measured_simulated_24h_schedule(
    stock_redis: Any,
    eligible: Any,
    monkeypatch: Any,
    extra_pages: int,
    fresh_quotes: int,
    expected: int,
) -> None:
    base = int(time.time()) // 86400 * 86400 + 1
    monkeypatch.setattr(time, "time", lambda: base)
    await seed(stock_redis, [item("A")])
    count = 0
    operations = {"full": 0, "delta": 0, "fresh": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal count
        count += 1
        if request.url.path == "/itemdetails":
            operations["fresh"] += 1
            return httpx.Response(200, json={"items": [item("A", 2)]})
        delta = "last_modified_time" in request.url.params
        op = "delta" if delta else "full"
        operations[op] += 1
        number = int(request.url.params["page"])
        # Distinct full-page items ensure the measured 13 pages form a catalog.
        rows = (
            [item("A" if number == 1 else "B")]
            if delta
            else [item("A" if number == 1 else f"full-{number}")]
        )
        return httpx.Response(
            200, json=page(rows, number < (1 + extra_pages if delta else 13))
        )

    client = client_with_transport(stock_redis, handler)
    for step in range(144):
        monkeypatch.setattr(time, "time", lambda step=step: base + step * 600)
        assert await client.refresh_stock_snapshot(incremental=True)
        if step == 20:
            assert await client.refresh_stock_snapshot()
        for _ in range(3):
            assert (await client.get_stock("A"))["stock_on_hand"] == 10
    for _ in range(fresh_quotes):
        await client.get_stock_bulk_fresh(["A"])
    assert count == expected
    assert operations == {
        "full": 13,
        "delta": 144 * (1 + extra_pages) * (2 if extra_pages else 1),
        "fresh": fresh_quotes,
    }
    counters = await client.metrics.report(base, base + 86400)
    assert (
        sum(n for key, n in counters.items() if key.startswith("attempt|")) == expected
    )
    assert counters["attempt|full|sent|initial"] == 13
    await client.close()
