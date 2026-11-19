"""Regression tests for tj-uxo1 (Nov 19 16:00 MSK pilot audit: *7829 and *3210)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic_ai import RunContext, ToolReturn
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage

import src.llm.engine as engine_module
from src.llm.catalog_planning import (
    SalesDeps,
    _has_footprint_dimension_evidence,
    product_matches_concept,
    rank_products_for_request,
    requested_catalog_concepts,
)
from src.llm.escalation_policy import (
    b2b_handoff_buckets,
    critical_escalation_decision,
    wholesale_handoff_from_history,
    wholesale_quantity,
)
from src.llm.prompts import BASE_SYSTEM_PROMPT
from src.models.conversation import Conversation
from src.schemas.common import SalesStage
from src.schemas.product import ProductRead, ProductSearchResult
from src.services import canonical_admin_seed as seed


def _product(
    sku: str,
    name: str,
    *,
    category: str = "Storage",
    subcategory: str | None = "Cabinet",
    description: str = "",
    price: float = 300.0,
    stock: int = 10,
    attributes: dict | None = None,
) -> ProductRead:
    return ProductRead(
        id=uuid.uuid4(),
        sku=sku,
        name_en=name,
        description_en=description,
        category=category,
        subcategory=subcategory,
        price=price,
        currency="AED",
        stock=stock,
        attributes=attributes,
        is_active=True,
        created_at=datetime.now(UTC),
    )


def _deps(user_query: str) -> SalesDeps:
    db = AsyncMock()
    conv = Conversation(
        id=uuid.uuid4(),
        phone="12345",
        customer_name="Test User",
        sales_stage=SalesStage.SOLUTION.value,
        language="en",
        escalation_status="none",
    )
    db.get.return_value = conv
    empty = MagicMock()
    empty.scalars.return_value.all.return_value = []
    empty.scalar_one_or_none.return_value = None
    db.execute.return_value = empty
    redis = AsyncMock()
    redis.get.return_value = None
    zoho = AsyncMock()
    zoho.get_stock_bulk.return_value = []
    return SalesDeps(
        db=db,
        conversation=conv,
        embedding_engine=AsyncMock(),
        zoho_inventory=zoho,
        zoho_crm=AsyncMock(),
        messaging_client=AsyncMock(),
        pii_map={},
        redis=redis,
        user_query=user_query,
    )


def _ctx(deps: SalesDeps) -> RunContext[SalesDeps]:
    return RunContext(
        deps=deps,
        retry=0,
        messages=[],
        prompt=deps.user_query,
        model=TestModel(),
        usage=RunUsage(),
    )


def test_vision_boq_label_below_20_units_never_triggers_wholesale_handoff() -> None:
    """Reproduces *7829: vision commentary 'most likely a bill of quantities' on 15 signage items."""
    text = (
        "Hi. I am interested in purchasing office furniture. Could you assist me?\n"
        "[The customer sent a photo. The photo shows: The attachment is a table, "
        "most likely a bill of quantities or order list for signage, with four columns: "
        "Location, Items, Size, and QTY. Rows as shown: - Sonapur: Notice board with "
        "glass door, 170 *150 cm, qty 1; Notice board with glass door, 100*60 cm, qty 6; "
        "EGIS signage board, 300*100 cm, qty 1. - Al qouz: Notice board with Glass door, "
        "120*80 cm, qty 4. - Abu dhabi: Notice board with glass door, 100*60 cm, qty 2. "
        "Total: 14 notice boards with glass doors and 1 EGIS signage board across three locations.]"
    )
    assert wholesale_quantity(text) == 14
    assert b2b_handoff_buckets(text) == ()
    assert critical_escalation_decision(customer_text=text).allowed is False
    assert wholesale_handoff_from_history(text, ()).allowed is False


def test_customer_boq_and_20_plus_qty_rows_still_escalate_without_subthreshold_count() -> (
    None
):
    """Explicit customer BOQ/wholesale or >=20 summed qty rows still trigger handoff cleanly."""
    customer_boq = "Please quote our BOQ for 6 ergonomic chairs."
    decision = wholesale_handoff_from_history(customer_boq, ())
    assert decision.allowed is True
    assert decision.trigger == "wholesale_or_bulk_project"
    assert "(6 units)" not in decision.reason

    vision_20_plus_qty = (
        "[The customer sent a photo. The photo shows: Table of items: "
        "Item A, qty 10; Item B, qty 12.]"
    )
    assert wholesale_quantity(vision_20_plus_qty) == 22
    assert "wholesale_or_bulk_project" in b2b_handoff_buckets(vision_20_plus_qty)
    assert "22 units" in wholesale_handoff_from_history(vision_20_plus_qty, ()).reason


def test_storage_cabinet_concepts_exclude_hanging_drawers_and_workstations() -> None:
    """Reproduces *3210: low/freestanding 2-door cabinet queries surface credenzas & cabinets."""
    low_concepts = requested_catalog_concepts(
        "Office Small Cabinet 2 door - Height 50cm Width 40cm Length 60cm"
    )
    assert [c.name for c in low_concepts] == ["low_storage_cabinet"]

    freestanding_concepts = requested_catalog_concepts(
        "2 door freestanding office storage cabinet white light grey"
    )
    assert [c.name for c in freestanding_concepts] == ["office_cabinet"]

    # Must not hijack hanging cabinet or workstation-with-cabinet searches
    assert requested_catalog_concepts("hanging cabinet with 2 drawers") == ()
    assert requested_catalog_concepts("Work station with cabinet") == ()

    low_concept = low_concepts[0]
    credenza = _product(
        "00-07056669",
        "Credenza, SIMPLE, SCS 776, 774х600х712, White",
        stock=5,
        price=185.13,
    )
    hanging = _product(
        "00-07120554",
        "Hanging cabinet with 2 drawers, SIMPLE, SC-2V.1, 403х446х323, White",
        category="Mobile drawer",
        subcategory="Hanging drawer",
        stock=5,
        price=87.21,
    )
    workstation = _product(
        "2SWC EVOQ 1200",
        "2 Seats Workstation & fix cabinet SKYLAND EVOQ 1200",
        category="Office Furniture",
        subcategory=None,
        stock=20,
        price=1240.0,
    )
    assert product_matches_concept(
        low_concept,
        name=credenza.name_en,
        category=credenza.category,
        subcategory=credenza.subcategory,
    )
    assert not product_matches_concept(
        low_concept,
        name=hanging.name_en,
        category=hanging.category,
        subcategory=hanging.subcategory,
    )
    assert not product_matches_concept(
        freestanding_concepts[0],
        name=workstation.name_en,
        category=workstation.category,
        subcategory=workstation.subcategory,
    )


def test_cyrillic_x_dimensions_and_stock_first_ranking() -> None:
    assert _has_footprint_dimension_evidence("Dimensions: 774х600х712 mm")
    credenza_zero = _product(
        "00-07119935",
        "Credenza, LINE, SF-572103, 1300х430х645, Oak light/Black graphite",
        stock=0,
        price=2014.0,
    )
    credenza_in_stock = _product(
        "00-07056669",
        "Credenza, SIMPLE, SCS 776, 774х600х712, White",
        stock=5,
        price=185.13,
    )
    hanging = _product(
        "00-07120554",
        "Hanging cabinet with 2 drawers, SIMPLE, SC-2V.1, 403х446х323, White",
        category="Mobile drawer",
        subcategory="Hanging drawer",
        stock=5,
        price=87.21,
    )
    ranked = rank_products_for_request(
        [hanging, credenza_zero, credenza_in_stock],
        "low 2 door office storage cabinet white",
        name_of=lambda p: p.name_en,
        description_of=lambda p: p.description_en,
        category_of=lambda p: p.category,
        subcategory_of=lambda p: p.subcategory,
        stock_of=lambda p: p.stock,
    )
    assert [p.sku for p in ranked] == ["00-07056669", "00-07119935", "00-07120554"]


@pytest.mark.asyncio
async def test_search_products_recovers_white_and_grey_2_door_cabinets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reproduces *3210 Turn 2: vector search put hanging drawers and workstations ahead."""
    hanging_lock = _product(
        "00-07144768",
        "Hanging cabinet with 2 drawers with lock, SIMPLE, SC-2V.1, 403х446х323, White",
        category="Mobile drawer",
        subcategory="Hanging drawer",
        stock=1,
        price=87.21,
    )
    hanging = _product(
        "00-07120554",
        "Hanging cabinet with 2 drawers, SIMPLE, SC-2V.1, 403х446х323, White",
        category="Mobile drawer",
        subcategory="Hanging drawer",
        stock=5,
        price=87.21,
    )
    workstation = _product(
        "2SWC EVOQ 1200",
        "2 Seats Workstation & fix cabinet SKYLAND EVOQ 1200",
        category="Office Furniture",
        subcategory=None,
        stock=20,
        price=1240.0,
    )
    simple_white_orm = SimpleNamespace(
        id=uuid.uuid4(),
        sku="00-07056631",
        name_en="Cabinet with wooden doors, SIMPLE, SR-5W.1, 770х375х1817, White",
        name_ar=None,
        description_en="Compact white 2-door cabinet.",
        category="Storage",
        subcategory="Cabinet",
        price=212.16,
        currency="AED",
        stock=31,
        image_url=None,
        zoho_item_id=None,
        attributes={"specifications": {"Dimensions": "1817x375x770 mm"}},
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=None,
    )
    metal_grey_orm = SimpleNamespace(
        id=uuid.uuid4(),
        sku="STEL SSC - 15",
        name_en="Metal file closed cabinet Skyland STEL SSC - 15",
        name_ar=None,
        description_en="",
        category="Storage",
        subcategory="Cabinet",
        price=382.35,
        currency="AED",
        stock=7,
        image_url=None,
        zoho_item_id=None,
        attributes={
            "specifications": {"Color": "RAL 7035", "Product name": "File cabinet"}
        },
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=None,
    )

    locker_orm = SimpleNamespace(
        id=uuid.uuid4(),
        sku="STEL SSL-2",
        name_en="2 door locker Skyland STEL SSL-2",
        name_ar=None,
        description_en="2-door steel locker.",
        category="Storage",
        subcategory="Cabinet",
        price=235.29,
        currency="AED",
        stock=28,
        image_url=None,
        zoho_item_id=None,
        attributes={},
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=None,
    )

    mock_rag = AsyncMock(
        return_value=ProductSearchResult(
            products=[hanging_lock, hanging, workstation],
            query_interpreted="2 door freestanding office storage cabinet white light grey",
            total_found=3,
        )
    )
    monkeypatch.setattr(engine_module, "rag_search_products", mock_rag)
    monkeypatch.setattr(engine_module, "_DEFAULT_RAG_SEARCH_PRODUCTS", mock_rag)
    monkeypatch.setattr(
        engine_module,
        "apply_made_to_order_catalog_fallback",
        AsyncMock(side_effect=lambda *, primary_result, **_: primary_result),
    )

    deps = _deps(
        "This type available ? white or light grey freestanding 2-door cabinet"
    )
    sql_res = MagicMock()
    sql_res.scalars.return_value.all.return_value = [
        simple_white_orm,
        metal_grey_orm,
        locker_orm,
    ]
    deps.db.execute.return_value = sql_res

    result = await engine_module.search_products(
        _ctx(deps),
        "2 door freestanding office storage cabinet white light grey",
        max_results=3,
    )

    assert isinstance(result, ToolReturn)
    text = str(result.return_value)
    assert "00-07056631" in text
    assert "STEL SSC - 15" in text
    assert "STEL SSL-2" in text
    assert "SC-2V.1" not in text
    assert "2SWC EVOQ 1200" not in text


def test_notice_and_signage_boards_are_explicitly_excluded_in_policy() -> None:
    assert "notice boards, whiteboards, or signage boards" in BASE_SYSTEM_PROMPT.lower()
    articles = seed.canonical_kb_articles()
    policy = next(
        a for a in articles if a.title == "Product categories Treejar supplies"
    )
    assert "notice/signage boards" in policy.content.lower()
