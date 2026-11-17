"""Regression tests for *9443 (complete-item frame modifiers) and *5268 (economical + sibling ranking)."""

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
    SalesDeps,
    products_need_reranking,
    rank_products_for_request,
    request_wants_components,
    wants_economical_options,
)
from src.llm.prompts import STAGE_RULES
from src.models.conversation import Conversation
from src.schemas.common import SalesStage
from src.schemas.product import ProductRead, ProductSearchResult


@dataclass(frozen=True)
class _Item:
    name: str
    description: str = ""
    price: float = 500.0
    category: str = "Chairs"


def _product(sku: str, item: _Item) -> ProductRead:
    return ProductRead(
        id=uuid.uuid4(),
        sku=sku,
        name_en=item.name,
        description_en=item.description,
        category=item.category,
        price=item.price,
        currency="AED",
        stock=20,
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


# --- *9443: Complete-item descriptions mentioning frames/bases/legs ---------


@pytest.mark.parametrize(
    "text",
    [
        "white top desk with black metal sled frame and cable grommet",
        "white top desk black metal sled frame",
        "office chair without wheels on sled base",
        "meeting table with black metal legs",
        "ergonomic chair with chrome base",
    ],
)
def test_complete_item_with_frame_or_base_modifier_does_not_want_components(
    text: str,
) -> None:
    assert request_wants_components(text) is False


@pytest.mark.parametrize(
    "text",
    [
        "Do you sell workstation frames only?",
        "Do you sell workstation frames?",
        "need a 4-seat desk frame",
        "desk frame without top",
        "replacement legs for conference table",
        "spare parts for office chair",
    ],
)
def test_explicit_component_requests_keep_components(text: str) -> None:
    assert request_wants_components(text) is True


@pytest.mark.asyncio
async def test_search_widens_to_30_when_top_9_are_all_frames_for_complete_desk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frames = [
        _product(
            f"WK-{i}",
            _Item(
                name=f"Workstation Frame WK {100 + i} — Black (Frame Only)",
                description="Tabletop is not included.",
                price=400.0 + i * 20,
                category="Desks & Tables",
            ),
        )
        for i in range(12)
    ]
    complete_desk = _product(
        "NOVO-1200",
        _Item(
            name="Rectangular shape desks SKYLAND NOVO 1200",
            description="Complete white top rectangular office desk with metal legs.",
            price=731.43,
            category="Desks & Tables",
        ),
    )
    mock_search = AsyncMock(
        side_effect=[
            ProductSearchResult(
                products=frames[:3],
                query_interpreted="white top desk",
                total_found=3,
            ),
            ProductSearchResult(
                products=frames[:9],
                query_interpreted="white top desk",
                total_found=9,
            ),
            ProductSearchResult(
                products=[*frames, complete_desk],
                query_interpreted="white top desk",
                total_found=13,
            ),
        ]
    )
    monkeypatch.setattr(engine_module, "rag_search_products", mock_search)
    deps = _deps("do you have this")

    result = await engine_module.search_products(
        _ctx(deps),
        "white top desk with black metal sled frame and cable grommet",
        max_results=3,
    )

    assert mock_search.await_count == 3
    assert mock_search.await_args_list[1].kwargs["query"].limit == 9
    assert mock_search.await_args_list[2].kwargs["query"].limit == 30
    assert isinstance(result, ToolReturn)
    text = str(result.return_value)
    assert "NOVO-1200" in text
    assert text.index("NOVO-1200") < text.index("WK-0")
    assert "Component only" in text


# --- *5268: Economical options & same-model colour sibling deduplication ----


@pytest.mark.parametrize(
    "text",
    [
        "For my home something economical",
        "economical ergonomic office chair",
        "budget-friendly desk for startup",
        "budget chairs for small office",
        "looking for an affordable task chair",
        "كرسي مكتب اقتصادي ومريح",
    ],
)
def test_wants_economical_options_detects_qualitative_budget_cues(text: str) -> None:
    assert wants_economical_options(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "My budget is AED 6000",
        "Our furniture budget is AED 6,000.",
        "ergonomic chair with headrest",
    ],
)
def test_wants_economical_options_ignores_numeric_budget_statements(text: str) -> None:
    assert wants_economical_options(text) is False


