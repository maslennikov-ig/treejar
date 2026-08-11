from __future__ import annotations

import ast
import pathlib
import re

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


def test_no_currency_pattern_is_written_anywhere_but_this_module() -> None:
    """`tj-rt7w.12`. Four vocabularies is a decision; four files is an accident.

    The spellings still differ, on purpose -- a budget read from a customer and
    a price we wrote ourselves are different questions. What the audit measured
    as a defect was that the divergence lived in four modules, so nobody could
    see it or say whether it was meant.

    Read through the AST rather than line by line: the pattern this test was
    written to catch spans two lines, and a line-wise version missed it.
    """
    llm = pathlib.Path(__file__).parents[1] / "src" / "llm"
    currency = re.compile(r"aed|dirhams?|\bdhs\b|درهم|د\\?\.إ", re.IGNORECASE)

    # One pattern names two currency words and is not about money: it lists
    # the tokens that mean "the number before me was a unit, not a quantity"
    # -- minutes, cm, aed, usd. Its vocabulary is a third distinct set and it
    # knows `usd`, which money.py does not. Named here so the exception is
    # reviewed rather than assumed.
    not_about_money = {"_SELECTION_MEASUREMENT_SUFFIX_RE"}

    offenders: list[str] = []
    for path in sorted(llm.glob("*.py")):
        if path.name == "money.py":
            continue
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        exempt = {
            id(assignment.value)
            for assignment in ast.walk(tree)
            if isinstance(assignment, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id in not_about_money
                for target in assignment.targets
            )
        }
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or id(node) in exempt:
                continue
            function = node.func
            compiled = (
                isinstance(function, ast.Attribute)
                and function.attr == "compile"
                and isinstance(function.value, ast.Name)
                and function.value.id == "re"
            )
            if not compiled or not node.args:
                continue
            written = ast.get_source_segment(source, node.args[0]) or ""
            # An f-string placeholder naming a money.py constant is the point,
            # not a violation, and BUDGET_AED_CURRENCY_PATTERN contains "AED".
            written = re.sub(r"\{[^{}]*\}", "", written)
            if currency.search(written):
                offenders.append(f"{path.name}:{node.lineno}")

    assert not offenders, (
        f"currency patterns still written outside money.py: {offenders}"
    )
