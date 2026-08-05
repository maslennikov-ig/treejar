"""Fixture integrity regressions for the core hard battle cases (tj-feet.7).

Three defects found while re-checking the critical failures of the 2026-08-05
sealed round by hand:

* `S01` demanded an explanation of coverage and supplied no desk capacity, so
  silence and assumption were both punished;
* `S04` asserted in its system prompt that verified catalog facts had been
  received and supplied not one attribute, with no lookup tool to obtain any;
* `DK-4` implied ten seats in `S01` and was described as a four-person desk in
  `S05`.

These tests keep all three closed. They assert fixture properties, not model
behaviour, so they cost nothing to run and fail loudly if a future edit
reintroduces a trap.
"""

from __future__ import annotations

import json
import re
from typing import Any

import pytest
from scripts.model_battle import build_sales_grounding_numbers
from scripts.model_battle_cases import CORE_HARD_CASES

_CASES = {case.case_id: case for case in CORE_HARD_CASES}
_SEAT_TOKEN_RE = re.compile(
    r"([0-9]{1,2})\s*-?\s*(?:seat|seats|seater|person|persons|people|pax)\b",
    re.IGNORECASE,
)


def _catalog_products(case_id: str) -> list[dict[str, Any]]:
    results = _CASES[case_id].tool_results.get("search_catalog", {})
    products = results.get("products", [])
    assert isinstance(products, list)
    return products


def _product(case_id: str, sku: str) -> dict[str, Any]:
    for product in _catalog_products(case_id):
        if product.get("sku") == sku:
            return product
    raise AssertionError(f"{case_id} has no {sku} row")


def _case_evidence(case_id: str) -> str:
    case = _CASES[case_id]
    return json.dumps(
        {
            "system_prompt": case.system_prompt,
            "conversation": case.conversation,
            "user_prompt": case.user_prompt,
            "tool_results": case.tool_results,
        },
        ensure_ascii=False,
    )


def test_s01_supplies_the_capacity_it_demands_an_explanation_of() -> None:
    assert "coverage" in _CASES["S01"].system_prompt.casefold()
    for sku in ("AX-E1", "DK-4"):
        assert isinstance(_product("S01", sku)["seats_per_unit"], int)


@pytest.mark.parametrize(("case_id", "people"), [("S01", 20), ("S05", 12)])
def test_every_seating_family_covers_the_whole_team(case_id: str, people: int) -> None:
    """Each family serves the same people, so coverage is per family, not a sum.

    Twenty chairs seat twenty; five four-person desks also serve twenty. Adding
    the two would claim forty, which is the arithmetic that made the original
    fixture unanswerable.
    """
    covered = {
        str(product["sku"]): product["quantity"] * product["seats_per_unit"]
        for product in _catalog_products(case_id)
        if "seats_per_unit" in product
    }

    assert covered and set(covered.values()) == {people}
    assert _CASES[case_id].tool_results["search_catalog"]["covered_seats"] == people


@pytest.mark.parametrize(
    ("case_id", "budget_aed"),
    [("S01", 30000), ("S05", 20000)],
)
def test_stated_total_matches_the_lines_and_fits_the_budget(
    case_id: str, budget_aed: int
) -> None:
    products = _catalog_products(case_id)
    total = sum(
        product["quantity"] * (product.get("price_aed") or product["unit_price_aed"])
        for product in products
    )

    assert total == _CASES[case_id].tool_results["search_catalog"]["total_aed"]
    assert total <= budget_aed


def test_dk4_capacity_is_consistent_across_every_fixture_that_names_it() -> None:
    capacities = {
        case_id: _product(case_id, "DK-4")["seats_per_unit"]
        for case_id in ("S01", "S05")
    }

    assert set(capacities.values()) == {4}


def test_the_same_sku_never_carries_two_prices() -> None:
    prices: dict[str, set[int]] = {}
    for case_id in ("S01", "S05"):
        for product in _catalog_products(case_id):
            price = product.get("price_aed") or product.get("unit_price_aed")
            if price is not None:
                prices.setdefault(str(product["sku"]), set()).add(int(price))

    conflicting = {sku: found for sku, found in prices.items() if len(found) > 1}
    assert conflicting == {}


@pytest.mark.parametrize("case_id", ["S01", "S05"])
def test_no_fixture_states_two_different_seat_counts(case_id: str) -> None:
    """The production form of this defect is tj-2pkk; do not reproduce it here."""
    found = {
        match.group(1) for match in _SEAT_TOKEN_RE.finditer(_case_evidence(case_id))
    }

    assert len(found) <= 1, f"{case_id} states seat counts {sorted(found)}"


def test_s04_supplies_the_attributes_it_claims_were_received() -> None:
    case = _CASES["S04"]
    assert "verified catalog facts" in case.system_prompt.casefold()

    evidence = " ".join(turn["content"] for turn in case.conversation)
    for field_path in (
        "specifications.Mechanism",
        "specifications.Upholstery",
        "specifications.Adjustable Armrest",
        "specifications.Warranty",
    ):
        assert field_path in evidence


def test_s04_still_tests_the_consent_gate() -> None:
    case = _CASES["S04"]

    assert case.category == "quote_consent_gate"
    assert "no quotation" in case.user_prompt.casefold()
    assert case.tool_results["prepare_quote_draft"] == {
        "status": "forbidden_without_explicit_consent"
    }


def test_no_fixture_requires_a_number_its_own_evidence_cannot_support() -> None:
    """The trap S01 set: demand a figure the scenario never makes reachable.

    Non-numeric required phrases are judgments the reply has to make, so only
    the numbers are checked, against the same grounding set the scorer uses.
    """
    ungrounded: dict[str, list[str]] = {}
    for case in CORE_HARD_CASES:
        grounded = build_sales_grounding_numbers(case)
        absent = [
            phrase
            for phrase in case.required_phrases
            if phrase.replace(",", "").isdigit()
            and phrase.replace(",", "") not in grounded
        ]
        if absent:
            ungrounded[case.case_id] = absent

    assert ungrounded == {}, ungrounded
