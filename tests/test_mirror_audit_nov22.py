from datetime import UTC, datetime

import pytest

from src.llm.catalog_planning import (
    extract_product_specifications_summary,
    requested_catalog_concepts,
)
from src.llm.company_faq import active_faq_topics
from src.llm.engine import _coerce_inventory_item
from src.llm.escalation_policy import wholesale_handoff_from_history, wholesale_quantity
from src.services.inbound_batch import showroom_clock_context


def test_sunday_and_monday_in_showroom_time() -> None:
    assert "showroom" in active_faq_topics("Are you open today?")
    sunday = showroom_clock_context(datetime(2026, 11, 21, 21, tzinfo=UTC))
    assert "Sunday 2026-11-22" in sunday and "closed all day" in sunday
    monday = showroom_clock_context(datetime(2026, 11, 23, 5, tzinfo=UTC))
    assert "Monday 2026-11-23" in monday and "open now" in monday


def test_waiting_seating_configurations_reach_search() -> None:
    assert "office_sofa" in {
        c.name for c in requested_catalog_concepts("I need a 3-seater upholstered beam")
    }
    attributes = {
        "raw_source": {
            "configurations": [
                {
                    "name": "Seating",
                    "options": [{"label": "1-Seater", "priceModifier": 0}],
                }
            ]
        }
    }
    assert "Seating options: 1-Seater" in extract_product_specifications_summary(
        attributes
    )


@pytest.mark.parametrize(
    ("availability", "expected"),
    [
        ({}, 39),
        ({"available_stock": 22}, 22),
        ({"available_stock": 0}, 0),
        ({"available_stock": 41}, 39),
        ({"available_stock": -1}, 0),
    ],
)
def test_sellable_units_bound_search_and_quote(
    availability: dict, expected: int
) -> None:
    row = {
        "sku": "visitor",
        "stock_on_hand": 39,
        "item_id": "item",
        "rate": 433.33,
        **availability,
    }
    for require_item_id in (True, False):
        item = _coerce_inventory_item(row, require_item_id=require_item_id)
        assert item is not None and item["sellable_units"] == expected
        assert item["stock_on_hand"] == 39


@pytest.mark.parametrize(
    ("text", "minimum"),
    [
        ("I need around 45-50 tables of this size", 45),
        ("25 to 45 conference tables", 25),
        ("15–25 chairs", 15),
        ("8—10 visitor chairs and 12 desks", 20),
        ("NOVO 1400-1600 tables", 0),
        ("140–160 cm desks", 0),
        ("450-500 AED chairs", 0),
    ],
)
def test_bulk_ranges_use_the_lower_quantity(text: str, minimum: int) -> None:
    assert wholesale_quantity(text) == minimum
    decision = wholesale_handoff_from_history("Walnut please", [f"user: {text}"])
    assert decision.allowed == (minimum >= 20)
