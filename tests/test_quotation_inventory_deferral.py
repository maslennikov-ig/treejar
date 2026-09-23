"""A Zoho rate limit defers a quotation instead of failing the turn (tj-uz6j.9).

Production 2026-09-23 16:20 UTC (conv fa224cab): create_contact answered 400
(name exists), the duplicate-name fallback hit 429 for every name, a retry of
create_quotation raised HTTPStatusError out of the tool, and the customer got
"I apologize, but I am experiencing a temporary issue".
"""

from __future__ import annotations

import datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import FunctionModel

from src.integrations.inventory.zoho_inventory import ZohoRateLimitError
from src.llm import engine
from src.llm.engine import QuotationItem, SalesDeps, create_quotation
from src.llm.inventory_customers import (
    KNOWN_INVENTORY_CUSTOMER_KEY,
    resolve_inventory_customer_id,
)
from src.llm.quotation_deferral import (
    PENDING_QUOTATION_KEY,
    pending_quotation_directive,
)

pytestmark = pytest.mark.usefixtures("authorized_outbound_unit_path")

_SKU = "OF-HAI-Luma-Workstation-RJ 9719-4-Walnut"
_PHONE = "+79689818825"


def _rate_limit(method: str = "GET") -> ZohoRateLimitError:
    request = httpx.Request(method, "https://www.zohoapis.eu/inventory/v1/contacts")
    response = httpx.Response(429, request=request)
    return ZohoRateLimitError(
        "429 Too Many Requests",
        request=request,
        response=response,
        retry_after_seconds=None,
    )


def _duplicate_name() -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://www.zohoapis.eu/inventory/v1/contacts")
    response = httpx.Response(
        400,
        json={"code": 3062, "message": 'The customer "AIDevTeam" already exists.'},
        request=request,
    )
    return httpx.HTTPStatusError("duplicate", request=request, response=response)


class _Redis:
    def __init__(self) -> None:
        self.values: dict[str, Any] = {}

    async def get(self, key: str) -> Any:
        return self.values.get(key)

    async def set(self, key: str, value: Any, ex: Any = None) -> None:
        self.values[key] = value


def _metadata(**extra: Any) -> dict[str, Any]:
    return {
        "quote_customer_details": {
            "name": "Nadia",
            "company": "AIDevTeam",
            "email": "nadia@example.com",
            "phone": _PHONE,
            "address": "Office 12, Business Bay, Dubai",
        },
        "order_runtime": {
            "quote_workflow": {
                "version": 2,
                "consent": "granted",
                "lifecycle": "quote_requested",
            }
        },
        **extra,
    }


def _ctx(inventory: AsyncMock, *, source_message_id: str = "wa-msg-1") -> MagicMock:
    conversation = SimpleNamespace(
        id="fa224cab-0000-0000-0000-000000000000",
        phone=_PHONE,
        customer_name="Nadia",
        language="en",
        escalation_status="none",
        metadata_=_metadata(),
    )
    db = AsyncMock()
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = None
    db.execute.return_value = execute_result
    deps = MagicMock(spec=SalesDeps)
    deps.zoho_inventory = inventory
    deps.messaging_client = AsyncMock()
    deps.conversation = conversation
    deps.crm_context = None
    deps.redis = _Redis()
    deps.db = db
    deps.zoho_crm = None
    deps.source_message_id = source_message_id
    deps.quotation_created = False
    deps.recent_history = []
    ctx = MagicMock(spec=RunContext)
    ctx.deps = deps
    return ctx


def _inventory_with_item() -> AsyncMock:
    inventory = AsyncMock()
    inventory.get_stock_bulk.return_value = [
        {
            "sku": _SKU,
            "item_id": "item-1",
            "rate": 1200.0,
            "stock_on_hand": 5,
            "name": "Luma Workstation",
            "description": "",
        }
    ]
    return inventory


def _incident_inventory() -> AsyncMock:
    inventory = _inventory_with_item()
    inventory.find_customer_by_phone.return_value = None
    inventory.find_customer_by_email.return_value = None
    inventory.create_contact.side_effect = _duplicate_name()
    inventory.find_inactive_customer_by_email.return_value = None
    inventory.find_customer_by_name.side_effect = _rate_limit()
    return inventory


