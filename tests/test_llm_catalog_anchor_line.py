"""The opening price anchor, and the one place its rules are written down.

`catalog_anchor_line` asks the database for the cheapest orderable row in each
of the two families a customer names first. The measured round has no database
and must still send the opening production sends, so the rules -- the families,
the stock floor, the wording -- live in one pure function that both callers
use. `tj-rdqc`.
"""

from __future__ import annotations

import pytest

from src.llm import catalog_planning
from src.llm.catalog_planning import (
    _ANCHOR_FAMILIES,
    _ANCHOR_MIN_STOCK,
    AnchorCatalogRow,
    anchor_line_from_catalog_rows,
    opening_wants_a_price_anchor,
)


def _row(
    name: str,
    price: float | None,
    stock: int | None,
    *,
    category: str | None = None,
    subcategory: str | None = None,
) -> AnchorCatalogRow:
    return AnchorCatalogRow(
        name=name,
        category=category,
        subcategory=subcategory,
        price=price,
        stock=stock,
    )


# Shapes taken from the catalog: an in-stock chair, an in-stock workstation, a
# single available unit, a free row, and something in neither family.
ROWS: tuple[AnchorCatalogRow, ...] = (
    _row("CH 616 NEW black mesh chair", 295.0, 36, category="Chairs"),
    _row("Executive chair, leather", 140.0, 12, category="Chairs"),
    _row("Last chair in the corner", 58.0, 1, category="Chairs"),
    _row("Bench workstation, 4 seats", 1813.0, 8, category="Workstation"),
    _row("Standing desk", 2400.0, 5, category="Desks & Tables", subcategory="Table"),
    _row("Display sample desk", 0.0, 40, category="Desks & Tables"),
    _row("Meeting room rug", 90.0, 60, category="Accessories"),
)


def test_the_anchor_names_the_cheapest_orderable_row_in_each_family() -> None:
    assert (
        anchor_line_from_catalog_rows(ROWS, language="en")
        == "Chairs from AED 58, desks and workstations from AED 1,813."
    )


def test_the_anchor_follows_the_customers_language() -> None:
    line = anchor_line_from_catalog_rows(ROWS, language="ar")

    assert line is not None
    assert "الكراسي من 58 درهم" in line
    assert "المكاتب ومحطات العمل من 1,813 درهم" in line


def test_the_arabic_anchor_separates_its_clauses_in_arabic() -> None:
    """`tj-b8il`. A Latin comma inside otherwise correct Arabic."""

    arabic = anchor_line_from_catalog_rows(ROWS, language="ar")
    english = anchor_line_from_catalog_rows(ROWS, language="en")

    assert arabic is not None and english is not None
    assert "، " in arabic
    assert ", " not in arabic
    assert ", " in english
    assert "، " not in english


@pytest.mark.parametrize(
    "rows",
    [
        (),
        (_row("Meeting room rug", 90.0, 60, category="Accessories"),),
        (_row("Out-of-stock chair", 58.0, _ANCHOR_MIN_STOCK - 1),),
        (_row("Chair with no price", None, 40, category="Chairs"),),
        (_row("Chair with no stock figure", 295.0, None, category="Chairs"),),
    ],
)
def test_a_catalog_that_cannot_answer_gets_no_invented_anchor(
    rows: tuple[AnchorCatalogRow, ...],
) -> None:
    """No fallback text with a number in it: the reply goes out without one."""

    assert anchor_line_from_catalog_rows(rows, language="en") is None


def test_one_available_unit_is_a_real_anchor_floor() -> None:
    """Owner decision 2026-08-14: one customer can buy one available item."""

    rows = (_row("Last chair in the corner", 58.0, 1, category="Chairs"),)

    assert anchor_line_from_catalog_rows(rows, language="en") == ("Chairs from AED 58.")


def test_the_anchor_result_carries_whether_its_floor_is_limited() -> None:
    """The renderer needs state, not a guess from the formatted price line."""

    anchor = catalog_planning.catalog_anchor_from_catalog_rows(ROWS, language="en")

    assert anchor is not None
    assert anchor.line == "Chairs from AED 58, desks and workstations from AED 1,813."
    assert anchor.has_limited_stock is True
    assert anchor.grounded_amounts == (58.0, 1813.0)


