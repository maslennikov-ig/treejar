"""Regression suite for tj-7z88: Nov 21 live-pilot audit (*7555) fixes.

Covers:
1. Sofa queries (including "L-shape corner sofa small") belong to seating /
   office_sofa, and wider_results in search_products preserves zero-stock
   made-to-order sofa fallback instead of overwriting sofas with L-shaped desks.
2. _product_search_call_limit scales for multi-item shopping lists and
   continuation turns ("share the other items") without collapsing to 2.
3. Search-limit fallback and Escalation Guidelines forbid unescalated
   "I'll come back to you on it" promises for unsearched/unfound items.
"""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic_ai import ToolReturn

from src.llm.catalog_families import catalog_text_families
from src.llm.catalog_planning import (
    CatalogPlanningContext,
    _product_search_call_limit,
    _search_products_limit_message,
    product_matches_concept,
    resolve_search_concepts,
)
from src.llm.engine import SalesDeps, search_products
from src.llm.prompts import BASE_SYSTEM_PROMPT
from src.models.conversation import Conversation


def _orm_product(
    sku: str,
    name_en: str,
    *,
    category: str,
    stock: int,
    price: float,
    description_en: str = "",
    zoho_item_id: str | None = None,
) -> SimpleNamespace:
    now = datetime.datetime(2026, 11, 21, tzinfo=datetime.UTC)
    return SimpleNamespace(
        id=uuid.uuid4(),
        sku=sku,
        name_en=name_en,
        name_ar=None,
        description_en=description_en or f"{name_en} commercial office furniture.",
        description_ar=None,
        category=category,
        subcategory=None,
        price=price,
        currency="AED",
        stock=stock,
        image_url=f"https://treejartrading.ae/img/{sku}.jpg",
        attributes={},
        is_active=True,
        zoho_item_id=zoho_item_id,
        created_at=now,
        updated_at=now,
        embedding=[0.1, 0.2, 0.3],
    )


@dataclass
class _DummyCtx:
    deps: SalesDeps


def test_office_sofa_concept_and_seating_family_classification() -> None:
    assert catalog_text_families("Visitor l shape sofa-small-1") == ("seating",)
    concepts = resolve_search_concepts("L-shape corner sofa small")
    assert [c.name for c in concepts] == ["office_sofa"]

    sofa_concept = concepts[0]
    assert product_matches_concept(
        sofa_concept,
        name="Lego Office Sofa",
        category="Sofas",
        description="Modular 1/2/3-seater office sofa.",
    )
    assert not product_matches_concept(
        sofa_concept,
        name="L-Shaped Executive Desk",
        category="Desks & Tables",
        description="Corner desk for office.",
    )


@pytest.mark.asyncio
async def test_l_shape_sofa_search_not_overwritten_by_wider_in_stock_l_desks() -> None:
    l_desks = [
        _orm_product(
            f"DESK-L-{idx}",
            f"L-Shaped Executive Desk {idx}",
            category="Desks & Tables",
            stock=5,
            price=1800.0 + idx * 100,
            zoho_item_id=f"zoho-desk-{idx}",
        )
        for idx in range(1, 16)
    ]
    sofas = [
        _orm_product(
            "SOFA-LEGO",
            "Lego Office Sofa",
            category="Sofas",
            stock=0,
            price=1565.0,
            description_en="Modular office sofa easy to combine configurations.",
        ),
        _orm_product(
            "SOFA-ALLORA",
            "Allora Office Sofa",
            category="Sofas",
            stock=0,
            price=1540.0,
        ),
        _orm_product(
            "SOFA-MARS",
            "Mars Office Sofa",
            category="Sofas",
            stock=0,
            price=875.0,
        ),
        _orm_product(
            "SOFA-COSIMA",
            "Cosima Office Sofa",
            category="Sofas",
            stock=0,
            price=2000.0,
        ),
    ]

    async def _execute(stmt: Any, *_args: Any, **_kwargs: Any) -> Any:
        sql = str(stmt)
        res = MagicMock()
        if "products.stock >" in sql:
            res.scalars.return_value.all.return_value = l_desks
        elif "products.stock <=" in sql:
            res.scalars.return_value.all.return_value = sofas
        else:
            res.scalars.return_value.all.return_value = sofas
        return res

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=_execute)
    embedder = AsyncMock()
    embedder.embed_async = AsyncMock(return_value=[0.1, 0.2, 0.3])
    zoho = AsyncMock()
    zoho.get_stock_bulk = AsyncMock(return_value=[])

    ctx = _DummyCtx(
        deps=SalesDeps(
            db=db,
            redis=AsyncMock(),
            conversation=Conversation(
                id=uuid.uuid4(),
                phone="971500007555@c.us",
                sales_stage="qualifying",
                language="en",
            ),
            embedding_engine=embedder,
            zoho_inventory=zoho,
            zoho_crm=AsyncMock(),
            messaging_client=MagicMock(),
            pii_map={},
            crm_context={"Segment": "Unknown"},
            user_query="Visitor l shape sofa-small-1",
            defer_product_media=True,
        )
    )

    result = await search_products(
        ctx, query="L-shape corner sofa small", max_results=3
    )
    text = result.return_value if isinstance(result, ToolReturn) else result
    assert "Office Sofa" in text
    assert "L-Shaped Executive Desk" not in text


def test_multi_item_and_continuation_search_call_limit() -> None:
    seven_item_list = (
        "Office chair 8 nos\n"
        "Reception chair 1 no\n"
        "Visitor chair 2 nos\n"
        "Visitor l shape sofa-small-1\n"
        "4 people workstation-2 set\n"
        "Coffee /tea table-1\n"
        "Tea counter-1"
    )
    turn3_deps = SimpleNamespace(
        user_query=seven_item_list,
        catalog_planning=CatalogPlanningContext(),
        recent_history=[f"user: {seven_item_list}"],
    )
    assert _product_search_call_limit(turn3_deps) == 7

    turn4_deps = SimpleNamespace(
        user_query="Ok please share the other items pictures and price also",
        catalog_planning=CatalogPlanningContext(),
        recent_history=[
            f"user: {seven_item_list}",
            "assistant: Here are the chairs. I haven't pulled the rest yet.",
            "user: Ok please share the other items pictures and price also",
        ],
    )
    assert _product_search_call_limit(turn4_deps) == 7

    narrow_followup_deps = SimpleNamespace(
        user_query="Show me cheaper chairs from this configuration.",
        catalog_planning=CatalogPlanningContext(
            families=("seating", "workspace", "storage")
        ),
        recent_history=[f"user: {seven_item_list}"],
    )
    assert _product_search_call_limit(narrow_followup_deps) == 2


def test_search_limit_message_and_prompt_forbid_unescalated_promises() -> None:
    msg = _search_products_limit_message(include_no_results=True).casefold()
    assert "escalate_to_manager" in msg
    assert "never promise" in msg
    assert "come back to the customer later" in BASE_SYSTEM_PROMPT.casefold()
