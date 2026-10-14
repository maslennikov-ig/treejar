"""Keep separate named products grounded in a single real search shape."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic_ai import ToolReturn

from src.llm import engine
from tests.test_search_products_named_references import (
    _CatalogDb,
    _ctx,
    _row,
    _vector_results,
)

pytestmark = pytest.mark.usefixtures("authorized_outbound_unit_path")

_OWNER_REQUEST = (
    "I need two walnut LUMA 9719-4 workstations for eight people in Dubai. "
    "My budget is AED 6000. Do not prepare a quotation. Please show CT 1065 "
    "coffee tables in Oak Devon and Wenge Magic with photos."
)
_SEARCH_QUERY = (
    "walnut LUMA 9719-4 workstation for 4 people, and CT 1065 coffee tables "
    "Oak Devon and Wenge Magic with photos"
)


def _catalog_rows() -> list[SimpleNamespace]:
    source = (
        Path(__file__).parent
        / "fixtures/catalog_snapshot_2026-10-14_tester_subset.json"
    )
    rows = []
    for data in json.loads(source.read_text()):
        row = _row(data["sku"], data["name_en"], stock=data["stock"])
        row.__dict__.update(data)
        rows.append(row)
    return rows


def _wanted(row: SimpleNamespace) -> bool:
    name = row.name_en.casefold()
    return "9719-4" in name or (
        "ct 1065" in name and ("oak devon" in name or "wenge magic" in name)
    )


@pytest.mark.asyncio
async def test_mixed_named_search_confirms_all_parts_and_keeps_only_their_media(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Retrieval contains the 2-person sibling and unrequested Walnut Dallas too.
    rows = _catalog_rows()
    monkeypatch.setattr(engine, "rag_search_products", _vector_results(*rows))
    lookup = _vector_results()
    lookup.return_value = SimpleNamespace(products=(), unresolved_references=())
    monkeypatch.setattr(engine, "_resolve_query_catalog_references", lookup)
    ctx = _ctx(_CatalogDb([]), {r.sku: r.stock for r in rows})
    ctx.deps.user_query = _OWNER_REQUEST
    ctx.deps.defer_product_media = True

    result = await engine.search_products(ctx, _SEARCH_QUERY, max_results=5)  # type: ignore[arg-type]

    assert isinstance(result, ToolReturn)
    assert "exact requested item not confirmed" not in result.return_value
    assert "closest alternatives" not in str(result.content).casefold()
    assert {media.product_key for media in ctx.deps.pending_product_media} == {
        str(row.id) for row in rows if _wanted(row)
    }
    assert len(ctx.deps.pending_product_media) == 3


@pytest.mark.asyncio
@pytest.mark.parametrize("missing_part", ["luma", "wenge", "oak"])
async def test_incomplete_mixed_named_search_keeps_the_real_gap(
    monkeypatch: pytest.MonkeyPatch, missing_part: str
) -> None:
    rows = [row for row in _catalog_rows() if _wanted(row)]
    rows = [
        row
        for row in rows
        if not (
            (missing_part == "luma" and "9719-4" in row.name_en.casefold())
            or (missing_part == "wenge" and "wenge magic" in row.name_en.casefold())
            or (missing_part == "oak" and "oak devon" in row.name_en.casefold())
        )
    ]
    monkeypatch.setattr(engine, "rag_search_products", _vector_results(*rows))
    lookup = _vector_results()
    lookup.return_value = SimpleNamespace(products=(), unresolved_references=())
    monkeypatch.setattr(engine, "_resolve_query_catalog_references", lookup)
    ctx = _ctx(_CatalogDb([]), {r.sku: r.stock for r in rows})
    ctx.deps.user_query = _OWNER_REQUEST
    ctx.deps.defer_product_media = True

    result = await engine.search_products(ctx, _SEARCH_QUERY)  # type: ignore[arg-type]

    assert isinstance(result, ToolReturn)
    assert "exact requested item not confirmed" in result.return_value
    assert "closest alternatives" in str(result.content).casefold()
