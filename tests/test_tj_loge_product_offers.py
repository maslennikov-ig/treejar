"""tj-loge.4: do not lead with frame-only or unrequested products.

Built on two live dialogues from 2026-11-05:

* A generic opening ("I am interested in purchasing office furniture. Could you
  assist me?") was answered with three workstation frames before the customer
  named any need.
* "Work station with cabinet" was answered with WK 360 / WK 120 frames
  ("tabletops and cabinets are not included") ahead of the SKYLAND EVOQ
  workstation with a fixed cabinet.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic_ai import RunContext, ToolReturn
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage

import src.llm.engine as engine_module
from src.llm.catalog_planning import (
    GENERIC_INTEREST_SEARCH_CONTRACT,
    SalesDeps,
    is_component_only_product,
    names_no_furniture_need,
    opening_wants_a_price_anchor,
    products_need_reranking,
    rank_products_for_request,
    request_wants_components,
)
from src.models.conversation import Conversation
from src.schemas.common import SalesStage
from src.schemas.product import ProductRead, ProductSearchResult

GENERIC_OPENING = (
    "Hi. I am interested in purchasing office furniture. Could you assist me?"
)


@dataclass(frozen=True)
class _Row:
    name: str
    description: str = ""


WK_360_FRAME = _Row(
    "WK 360 6-seat workstation frame black",
    "Frame-only; tabletops and cabinets are not included.",
)
WK_120_FRAME = _Row(
    "WK 120 workstation frame black",
    "Tabletops are not included.",
)
EVOQ_WITH_CABINET = _Row(
    "SKYLAND EVOQ 1200 2-seat workstation",
    "2-seat workstation with fixed cabinet.",
)
LUMA_MANAGER_DESK = _Row(
    "SKYLAND LUMA manager desk 1600",
    "Manager desk with steel frame and melamine top.",
)
PLAIN_WORKSTATION = _Row(
    "Bench workstation 4-seat",
    "Four-seat bench workstation, white top, black frame.",
)


def _rank(rows: list[_Row], request: str) -> list[_Row]:
    return rank_products_for_request(
        rows,
        request,
        name_of=lambda row: row.name,
        description_of=lambda row: row.description,
    )


# --- 1. A generic purchase-interest opening names no need -----------------


@pytest.mark.parametrize(
    "text",
    [
        GENERIC_OPENING,
        "I am interested in purchasing office furniture.",
        "Hello, can you help me? I want to buy furniture",
        "Could you assist me?",
    ],
)
def test_generic_purchase_interest_names_no_need(text: str) -> None:
    assert names_no_furniture_need(text) is True
    assert opening_wants_a_price_anchor(text) is False


@pytest.mark.parametrize(
    "text",
    [
        "manager desk required",
        "Work station with cabinet",
        "Qty.350Nos",
        "office furniture for four people",
        "I want to buy furniture, what are your prices?",
        "I am interested in 10 chairs",
        "Hello",
        "How much are your prices?",
    ],
)
def test_a_stated_need_or_bare_greeting_is_not_generic(text: str) -> None:
    assert names_no_furniture_need(text) is False


@pytest.mark.parametrize(
    "text",
    ["Hello", "How much are your prices?", "manager desk required"],
)
def test_calibrated_openings_keep_the_price_anchor(text: str) -> None:
    assert opening_wants_a_price_anchor(text) is True


# --- 2. Frame-only rows never lead a request for a complete item ----------


def test_frame_rows_are_recognised_as_components() -> None:
    assert is_component_only_product(WK_360_FRAME.name, WK_360_FRAME.description)
    assert is_component_only_product(WK_120_FRAME.name, WK_120_FRAME.description)
    assert is_component_only_product("Desk base only", "")
    assert is_component_only_product("Gas lift", "Spare part for task chairs")


def test_complete_products_with_a_frame_word_are_not_components() -> None:
    assert not is_component_only_product(
        LUMA_MANAGER_DESK.name, LUMA_MANAGER_DESK.description
    )
    assert not is_component_only_product(
        PLAIN_WORKSTATION.name, PLAIN_WORKSTATION.description
    )
    assert not is_component_only_product(
        EVOQ_WITH_CABINET.name, EVOQ_WITH_CABINET.description
    )
    assert not is_component_only_product("Mesh chair chrome frame", "")


def test_workstation_with_cabinet_leads_with_the_cabinet_workstation() -> None:
    rows = [WK_360_FRAME, WK_120_FRAME, PLAIN_WORKSTATION, EVOQ_WITH_CABINET]
    request = "Work station with cabinet\nQty.350Nos"

    ranked = _rank(rows, request)

    assert ranked[0] == EVOQ_WITH_CABINET
    assert ranked[1] == PLAIN_WORKSTATION
    assert ranked[-2:] == [WK_360_FRAME, WK_120_FRAME]


def test_manager_desk_request_puts_frames_last_and_keeps_vector_order() -> None:
    rows = [WK_360_FRAME, LUMA_MANAGER_DESK, WK_120_FRAME, PLAIN_WORKSTATION]

    ranked = _rank(rows, "manager desk required")

    assert ranked == [LUMA_MANAGER_DESK, PLAIN_WORKSTATION, WK_360_FRAME, WK_120_FRAME]


def test_frames_keep_their_place_when_the_customer_asks_for_frames() -> None:
    rows = [WK_360_FRAME, LUMA_MANAGER_DESK]
    request = "Do you sell workstation frames only?"

    assert request_wants_components(request)
    assert _rank(rows, request) == rows
    assert not products_need_reranking(
        rows,
        request,
        name_of=lambda row: row.name,
        description_of=lambda row: row.description,
    )


def test_frames_still_appear_when_nothing_complete_matches() -> None:
    assert _rank([WK_360_FRAME, WK_120_FRAME], "workstation") == [
        WK_360_FRAME,
        WK_120_FRAME,
    ]


# --- search_products wiring ------------------------------------------------


def _product(sku: str, row: _Row) -> ProductRead:
    return ProductRead(
        id=uuid.uuid4(),
        sku=sku,
        name_en=row.name,
        description_en=row.description,
        price=500.0,
        currency="AED",
        stock=20,
        is_active=True,
        created_at=datetime.now(UTC),
    )


def _deps(user_query: str, recent_history: list[str] | None = None) -> SalesDeps:
    db = AsyncMock()
    conv = Conversation(
        id=uuid.uuid4(),
        phone="12345",
        customer_name="Test User",
        sales_stage=SalesStage.GREETING.value,
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
        recent_history=recent_history,
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


@pytest.mark.asyncio
async def test_generic_opening_search_returns_no_products(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_search = AsyncMock()
    monkeypatch.setattr(engine_module, "rag_search_products", mock_search)
    deps = _deps(GENERIC_OPENING)

    result = await engine_module.search_products(_ctx(deps), "office furniture")

    mock_search.assert_not_awaited()
    assert isinstance(result, ToolReturn)
    assert result.content == GENERIC_INTEREST_SEARCH_CONTRACT
    assert deps.product_search_calls == 0


@pytest.mark.asyncio
async def test_generic_turn_still_searches_a_need_stated_earlier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_search = AsyncMock(
        return_value=ProductSearchResult(
            products=[_product("LUMA-1600", LUMA_MANAGER_DESK)],
            query_interpreted="office furniture",
            total_found=1,
        )
    )
    monkeypatch.setattr(engine_module, "rag_search_products", mock_search)
    deps = _deps("Could you assist me?", ["user: manager desk required"])

    await engine_module.search_products(_ctx(deps), "office furniture")

    mock_search.assert_awaited_once()


@pytest.mark.asyncio
async def test_search_widens_and_leads_with_the_cabinet_workstation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    narrow = ProductSearchResult(
        products=[
            _product("WK-360", WK_360_FRAME),
            _product("WK-120", WK_120_FRAME),
            _product("BENCH-4", PLAIN_WORKSTATION),
        ],
        query_interpreted="workstation with cabinet",
        total_found=3,
    )
    wide = ProductSearchResult(
        products=[*narrow.products, _product("EVOQ-1200", EVOQ_WITH_CABINET)],
        query_interpreted="workstation with cabinet",
        total_found=4,
    )
    mock_search = AsyncMock(side_effect=[narrow, wide])
    monkeypatch.setattr(engine_module, "rag_search_products", mock_search)
    deps = _deps("Work station with cabinet")

    result = await engine_module.search_products(
        _ctx(deps), "workstation with cabinet", max_results=3
    )

    assert mock_search.await_count == 2
    assert mock_search.await_args_list[1].kwargs["query"].limit == 9
    assert isinstance(result, ToolReturn)
    text = str(result.return_value)
    assert "EVOQ-1200" in text
    assert "WK-120" not in text
    assert text.index("EVOQ-1200") < text.index("BENCH-4") < text.index("WK-360")
    assert "Component only" in text
