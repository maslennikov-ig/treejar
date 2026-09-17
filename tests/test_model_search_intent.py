"""Model-selected search constraints survive conflicting customer keywords."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from pydantic_ai import RunContext
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage

from src.llm import engine
from src.models.conversation import Conversation


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "user_text",
    [
        "No privacy panels, only open desks",
        "Do not show 10 options. I only need one desk, not 4 seats.",
        "Not interested in assembly. Compare open desks.",
    ],
)
async def test_search_does_not_reinterpret_the_model_query(user_text):
    deps = engine.SalesDeps(
        db=AsyncMock(),
        redis=AsyncMock(),
        conversation=Conversation(
            id=uuid4(), phone="test", language="en", metadata_={}
        ),
        embedding_engine=AsyncMock(),
        zoho_inventory=AsyncMock(),
        zoho_crm=None,
        messaging_client=AsyncMock(),
        pii_map={},
        user_query=user_text,
    )
    ctx = RunContext(deps=deps, model=TestModel(), usage=RunUsage(), prompt=user_text)
    with patch.object(
        engine,
        "rag_search_products",
        AsyncMock(return_value=SimpleNamespace(products=[])),
    ) as search:
        await engine.search_products(ctx, query="open desks", max_results=2)
    selected = search.await_args.kwargs["query"]
    assert selected.query == "open desks"
    assert selected.limit == 2
    assert deps.catalog_planning.requested_seats is None
    assert not deps.catalog_planning.complete_coverage
    deps.zoho_inventory.get_stock_bulk.assert_not_awaited()


def _context(user_text):
    deps = engine.SalesDeps(
        db=AsyncMock(),
        redis=AsyncMock(),
        conversation=Conversation(
            id=uuid4(), phone="test", language="en", metadata_={}
        ),
        embedding_engine=AsyncMock(),
        zoho_inventory=AsyncMock(),
        zoho_crm=None,
        messaging_client=AsyncMock(),
        pii_map={},
        user_query=user_text,
    )
    return RunContext(deps=deps, model=TestModel(), usage=RunUsage(), prompt=user_text)


@pytest.mark.asyncio
async def test_negated_fact_keywords_do_not_force_catalog_fact_repair():
    from tests.test_llm_engine import _catalog_acceptance_product

    ctx = _context(
        "Do not compare dimensions or acoustic performance; just cheapest desk"
    )
    product = _catalog_acceptance_product(
        sku="DESK", name="Office Desk", price=100.0, stock=3, description="Office desk"
    )
    with patch.object(
        engine,
        "rag_search_products",
        AsyncMock(return_value=SimpleNamespace(products=[product])),
    ):
        await engine.search_products(ctx, "office desk")
    assert ctx.deps.unsupported_catalog_facts == set()
    assert ctx.deps.catalog_fact_products == {}
    assert engine._materialize_verified_catalog_facts(ctx.deps) is None


@pytest.mark.asyncio
async def test_cross_sell_uses_exact_model_query_despite_negated_customer_keywords():
    ctx = _context("Do not add another desk; I only need a footrest")
    with (
        patch.object(
            engine,
            "rag_search_products",
            AsyncMock(return_value=SimpleNamespace(products=[])),
        ) as search,
        patch("src.services.recommendations.get_cross_sell", AsyncMock()) as curated,
    ):
        await engine.recommend_products(
            ctx,
            category="chair",
            recommendation_type="cross_sell",
            catalog_query="ergonomic footrest",
        )
    assert search.await_args.kwargs["query"].query == "ergonomic footrest"
    curated.assert_not_awaited()


@pytest.mark.asyncio
async def test_search_omitted_planning_fields_preserve_model_recorded_capacity():
    ctx = _context("sure, compare alternatives")
    with patch.object(
        engine,
        "rag_search_products",
        AsyncMock(return_value=SimpleNamespace(products=[])),
    ):
        await engine.search_products(
            ctx,
            "office desks",
            requested_seats=12,
            complete_coverage=True,
            budget_cap_aed=7000,
            families=["workspace"],
        )
        await engine.search_products(ctx, "other office desks")
    assert ctx.deps.catalog_planning.requested_seats == 12
    assert ctx.deps.catalog_planning.complete_coverage is True
    assert ctx.deps.catalog_planning.budget_cap == 7000
