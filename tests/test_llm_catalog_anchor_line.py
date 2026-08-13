"""The opening price anchor, and the one place its rules are written down.

`catalog_anchor_line` asks the database for the cheapest orderable row in each
of the two families a customer names first. The measured round has no database
and must still send the opening production sends, so the rules -- the families,
the stock floor, the wording -- live in one pure function that both callers
use. `tj-rdqc`.
"""

from __future__ import annotations

import pytest

from src.llm.catalog_planning import (
    _ANCHOR_FAMILIES,
    _ANCHOR_MIN_STOCK,
    anchor_line_from_catalog_rows,
)

# Shapes taken from the catalog: an orderable chair, an orderable desk, a
# single leftover unit, a free row, and something in neither family.
ROWS: tuple[tuple[str, float | None, int | None], ...] = (
    ("CH 616 NEW black mesh chair", 295.0, 36),
    ("Executive chair, leather", 140.0, 12),
    ("Last chair in the corner", 58.0, 1),
    ("Bench workstation, 4 seats", 1813.0, 8),
    ("Standing desk", 2400.0, 5),
    ("Display sample desk", 0.0, 40),
    ("Meeting room rug", 90.0, 60),
)


def test_the_anchor_names_the_cheapest_orderable_row_in_each_family() -> None:
    assert (
        anchor_line_from_catalog_rows(ROWS, language="en")
        == "Chairs from AED 140, desks and workstations from AED 1,813."
    )


def test_the_anchor_follows_the_customers_language() -> None:
    line = anchor_line_from_catalog_rows(ROWS, language="ar")

    assert line is not None
    assert "الكراسي من 140 درهم" in line
    assert "المكاتب ومحطات العمل من 1,813 درهم" in line


@pytest.mark.parametrize(
    "rows",
    [
        (),
        (("Meeting room rug", 90.0, 60),),
        # A single leftover unit is true and not orderable, which is the whole
        # reason for the stock floor.
        (("Last chair in the corner", 58.0, _ANCHOR_MIN_STOCK - 1),),
        (("Chair with no price", None, 40),),
        (("Chair with no stock figure", 295.0, None),),
    ],
)
def test_a_catalog_that_cannot_answer_gets_no_invented_anchor(
    rows: tuple[tuple[str, float | None, int | None], ...],
) -> None:
    """No fallback text with a number in it: the reply goes out without one."""

    assert anchor_line_from_catalog_rows(rows, language="en") is None


def test_both_families_are_read_from_the_one_declaration() -> None:
    """A family added to `_ANCHOR_FAMILIES` must reach the pure function too."""

    for _family, terms, label_en, _label_ar in _ANCHOR_FAMILIES:
        rows = ((f"A {terms[0]} for the office", 700.0, 40),)

        assert anchor_line_from_catalog_rows(rows, language="en") == (
            f"{label_en} from AED 700."
        )
