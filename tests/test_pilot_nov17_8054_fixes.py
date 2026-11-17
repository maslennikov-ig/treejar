from __future__ import annotations

import datetime
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.dialogue.order_state import QuoteConsent
from src.llm.catalog_planning import _resolve_zoho_sku_map_by_item_id
from src.llm.engine import QuotationItem, _create_quotation
from src.llm.escalation_policy import (
    critical_escalation_decision,
    recorded_wholesale_quantity,
    wholesale_handoff_from_history,
    wholesale_quantity,
)
from src.services.quotation_retry import _pending_is_live, retry_pending_quotation


def test_table_item_colon_quantity_triggers_wholesale_handoff_without_price_false_positives() -> (
    None
):
    photo_table = (
        "[The customer sent a photo. The photo shows: The attachment is a "
        "spreadsheet-style table titled 'FURNITURES' with columns No, Description "
        "and TOTAL. It lists 17 items with quantities: 1. Reception Table: 2 "
        "2. Coffee Table: 6 3. Sofa: 5 4. Ergonomic chair: 97 5. Corner storage: 1 "
        "6. Office Work Desk: 13 7. Visitors chairs: 16 8. Storage Cabinets: 33 "
        "9. Workstations: 50 10. Waiting Chairs: 0 16. Benches for seating: 32 "
        "17. Chairs: 15]"
    )
    assert wholesale_quantity(photo_table) >= 97
    decision = critical_escalation_decision(customer_text=photo_table)
    assert decision.allowed is True
    assert decision.trigger == "wholesale_or_bulk_project"

    # Multi-line table where individual lines are <20 (13 + 16 = 29 >= 20)
    combined_table = "Office Work Desk: 13\nVisitors chairs: 16"
    assert wholesale_quantity(combined_table) == 29

    # Guard against prices, ranges, and dimensions
    assert wholesale_quantity("Chairs: 350 AED") == 0
    assert wholesale_quantity("Chairs: 300-450") == 0
    assert wholesale_quantity("Table: 1600x800") == 0
    assert wholesale_quantity("Desk: 120 cm") == 0


def test_model_recorded_selected_items_trigger_wholesale_handoff() -> None:
    metadata = {
        "dialogue_state": {
            "slots": {
                "selected_items": [
                    {"sku": "CH 616 NEW black", "quantity": 12},
                    {"sku": "STEL SSC - 15", "quantity": 10},
                ]
            }
        }
    }
    assert recorded_wholesale_quantity(metadata) == 22
    decision = wholesale_handoff_from_history(
        "Please send quotation",
        (),
        conversation_metadata=metadata,
    )
    assert decision.allowed is True
    assert decision.trigger == "wholesale_or_bulk_project"
    assert "22 units" in decision.reason

    crit = critical_escalation_decision(
        customer_text="Please send quotation",
        conversation_metadata=metadata,
    )
    assert crit.allowed is True
    assert crit.trigger == "wholesale_or_bulk_project"


@pytest.mark.asyncio
async def test_resolve_zoho_sku_map_bridges_renamed_zoho_sku_via_item_id() -> None:
    fake_state = SimpleNamespace(
        items={
            "378603000019974638": {
                "item_id": "378603000019974638",
                "sku": "STEL SSL-15",
                "status": "active",
                "stock_on_hand": 8.0,
            }
        }
    )
    stock_store = SimpleNamespace(read=AsyncMock(return_value=(fake_state, {})))
    zoho_inventory = SimpleNamespace(stock_store=stock_store)

    mapped = await _resolve_zoho_sku_map_by_item_id(
        zoho_inventory,
        {"STEL SSC - 15": "378603000019974638", "CH 616 NEW black": None},
    )
    assert mapped == {"STEL SSC - 15": "STEL SSL-15"}


@pytest.mark.asyncio
async def test_create_quotation_routes_20_plus_units_to_b2b_manager_instead_of_pdf() -> (
    None
):
    conv = SimpleNamespace(
        id=uuid.uuid4(),
        phone="971558798054",
        language="en",
        escalation_status="none",
        metadata_={
            "pending_quotation": {
                "status": "pending",
                "items": [{"sku": "X", "quantity": 25}],
            }
        },
    )
    deps = SimpleNamespace(
        conversation=conv,
        db=AsyncMock(),
        recent_history=["user: Kindly send quotation"],
        zoho_inventory=SimpleNamespace(get_stock_bulk_fresh=AsyncMock()),
        customer_write_gate_resolved=True,
    )
    ctx = SimpleNamespace(deps=deps)

    with (
        patch("src.llm.engine.require_resolved_customer_writes"),
        patch(
            "src.integrations.notifications.escalation.notify_manager_escalation",
            new_callable=AsyncMock,
        ) as mock_notify,
    ):
        msg = await _create_quotation(
            ctx,  # type: ignore[arg-type]
            [
                QuotationItem(sku="CH 616 NEW black", quantity=97),
                QuotationItem(sku="STEL SSC - 15", quantity=33),
            ],
        )

    assert "wholesale project pricing" in msg
    assert "pending_quotation" not in conv.metadata_
    assert "wholesale_handoff_notified_at" in conv.metadata_
    mock_notify.assert_awaited_once()
    deps.zoho_inventory.get_stock_bulk_fresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_retry_pending_quotation_clears_and_stops_when_handed_to_manager() -> (
    None
):
    now_iso = datetime.datetime.now(datetime.UTC).isoformat()
    conv = SimpleNamespace(
        id=uuid.uuid4(),
        phone="971558798054",
        escalation_status="manual_takeover",
        metadata_={
            "quote_workflow": {
                "consent": QuoteConsent.GRANTED.value,
                "lifecycle": "creating",
            },
            "pending_quotation": {
                "version": 1,
                "status": "pending",
                "items": [{"sku": "CH 616 NEW black", "quantity": 5}],
                "first_deferred_at": now_iso,
                "deferred_at": now_iso,
            },
        },
    )
    assert _pending_is_live(conv, conv.metadata_["pending_quotation"]) is False

    fake_db = MagicMock()
    fake_db.get = AsyncMock(return_value=conv)
    fake_db.commit = AsyncMock()
    fake_cm = AsyncMock()
    fake_cm.__aenter__.return_value = fake_db
    fake_cm.__aexit__.return_value = False

    with patch("src.core.database.async_session_factory", return_value=fake_cm):
        outcome = await retry_pending_quotation({"redis": AsyncMock()}, str(conv.id), 4)

    assert outcome == "handed_to_manager"
    assert "pending_quotation" not in conv.metadata_
    fake_db.commit.assert_awaited_once()