@pytest.fixture
def manager_alert() -> Any:
    with (
        patch(
            "src.services.inbound_channels."
            "should_send_manager_alert_for_conversation_with_db",
            AsyncMock(return_value=True),
        ),
        patch(
            "src.services.notifications.send_telegram_message",
            AsyncMock(return_value=True),
        ) as send,
        patch(
            "src.integrations.notifications.escalation.notify_manager_escalation",
            AsyncMock(),
        ) as escalation,
    ):
        yield SimpleNamespace(send=send, escalation=escalation)


# --- customer resolution -------------------------------------------------------


@pytest.mark.asyncio
async def test_rate_limit_in_duplicate_name_fallback_stops_the_scan_and_propagates() -> (
    None
):
    inventory = _incident_inventory()
    with pytest.raises(ZohoRateLimitError):
        await resolve_inventory_customer_id(
            phone=_PHONE,
            customer_name="Nadia",
            customer_email="nadia@example.com",
            customer_company="AIDevTeam",
            zoho_inventory=inventory,
        )
    # "AIDevTeam" was tried once; "Nadia" was never paged against the limit.
    inventory.find_customer_by_name.assert_awaited_once_with("AIDevTeam")


@pytest.mark.asyncio
async def test_rate_limit_on_phone_lookup_is_not_folded_into_no_customer() -> None:
    inventory = AsyncMock()
    inventory.find_customer_by_phone.side_effect = _rate_limit()
    with pytest.raises(ZohoRateLimitError):
        await resolve_inventory_customer_id(
            phone=_PHONE,
            customer_name="Nadia",
            customer_email="",
            customer_company="AIDevTeam",
            zoho_inventory=inventory,
        )
    inventory.create_contact.assert_not_awaited()


@pytest.mark.asyncio
async def test_returning_customer_reuses_the_remembered_contact() -> None:
    conversation = SimpleNamespace(
        metadata_={
            KNOWN_INVENTORY_CUSTOMER_KEY: {
                "contact_id": "contact-77",
                "phone_digits": "79689818825",
            }
        }
    )
    inventory = AsyncMock()
    inventory.get_contact.return_value = {
        "contact_id": "contact-77",
        "contact_type": "customer",
        "status": "active",
        "contact_persons": [{"phone": _PHONE, "mobile": _PHONE}],
    }
    result = await resolve_inventory_customer_id(
        phone=_PHONE,
        customer_name="Nadia",
        customer_email="nadia@example.com",
        customer_company="AIDevTeam",
        zoho_inventory=inventory,
        conversation=conversation,  # type: ignore[arg-type]
    )
    assert result == "contact-77"
    inventory.get_contact.assert_awaited_once_with("contact-77")
    inventory.find_customer_by_phone.assert_not_awaited()
    inventory.create_contact.assert_not_awaited()
    inventory.find_customer_by_name.assert_not_awaited()


@pytest.mark.asyncio
async def test_resolved_contact_is_remembered_per_phone_across_conversations() -> None:
    redis = _Redis()
    first = SimpleNamespace(metadata_={})
    inventory = AsyncMock()
    inventory.find_customer_by_phone.return_value = {
        "contact_id": "contact-9",
        "contact_type": "customer",
        "status": "active",
    }
    assert (
        await resolve_inventory_customer_id(
            phone=f"{_PHONE}#synthetic-suffix",
            customer_name="Nadia",
            customer_email="",
            customer_company="",
            zoho_inventory=inventory,
            conversation=first,  # type: ignore[arg-type]
            redis=redis,
        )
        == "contact-9"
    )
    assert first.metadata_[KNOWN_INVENTORY_CUSTOMER_KEY]["contact_id"] == "contact-9"

    # A later conversation for the same phone starts with empty metadata.
    later_inventory = AsyncMock()
    later_inventory.get_contact.return_value = {
        "contact_id": "contact-9",
        "contact_type": "customer",
        "status": "active",
    }
    assert (
        await resolve_inventory_customer_id(
            phone=_PHONE,
            customer_name="Nadia",
            customer_email="",
            customer_company="",
            zoho_inventory=later_inventory,
            conversation=SimpleNamespace(metadata_={}),  # type: ignore[arg-type]
            redis=redis,
        )
        == "contact-9"
    )
    later_inventory.find_customer_by_phone.assert_not_awaited()


