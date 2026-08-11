from __future__ import annotations

import pytest

from src.llm.money import (
    canonical_amount,
    contains_customer_output_currency,
    find_customer_output_amounts,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (290, "290"),
        ("290.00", "290"),
        ("1,234.500", "1234.5"),
        ("42.4200", "42.42"),
        (None, None),
        ("not-a-number", None),
    ],
)
def test_equivalent_amount_spellings_have_one_canonical_form(
    value: object,
    expected: str | None,
) -> None:
    assert canonical_amount(value) == expected


def test_customer_output_amounts_are_canonical_in_both_existing_orders() -> None:
    text = "AED 1,234.500, 290.00 AED, and 42.4200 درهم."

    assert find_customer_output_amounts(text) == ("1234.5", "290", "42.42")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Prices are quoted in AED.", True),
        ("الأسعار بالدرهم.", True),
        ("No confirmed price is available.", False),
    ],
)
def test_currency_presence_preserves_the_opening_guard_contract(
    text: str,
    expected: bool,
) -> None:
    assert contains_customer_output_currency(text) is expected