def test_fractional_floor_uses_the_same_approved_rounding_in_text_and_evidence() -> (
    None
):
    """Owner decision 2026-08-14: a whole-AED `from` floor may round fils."""

    anchor = catalog_planning.catalog_anchor_from_catalog_rows(
        (_row("Task desk", 58.48, 1, category="Desks"),),
        language="en",
    )

    assert anchor is not None
    assert anchor.line == "desks and workstations from AED 58."
    assert anchor.grounded_amounts == (58.0,)


def test_both_families_are_read_from_the_one_declaration() -> None:
    """A family added to `_ANCHOR_FAMILIES` must reach the pure function too."""

    for family in _ANCHOR_FAMILIES:
        rows = (
            _row(
                f"A {family.name_terms[0]} for the office",
                700.0,
                40,
                category=family.taxonomy_terms[0],
            ),
        )

        assert anchor_line_from_catalog_rows(rows, language="en") == (
            f"{family.label_en} from AED 700."
        )


# `tj-3jo0`. Three rows whose names carry a family term and whose catalog
# taxonomy says they are something else. Each one of them headed the anchor
# before the taxonomy had to agree, and the pedestal did it in production.
def test_a_storage_pedestal_does_not_price_the_desks() -> None:
    rows = (
        _row(
            "Desk height pedestal, SIMPLE, SC-3D.1A",
            154.23,
            7,
            category="Storage",
            subcategory="Pedestal",
        ),
        _row(
            "Single workstation SKYLAND LUMA 9719-1",
            491.0,
            9,
            category="Workstation",
        ),
    )

    assert anchor_line_from_catalog_rows(rows, language="en") == (
        "desks and workstations from AED 491."
    )


def test_a_workstation_chair_is_counted_once_and_as_a_chair() -> None:
    rows = (
        _row(
            "SkyLand Workstation Chair CH 630 black",
            262.0,
            20,
            category="Chairs",
            subcategory="Workstation Chair",
        ),
        _row(
            "Single workstation SKYLAND LUMA 9719-1",
            491.0,
            9,
            category="Workstation",
        ),
    )

    assert anchor_line_from_catalog_rows(rows, language="en") == (
        "Chairs from AED 262, desks and workstations from AED 491."
    )


def test_an_accessory_named_after_a_family_is_not_in_it() -> None:
    rows = (
        _row("Desk mat, felt, 800x400", 39.0, 60, category="Accessories"),
        _row(
            "Single workstation SKYLAND LUMA 9719-1",
            491.0,
            9,
            category="Workstation",
        ),
    )

    assert anchor_line_from_catalog_rows(rows, language="en") == (
        "desks and workstations from AED 491."
    )


# `tj-7vhq`. The anchor is a price offered before the customer asks, which is
# right on a bare greeting and wrong on a message about something else.
@pytest.mark.parametrize(
    "opening",
    [
        "Hello",
        "مرحبا",
        "?",
        "How much are your prices?",
        "Do you have executive chairs in stock?",
        "أحتاج مكاتب لمكتب جديد",
        # An off-topic marker beside a named item is still a furniture message.
        "We are hiring, and we also need 20 chairs for the new floor.",
    ],
)
def test_an_opening_that_may_be_about_furniture_is_priced(opening: str) -> None:
    assert opening_wants_a_price_anchor(opening) is True


@pytest.mark.parametrize(
    "opening",
    [
        "Good morning, please find my CV attached. My salary expectation is 6000 AED.",
        "I am looking for a job in your company, I have 5 years in furniture sales.",
        "Your shipment has been dispatched, tracking number 7781234.",
        "مرحبا، أرغب بالتقديم على وظيفة لديكم وأرفق سيرة ذاتية.",
        "We offer digital marketing and SEO for your website, business proposal "
        "attached.",
    ],
)
def test_an_opening_that_carries_no_furniture_need_is_not_priced(opening: str) -> None:
    assert opening_wants_a_price_anchor(opening) is False