def test_rank_products_deduplicates_colour_siblings_and_leads_with_affordable_models() -> (
    None
):
    ch620 = _Item("Executive Office Chair CH 620 grey", price=290.0, category="Chairs")
    ch970_grey = _Item(
        "Executive Office Chair CH 970 grey", price=1600.0, category="Chairs"
    )
    ch970_black = _Item(
        "Executive Office Chair CH 970 black", price=1440.0, category="Chairs"
    )
    ch500_m = _Item(
        "Operative Office Chair CH 500 M black", price=377.33, category="Chairs"
    )
    ch616 = _Item(
        "Operative Office Chair CH 616 NEW black", price=326.67, category="Chairs"
    )
    desk = _Item("Side table COMP", price=120.0, category="Desks & Tables")

    rows = [ch620, ch970_grey, ch970_black, ch500_m, ch616, desk]
    assert products_need_reranking(
        rows,
        "economical ergonomic office chair",
        name_of=lambda r: r.name,
        description_of=lambda r: r.description,
        price_of=lambda r: r.price,
    )

    ranked = rank_products_for_request(
        rows,
        "economical ergonomic office chair",
        name_of=lambda r: r.name,
        description_of=lambda r: r.description,
        price_of=lambda r: r.price,
        category_of=lambda r: r.category,
    )

    assert [r.name for r in ranked[:3]] == [
        ch620.name,
        ch616.name,
        ch500_m.name,
    ]
    assert ranked[-2] == desk or ranked[-1] == desk
    assert ranked.index(ch970_black) < ranked.index(ch970_grey)


def test_non_economical_search_preserves_vector_order_while_demoting_duplicate_colours() -> (
    None
):
    ch970_grey = _Item("Executive Office Chair CH 970 grey", price=1600.0)
    ch970_black = _Item("Executive Office Chair CH 970 black", price=1440.0)
    ch620 = _Item("Executive Office Chair CH 620 grey", price=290.0)
    ch500_m = _Item("Operative Office Chair CH 500 M black", price=377.33)

    ranked = rank_products_for_request(
        [ch970_grey, ch970_black, ch620, ch500_m],
        "ergonomic chair with headrest",
        name_of=lambda r: r.name,
        description_of=lambda r: r.description,
        price_of=lambda r: r.price,
        category_of=lambda r: r.category,
    )

    assert [r.name for r in ranked] == [
        ch970_grey.name,
        ch620.name,
        ch500_m.name,
        ch970_black.name,
    ]


def test_explicit_colour_variant_query_keeps_colour_siblings_together() -> None:
    ch970_grey = _Item("Executive Office Chair CH 970 grey", price=1600.0)
    ch970_black = _Item("Executive Office Chair CH 970 black", price=1440.0)
    ch620 = _Item("Executive Office Chair CH 620 grey", price=290.0)

    ranked = rank_products_for_request(
        [ch970_grey, ch970_black, ch620],
        "what colours do you have for executive chair",
        name_of=lambda r: r.name,
        description_of=lambda r: r.description,
        price_of=lambda r: r.price,
        category_of=lambda r: r.category,
    )

    assert [r.name for r in ranked[:2]] == [ch970_grey.name, ch970_black.name]


@pytest.mark.asyncio
async def test_search_products_widens_for_economical_query_and_returns_budget_chairs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ch620 = _product("CH-620", _Item("Executive Office Chair CH 620 grey", price=290.0))
    ch970_g = _product(
        "CH-970-G", _Item("Executive Office Chair CH 970 grey", price=1600.0)
    )
    ch970_b = _product(
        "CH-970-B", _Item("Executive Office Chair CH 970 black", price=1440.0)
    )
    ch616 = _product(
        "CH-616", _Item("Operative Office Chair CH 616 NEW black", price=326.67)
    )
    ch500_m = _product(
        "CH-500-M", _Item("Operative Office Chair CH 500 M black", price=377.33)
    )

    mock_search = AsyncMock(
        side_effect=[
            ProductSearchResult(
                products=[ch620, ch970_g, ch970_b],
                query_interpreted="economical ergonomic office chair",
                total_found=3,
            ),
            ProductSearchResult(
                products=[ch620, ch970_g, ch970_b, ch616, ch500_m],
                query_interpreted="economical ergonomic office chair",
                total_found=5,
            ),
        ]
    )
    monkeypatch.setattr(engine_module, "rag_search_products", mock_search)
    deps = _deps("For my home something economical with good back support")

    result = await engine_module.search_products(
        _ctx(deps),
        "economical ergonomic office chair with good lumbar back support",
        max_results=3,
    )

    assert mock_search.await_count == 2
    assert mock_search.await_args_list[1].kwargs["query"].limit == 15
    assert isinstance(result, ToolReturn)
    text = str(result.return_value)
    assert "CH-620" in text
    assert "CH-616" in text
    assert "CH-500-M" in text
    assert "CH-970" not in text


def test_solution_prompt_guides_distinct_budget_models() -> None:
    assert "distinct models" in STAGE_RULES["solution"]
    assert "affordable/budget tier" in STAGE_RULES["solution"]