@pytest.mark.asyncio
async def test_remembered_contact_now_on_another_phone_is_not_reused() -> None:
    conversation = SimpleNamespace(
        metadata_={
            KNOWN_INVENTORY_CUSTOMER_KEY: {
                "contact_id": "contact-77",
                "phone_digits": "79689818825",
            }
        }
    )
    inventory = AsyncMock()
    inventory.get_contact.return_value = {
        "contact_id": "contact-77",
        "contact_type": "customer",
        "status": "active",
        "contact_persons": [{"phone": "+971500000000"}],
    }
    inventory.find_customer_by_phone.return_value = {
        "contact_id": "contact-new",
        "contact_type": "customer",
        "status": "active",
    }
    result = await resolve_inventory_customer_id(
        phone=_PHONE,
        customer_name="Nadia",
        customer_email="",
        customer_company="",
        zoho_inventory=inventory,
        conversation=conversation,  # type: ignore[arg-type]
    )
    assert result == "contact-new"
    assert conversation.metadata_[KNOWN_INVENTORY_CUSTOMER_KEY]["contact_id"] == (
        "contact-new"
    )


# --- create_quotation --------------------------------------------------------------


@pytest.mark.asyncio
async def test_incident_chain_defers_the_quote_with_an_honest_status(
    manager_alert: Any,
) -> None:
    inventory = _incident_inventory()
    ctx = _ctx(inventory)

    result = await create_quotation(ctx, [QuotationItem(sku=_SKU, quantity=3)])

    assert "has not been sent yet" in result
    assert "manager has been notified" in result
    assert "temporary issue" not in result
    inventory.create_sale_order.assert_not_awaited()
    ctx.deps.messaging_client.send_media.assert_not_awaited()
    manager_alert.escalation.assert_not_awaited()  # the bot is not paused
    manager_alert.send.assert_awaited_once()
    alert_text = manager_alert.send.await_args.args[0]
    assert _SKU in alert_text and "fa224cab" in alert_text
    pending = ctx.deps.conversation.metadata_[PENDING_QUOTATION_KEY]
    assert pending["status"] == "pending"
    assert pending["items"] == [{"sku": _SKU, "quantity": 3}]
    assert pending["reason"] == "inventory_rate_limited"
    assert pending["manager_notified"] is True
    assert ctx.deps.quotation_created is False


@pytest.mark.asyncio
async def test_same_turn_retry_makes_no_further_zoho_calls(manager_alert: Any) -> None:
    inventory = _inventory_with_item()
    inventory.get_stock_bulk.side_effect = _rate_limit()
    ctx = _ctx(inventory)
    items = [QuotationItem(sku=_SKU, quantity=3)]

    first = await create_quotation(ctx, items)
    second = await create_quotation(ctx, items)

    assert first == second
    assert inventory.get_stock_bulk.await_count == 1
    manager_alert.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_sale_order_429_defers_instead_of_critical_escalation(
    manager_alert: Any,
) -> None:
    inventory = _inventory_with_item()
    inventory.find_customer_by_phone.return_value = {
        "contact_id": "contact-1",
        "contact_type": "customer",
        "status": "active",
    }
    inventory.create_sale_order.side_effect = _rate_limit("POST")
    ctx = _ctx(inventory)

    result = await create_quotation(ctx, [QuotationItem(sku=_SKU, quantity=3)])

    assert "has not been sent yet" in result
    manager_alert.escalation.assert_not_awaited()
    assert ctx.deps.conversation.metadata_[PENDING_QUOTATION_KEY]["items"] == [
        {"sku": _SKU, "quantity": 3}
    ]


@pytest.mark.asyncio
async def test_unalerted_deferral_does_not_claim_a_manager_was_told(
    manager_alert: Any,
) -> None:
    manager_alert.send.return_value = False
    inventory = _inventory_with_item()
    inventory.get_stock_bulk.side_effect = _rate_limit()
    ctx = _ctx(inventory)

    result = await create_quotation(ctx, [QuotationItem(sku=_SKU, quantity=3)])

    assert "manager" not in result.casefold()
    assert "has not been sent yet" in result


@pytest.mark.asyncio
async def test_non_transient_failures_still_raise() -> None:
    inventory = _inventory_with_item()
    inventory.get_stock_bulk.side_effect = RuntimeError("bug")
    with pytest.raises(RuntimeError):
        await create_quotation(_ctx(inventory), [QuotationItem(sku=_SKU, quantity=1)])


