from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.llm.engine import (
    CatalogDecision,
    StockSnapshot,
    VerifiedCatalogLine,
    validate_catalog_decision,
)


def _line(*, sku: str = "CH-616", stock: int = 4) -> VerifiedCatalogLine:
    return VerifiedCatalogLine(
        family="seating",
        name="Operative chair",
        sku=sku,
        quantity=4,
        unit_price=295.0,
        total=1180.0,
        currency="AED",
        stock=stock,
        capacity=1,
    )


def test_catalog_decision_rejects_conflicting_stock_for_same_sku() -> None:
    now = datetime(2026, 8, 3, tzinfo=UTC)
    decision = CatalogDecision(
        requirements=("seating",),
        selected_lines=(_line(),),
        requested_seats=4,
        budget_cap=2000.0,
        stock_snapshots=(
            StockSnapshot(sku="CH-616", available=4, source="zoho", as_of=now),
            StockSnapshot(sku="ch-616", available=3, source="zoho", as_of=now),
        ),
        recommendation="CH-616",
    )

    with pytest.raises(ValueError, match="conflicting stock"):
        validate_catalog_decision(decision)


def test_catalog_decision_requires_zoho_snapshot_for_selected_line() -> None:
    decision = CatalogDecision(
        requirements=("seating",),
        selected_lines=(_line(),),
        requested_seats=4,
        budget_cap=2000.0,
        stock_snapshots=(
            StockSnapshot(
                sku="CH-616",
                available=4,
                source="catalog",
                as_of=datetime(2026, 8, 3, tzinfo=UTC),
            ),
        ),
        recommendation="CH-616",
    )

    with pytest.raises(ValueError, match="Zoho stock"):
        validate_catalog_decision(decision)


def test_catalog_decision_accepts_complete_constraint_first_plan() -> None:
    decision = CatalogDecision(
        requirements=("seating",),
        selected_lines=(_line(),),
        requested_seats=4,
        budget_cap=2000.0,
        stock_snapshots=(
            StockSnapshot(
                sku="CH-616",
                available=4,
                source="zoho",
                as_of=datetime(2026, 8, 3, tzinfo=UTC),
            ),
        ),
        recommendation="CH-616",
    )

    assert validate_catalog_decision(decision) is decision
