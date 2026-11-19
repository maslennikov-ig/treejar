"""Regression tests for tj-8mtx: hybrid concept/attribute recall, ranking, and specs formatting."""

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
    extract_product_specifications_summary,
    product_matches_concept,
    rank_products_for_request,
    requested_catalog_concepts,
)
from src.llm.verified_answers import classify_product_match
from src.models.conversation import Conversation
from src.rag.made_to_order_fallback import augment_results_with_concept_candidates
from src.schemas.common import SalesStage
from src.schemas.product import ProductRead, ProductSearchQuery, ProductSearchResult


def _product(
    sku: str,
    name: str,
    *,
    category: str = "Desks & Tables",
    subcategory: str | None = None,
    description: str = "",
    price: float = 800.0,
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


def test_requested_catalog_concepts_and_chair_exclusion() -> None:
    concepts = requested_catalog_concepts("electric height adjustable sit-stand desk")
    assert [c.name for c in concepts] == ["height_adjustable_desk"]
    ha_concept = concepts[0]

    assert requested_catalog_concepts("ergonomic adjustable office chair") == ()
    assert product_matches_concept(
        ha_concept,
        name="Adjustable table SkyLand SK 28 white NEW",
        category="adjustable tables",
        description="",
    )
    assert product_matches_concept(
        ha_concept,
        name="Adjustable table SkyLand SK 20 white",
        category="Smart Furniture",
        attributes={
            "specifications": {
                "Desk Design": "Standing Desk",
                "Lifting Mechanism": "Electric",
            }
        },
    )
    assert not product_matches_concept(
        ha_concept,
        name="Executive Office Chair CH 200 blue",
        category="Smart Furniture",
        description="Massage office chair",
    )
    assert not product_matches_concept(
        ha_concept,
        name="Manager Desk 1400 SKYLAND LUMA 927-14",
        category="Desks & Tables",
    )


def test_extract_specifications_summary_filters_packaging_and_boilerplate() -> None:
    summary = extract_product_specifications_summary(
        {
            "specifications": {
                "Size": "120x60cm",
                "Desk Design": "Standing Desk",
                "Lifting Mechanism": "Electric",
                "Item Package Weight": "31.5",
                "Package Length Unit": "Centimeters",
                "Parentage Level": "Child",
                "Number of Boxes": "1",
            },
            "features": [
                "Fast delivery across UAE",
                "Dual-motor height adjustment, 35 mm/s lift speed",
            ],
        }
    )
    assert "Size: 120x60cm" in summary
    assert "Desk Design: Standing Desk" in summary
    assert "Lifting Mechanism: Electric" in summary
    assert "Dual-motor height adjustment" in summary
    assert "Package" not in summary
    assert "Parentage" not in summary
    assert "Fast delivery across UAE" not in summary


def test_rank_products_prefers_in_stock_height_adjustable_and_deduplicates_colours() -> (
    None
):
    chair = _product(
        "CH 135 black", "Executive Office Chair CH 135 black", category="Chairs"
    )
    fixed_desk = _product(
        "LUMA 927-14", "Manager Desk 1400 SKYLAND LUMA 927-14", stock=34
    )
    sk38_zero = _product(
        "SK 38 white",
        "Adjustable table SkyLand SK 38 white",
        category="Smart Furniture",
        stock=0,
        price=1173.33,
    )
    sk28_new = _product(
        "SK 28 white NEW",
        "Adjustable table SkyLand SK 28 white NEW",
        category="adjustable tables",
        stock=93,
        price=810.0,
    )
    sk38_black_new = _product(
        "SK 38 black NEW",
        "Adjustable table SkyLand SK 38 black NEW",
        category="adjustable tables",
        stock=49,
        price=866.0,
    )
    sk38_white_new = _product(
        "SK 38 white NEW",
        "Adjustable table SkyLand SK 38 white NEW",
        category="adjustable tables",
        stock=41,
        price=866.0,
    )
    sk20 = _product(
        "SK 20 white",
        "Adjustable table SkyLand SK 20 white",
        category="Smart Furniture",
        stock=40,
        price=795.0,
    )

    ranked = rank_products_for_request(
        [chair, fixed_desk, sk38_zero, sk28_new, sk38_black_new, sk38_white_new, sk20],
        "electric height adjustable sit-stand desk",
        name_of=lambda p: p.name_en,
        description_of=lambda p: p.description_en,
        category_of=lambda p: p.category,
        subcategory_of=lambda p: p.subcategory,
        attributes_of=lambda p: p.attributes,
        stock_of=lambda p: p.stock,
    )

    top3_skus = [p.sku for p in ranked[:3]]
    assert top3_skus == ["SK 28 white NEW", "SK 38 black NEW", "SK 20 white"]
    assert ranked.index(sk38_zero) < ranked.index(fixed_desk)
    assert ranked.index(sk38_zero) < ranked.index(chair)


@pytest.mark.asyncio
async def test_augment_results_with_concept_candidates_recovers_missed_adjustable_tables() -> (
    None
):
    fixed = _product("LUMA 927-14", "Manager Desk 1400 SKYLAND LUMA 927-14", stock=34)
    sk28 = SimpleNamespace(
        id=uuid.uuid4(),
        sku="SK 28 white NEW",
        name_en="Adjustable table SkyLand SK 28 white NEW",
        name_ar=None,
        description_en="",
        category="adjustable tables",
        subcategory=None,
        price=810.0,
        currency="AED",
        stock=93,
        image_url=None,
        zoho_item_id=None,
        attributes={},
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=None,
    )
    ch200 = SimpleNamespace(
        id=uuid.uuid4(),
        sku="CH 200 blue",
        name_en="Executive Office Chair CH 200 blue",
        name_ar=None,
        description_en="Massage office chair",
        category="Smart Furniture",
        subcategory=None,
        price=699.0,
        currency="AED",
        stock=3,
        image_url=None,
        zoho_item_id=None,
        attributes={},
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=None,
    )

    db = AsyncMock()
    exec_res = MagicMock()
    exec_res.scalars.return_value.all.return_value = [sk28, ch200]
    db.execute.return_value = exec_res

    concepts = requested_catalog_concepts("height adjustable sit-stand desk")
    augmented = await augment_results_with_concept_candidates(
        db,
        ProductSearchQuery(query="height adjustable sit-stand desk", limit=3),
        concepts=concepts,
        existing_result=ProductSearchResult(
            products=[fixed],
            query_interpreted="height adjustable sit-stand desk",
            total_found=1,
        ),
        min_results=3,
    )

    skus = [p.sku for p in augmented.products]
    assert "SK 28 white NEW" in skus
    assert "CH 200 blue" not in skus


@pytest.mark.asyncio
async def test_search_products_hybrid_recovers_adjustable_desks_and_formats_specs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reproduces *3918: vector search missed adjustable tables at top-3."""
    chair = _product(
        "CH 135 black", "Executive Office Chair CH 135 black", category="Chairs"
    )
    fixed_desk = _product(
        "LUMA 927-14", "Manager Desk 1400 SKYLAND LUMA 927-14", stock=34
    )
    pedestal = _product("SC-3D.1A", "Desk height pedestal SIMPLE", category="Storage")

    sk20_orm = SimpleNamespace(
        id=uuid.uuid4(),
        sku="SK 20 white",
        name_en="Adjustable table SkyLand SK 20 white",
        name_ar=None,
        description_en="Adjustable table SkyLand SK 20 white — premium adjustable tables.",
        category="Smart Furniture",
        subcategory=None,
        price=795.0,
        currency="AED",
        stock=40,
        image_url=None,
        zoho_item_id=None,
        attributes={
            "specifications": {
                "Size": "120x60cm",
                "Desk Design": "Standing Desk",
                "Lifting Mechanism": "Electric",
                "Special Features": "Adjustable Height",
            }
        },
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=None,
    )
    sk28_orm = SimpleNamespace(
        id=uuid.uuid4(),
        sku="SK 28 white NEW",
        name_en="Adjustable table SkyLand SK 28 white NEW",
        name_ar=None,
        description_en="",
        category="adjustable tables",
        subcategory=None,
        price=810.0,
        currency="AED",
        stock=93,
        image_url=None,
        zoho_item_id=None,
        attributes={},
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=None,
    )

    mock_rag = AsyncMock(
        return_value=ProductSearchResult(
            products=[chair, fixed_desk, pedestal],
            query_interpreted="electric height adjustable sit-stand desk",
            total_found=3,
        )
    )
    # Keep default identity check active by patching _DEFAULT_RAG_SEARCH_PRODUCTS too
    monkeypatch.setattr(engine_module, "rag_search_products", mock_rag)
    monkeypatch.setattr(engine_module, "_DEFAULT_RAG_SEARCH_PRODUCTS", mock_rag)
    monkeypatch.setattr(
        engine_module,
        "apply_made_to_order_catalog_fallback",
        AsyncMock(side_effect=lambda *, primary_result, **_: primary_result),
    )

    deps = _deps("I am interested in your height adjustable desk models")
    sql_res = MagicMock()
    sql_res.scalars.return_value.all.return_value = [sk28_orm, sk20_orm]
    deps.db.execute.return_value = sql_res

    result = await engine_module.search_products(
        _ctx(deps),
        "electric height adjustable sit-stand desk",
        max_results=3,
    )

    assert isinstance(result, ToolReturn)
    text = str(result.return_value)
    assert "SK 28 white NEW" in text
    assert "SK 20 white" in text
    assert "Category: adjustable tables" in text
    assert "Category: Smart Furniture" in text
    assert (
        "Specifications: Size: 120x60cm; Desk Design: Standing Desk; Lifting Mechanism: Electric"
        in text
    )
    assert "Weak catalog matches only" not in text


def test_classify_product_match_treats_adjustable_tables_as_relevant_not_missing() -> (
    None
):
    match = classify_product_match(
        "sit-stand desk",
        ["Adjustable table SkyLand SK 28 white NEW\n\nadjustable tables"],
        candidate_skus=["SK 28 white NEW"],
    )
    assert match in {"nearby", "generic", "exact"}
    assert match != "missing"


@pytest.mark.parametrize(
    ("query", "expected_concept"),
    [
        ("soundproof phone booth for 1 person", "acoustic_pod"),
        ("high bar stool with backrest", "bar_stool"),
        ("l-shaped corner desk for manager", "l_shape_desk"),
        ("office reception counter desk", "reception_desk"),
        ("8 person conference meeting table", "meeting_table"),
        ("steel locker or mobile pedestal", "steel_storage"),
    ],
)
def test_other_catalog_concepts_detected_uniformly(
    query: str, expected_concept: str
) -> None:
    concepts = requested_catalog_concepts(query)
    assert expected_concept in [c.name for c in concepts]