@pytest.mark.asyncio
async def test_next_turn_is_told_to_finish_and_success_clears_the_pending_quote(
    manager_alert: Any,
) -> None:
    inventory = _inventory_with_item()
    inventory.get_stock_bulk.side_effect = _rate_limit()
    ctx = _ctx(inventory)
    items = [QuotationItem(sku=_SKU, quantity=3)]
    await create_quotation(ctx, items)

    # Same inbound message: no directive, the deferral already answered it.
    assert pending_quotation_directive(ctx.deps) is None
    ctx.deps.source_message_id = "wa-msg-2"
    directive = pending_quotation_directive(ctx.deps)
    assert directive is not None
    assert f"{_SKU} x 3" in directive
    assert "call it with exactly these items" in directive

    async def _created(inner_ctx: Any, _items: Any) -> str:
        inner_ctx.deps.quotation_created = True
        return "Quotation SA-1 has been prepared and sent to you."

    with patch.object(engine, "_create_quotation", _created):
        result = await create_quotation(ctx, items)
    assert result.startswith("Quotation SA-1")
    assert PENDING_QUOTATION_KEY not in ctx.deps.conversation.metadata_
    assert pending_quotation_directive(ctx.deps) is None


@pytest.mark.asyncio
async def test_stale_or_declined_pending_quote_gives_no_directive() -> None:
    ctx = _ctx(AsyncMock(), source_message_id="wa-msg-9")
    old = (datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=8)).isoformat()
    ctx.deps.conversation.metadata_[PENDING_QUOTATION_KEY] = {
        "status": "pending",
        "items": [{"sku": _SKU, "quantity": 3}],
        "deferred_at": old,
        "source_message_id": "wa-msg-1",
    }
    assert pending_quotation_directive(ctx.deps) is None
    ctx.deps.conversation.metadata_[PENDING_QUOTATION_KEY]["deferred_at"] = (
        datetime.datetime.now(datetime.UTC).isoformat()
    )
    assert pending_quotation_directive(ctx.deps) is not None
    ctx.deps.conversation.metadata_["order_runtime"]["quote_workflow"]["consent"] = (
        "declined"
    )
    assert pending_quotation_directive(ctx.deps) is None


@pytest.mark.asyncio
async def test_agent_loop_gets_a_tool_result_not_a_generic_failure(
    manager_alert: Any,
) -> None:
    inventory = _incident_inventory()
    ctx = _ctx(inventory)

    def model(messages: Any, info: Any) -> ModelResponse:
        returns = [
            part
            for message in messages
            for part in message.parts
            if isinstance(part, ToolReturnPart)
        ]
        if not returns:
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        "create_quotation",
                        {"items": [{"sku": _SKU, "quantity": 3}]},
                    )
                ]
            )
        return ModelResponse(parts=[TextPart(str(returns[-1].content))])

    agent = Agent(
        FunctionModel(model), deps_type=SalesDeps, tools=[engine.create_quotation]
    )
    result = await agent.run("my email is nadia@example.com", deps=ctx.deps)

    assert "has not been sent yet" in result.output
    inventory.create_sale_order.assert_not_awaited()


# --- stock reads -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_stock_429_reports_the_catalog_listing_as_unconfirmed() -> None:
    ctx = _ctx(AsyncMock())
    ctx.deps.stock_snapshots = {}
    ctx.deps.zoho_inventory.get_stock.side_effect = _rate_limit()
    catalog_row = SimpleNamespace(zoho_item_id=None, stock=4, sku=_SKU)
    with patch.object(
        engine, "_find_catalog_product_by_sku", AsyncMock(return_value=catalog_row)
    ):
        result = await engine.get_stock(ctx, _SKU)
    assert result.return_value["status"] == "temporarily_unavailable"
    assert result.return_value["stock_confirmed"] is False
    assert result.return_value["catalog_listed"] is True
    assert result.return_value["stock_source"] == "catalog_unconfirmed"
    assert "not live-confirmed" in result.content
    assert ctx.deps.stock_snapshots == {}


@pytest.mark.asyncio
async def test_search_stock_check_429_falls_back_to_unconfirmed_catalog_stock() -> None:
    """search_products renders a None lookup as "Current stock: unconfirmed"."""
    from src.llm.catalog_planning import _zoho_stock_for_catalog_candidates

    deps = SimpleNamespace(zoho_inventory=AsyncMock())
    deps.zoho_inventory.get_stock_bulk.side_effect = _rate_limit()
    assert await _zoho_stock_for_catalog_candidates(deps, [_SKU]) is None  # type: ignore[arg-type]
