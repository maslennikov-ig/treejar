"""search_products resolves named SKUs directly and reads needs-only requests.

tj-uz6j.4, production 2026-09-23: "CH 616 NEW black" had local stock 0, so the
in-stock vector search never returned it. get_stock found it (Zoho stock 1), and
the next search_products call still told the customer the exact chair was not
confirmed. tj-uz6j.2: a needs-only request carried the same caveat on every
reply although it named no item at all.
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

import src.llm.catalog_references as catalog_references_module
import src.llm.engine as engine_module
from src.llm.catalog_planning import (
    CatalogPlanningContext,
    _catalog_search_query_with_constraints,
    _product_search_response_contract,
)
from src.llm.engine import SalesDeps, search_products
from src.models.conversation import Conversation
from src.schemas.product import ProductRead

pytestmark = pytest.mark.usefixtures("authorized_outbound_unit_path")

_NOT_CONFIRMED = "exact requested item not confirmed"


def _row(sku: str, name: str, *, stock: int, price: float = 295.0) -> Any:
    return SimpleNamespace(
        id=uuid.uuid4(),
        sku=sku,
        name_en=name,
        name_ar=None,
        description_en=f"{name} for office use",
        category="Chairs",
        subcategory=None,
        price=price,
        currency="AED",
        stock=stock,
        image_url=None,
        zoho_item_id=None,
        attributes=None,
        is_active=True,
        created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        updated_at=None,
    )


_CATALOG = [
    _row("CH 616 NEW black", "Operative Office Chair CH 616 NEW black", stock=0),
    _row("CH 616 black", "Executive Office Chair CH 616 black", stock=3, price=410),
    _row("CH 460 black", "Operative Office Chair CH 460 black", stock=8, price=180),
]


class _CatalogDb:
    """Answers every select with the whole catalog; callers filter by stem."""

    def __init__(self, rows: list[Any]) -> None:
        self.rows = rows
        self.execute = AsyncMock(side_effect=self._execute)
        self.commit = AsyncMock()

    async def _execute(self, *_args: Any, **_kwargs: Any) -> Any:
        result = MagicMock()
        result.scalars.return_value.all.return_value = list(self.rows)
        return result


@dataclass
class _Ctx:
    deps: SalesDeps


def _ctx(db: Any, stock_by_sku: dict[str, int] | None = None) -> _Ctx:
    zoho = AsyncMock()
    zoho.get_stock_bulk.return_value = [
        {"sku": sku, "stock_on_hand": stock, "rate": 295.0}
        for sku, stock in (stock_by_sku or {}).items()
    ]
    return _Ctx(
        deps=SalesDeps(
            db=db,
            redis=AsyncMock(),
            conversation=Conversation(
                id="00000000-0000-0000-0000-000000000000",
                phone="+1234567890",
                sales_stage="greeting",
                language="en",
            ),
            embedding_engine=AsyncMock(),
            zoho_inventory=zoho,
            zoho_crm=AsyncMock(),
            messaging_client=MagicMock(),
            pii_map={},
            crm_context={"Segment": "Unknown"},
        )
    )


def _vector_results(*rows: Any) -> AsyncMock:
    return AsyncMock(
        return_value=SimpleNamespace(
            products=[ProductRead.model_validate(row) for row in rows]
        )
    )


@pytest.mark.asyncio
async def test_named_zero_stock_sku_is_found_and_exact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The in-stock vector search returns only the sibling, never the NEW chair.
    monkeypatch.setattr(
        engine_module, "rag_search_products", _vector_results(_CATALOG[1])
    )
    ctx = _ctx(_CatalogDb(_CATALOG), {"CH 616 NEW black": 1})

    result = await search_products(ctx, "CH 616 NEW black chair")  # type: ignore[arg-type]

    assert isinstance(result, ToolReturn)
    text = result.return_value
    assert text.startswith("Name: Operative Office Chair CH 616 NEW black")
    assert "Current stock: 1 (Zoho-confirmed)" in text
    assert _NOT_CONFIRMED not in text
    assert "closest alternatives" not in str(result.content).casefold()


@pytest.mark.asyncio
async def test_two_named_skus_in_one_query_both_resolve(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(engine_module, "rag_search_products", _vector_results())
    ctx = _ctx(_CatalogDb(_CATALOG))

    result = await search_products(  # type: ignore[arg-type]
        ctx, "CH 616 NEW black and CH 460 black chairs"
    )

    assert isinstance(result, ToolReturn)
    text = result.return_value
    assert "SKU: CH 616 NEW black" in text
    assert "SKU: CH 460 black" in text
    assert "SKU: CH 616 black\n" not in text
    assert _NOT_CONFIRMED not in text


@pytest.mark.asyncio
async def test_unknown_named_sku_is_reported_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(engine_module, "rag_search_products", _vector_results())
    ctx = _ctx(_CatalogDb(_CATALOG))

    result = await search_products(ctx, "CH 460 black and CH 999 grey")  # type: ignore[arg-type]

    assert isinstance(result, ToolReturn)
    assert "Requested catalog reference not found in the catalog: CH 999 grey" in (
        result.return_value
    )
    assert "SKU: CH 460 black" in result.return_value


@pytest.mark.asyncio
async def test_generic_query_uses_vector_search_without_direct_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    luma = _row(
        "OF-HAI-Luma-Workstation-RJ 9719-4-Walnut",
        "Four person workstation SKYLAND LUMA 9719-4",
        stock=30,
        price=1883,
    )
    novo = _row(
        "OF-YED-NOVO-Workstation-63LW-1.2T-6-white",
        "4 Person Face to Face Table SKYLAND NOVO 2400",
        stock=5,
        price=1813,
    )
    rag = _vector_results(luma, novo)
    monkeypatch.setattr(engine_module, "rag_search_products", rag)
    db = _CatalogDb(_CATALOG)
    ctx = _ctx(db)

    result = await search_products(  # type: ignore[arg-type]
        ctx,
        "office furniture for a new Dubai office for four people; seating and "
        "workspace options",
    )

    assert isinstance(result, ToolReturn)
    rag.assert_awaited_once()
    db.execute.assert_not_awaited()
    assert _NOT_CONFIRMED not in result.return_value
    assert "no specific item was named" in result.return_value
    assert "not confirmed" not in str(result.content).casefold().replace(
        "do not say the requested item is unconfirmed", ""
    )


@pytest.mark.asyncio
async def test_named_but_absent_brand_keeps_the_caveat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    luma = _row(
        "OF-HAI-Luma-Workstation-RJ 9719-4-Walnut",
        "Four person workstation SKYLAND LUMA 9719-4",
        stock=30,
        price=1883,
    )
    monkeypatch.setattr(engine_module, "rag_search_products", _vector_results(luma))
    ctx = _ctx(_CatalogDb(_CATALOG))

    result = await search_products(ctx, "HERMAN workstation for four people")  # type: ignore[arg-type]

    assert isinstance(result, ToolReturn)
    assert _NOT_CONFIRMED in result.return_value


@pytest.mark.asyncio
async def test_contracts_drop_the_stray_caveat_and_generic_has_none() -> None:
    exact = _product_search_response_contract(match_kind="exact").casefold()
    generic = _product_search_response_contract(match_kind="generic").casefold()

    assert "say that honestly" not in exact
    assert "closest alternatives" not in exact
    assert "no exact item to confirm" in generic
    assert "invent" in generic
    assert "next action" in generic


def test_seat_count_is_not_appended_to_a_named_model_or_seating_query() -> None:
    planning = CatalogPlanningContext(requested_seats=4)

    assert (
        _catalog_search_query_with_constraints(
            "LUMA 9719-4 workstation", "private desks", planning
        )
        == "LUMA 9719-4 workstation"
    )
    assert (
        _catalog_search_query_with_constraints(
            "ergonomic office chair", "private desks", planning
        )
        == "ergonomic office chair"
    )
    assert (
        _catalog_search_query_with_constraints("workstation", "private desks", planning)
        == "workstation 4 person privacy panels"
    )


def test_latin_sku_lookup_also_reaches_a_cyrillic_catalogue_prefix() -> None:
    assert catalog_references_module._cyrillic_sku_prefix_variant("CH 135 BLACK") == (
        "СН 135 BLACK"
    )
    assert catalog_references_module._cyrillic_sku_prefix_variant("SK-12") is None
    assert catalog_references_module._cyrillic_sku_prefix_variant("BLACK") is None
