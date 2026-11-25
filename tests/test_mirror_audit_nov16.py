"""Regression suite for tj-kddn: Nikita Nov 16 / Noor mirror audit fixes.

Covers 5 structural classes uncovered during Nikita Nov 16 shift QA audit and Nov 15/17 router blackout dialogues:
1. _follows_a_model_name falsely dropped bulk quantities preceded by uppercase words (I NEED 100 PCS, WE NEED 50 CHAIRS) or non-model series words (exact model 100pcs in *2280).
2. _BULK_ITEM_EN only matched pcs, missing singular pc (*2482: Around 40 pc).
3. _WHOLESALE_PRICING_RE missed whole sell, whole seller, whole sale (*2482).
4. _CUSTOM_MADE_TO_ORDER_RE missed custom shape/dimension descriptors (custom triangle table in *3375).
5. FAQ Q26, Rule 14, and canonical seed clarify Treejar does not supply residential beds / double beds / bedroom furniture (*2039).
"""

from __future__ import annotations

import pytest

from src.llm.escalation_policy import (
    b2b_handoff_decision,
    critical_escalation_decision,
    wholesale_quantity,
)
from src.llm.prompts import BASE_SYSTEM_PROMPT
from src.services.canonical_admin_seed import canonical_kb_articles


@pytest.mark.parametrize(
    ("text", "expected_qty"),
    [
        ("My client need this chair exact model 100pcs", 100),
        ("exact model 100pcs", 100),
        ("this model 50 pcs", 50),
        ("I NEED 100 PCS", 100),
        ("WE NEED 50 CHAIRS", 50),
        ("PLEASE ORDER 30 DESKS", 30),
        ("WANT 25 WORKSTATIONS", 25),
        ("CH 970 100 pcs", 100),
    ],
)
def test_exact_model_and_uppercase_bulk_quantity_escalates(
    text: str, expected_qty: int
) -> None:
    assert wholesale_quantity(text) == expected_qty
    decision = b2b_handoff_decision(text)
    assert decision.allowed is True
    assert decision.trigger == "wholesale_or_bulk_project"
    crit = critical_escalation_decision(customer_text=text)
    assert crit.allowed is True


@pytest.mark.parametrize(
    ("text", "expected_qty"),
    [
        ("Around 40 pc", 40),
        ("20 pc", 20),
        ("I need 25 pc of office chairs", 25),
        ("30 pc desks", 30),
    ],
)
def test_singular_pc_unit_triggers_wholesale_escalation(
    text: str, expected_qty: int
) -> None:
    assert wholesale_quantity(text) == expected_qty
    decision = b2b_handoff_decision(text)
    assert decision.allowed is True
    assert decision.trigger == "wholesale_or_bulk_project"
    crit = critical_escalation_decision(customer_text=text)
    assert crit.allowed is True


@pytest.mark.parametrize(
    "text",
    [
        "Give me whole sell price",
        "If you are Whole seller i Will continue with you",
        "Whole sell",
        "Do you offer whole sell rates?",
        "Please share whole sale pricelist",
        "CH 240 M Black, qty 6. Quote me best price for reselling.",
        "Could you confirm reseller pricing on six chairs?",
    ],
)
def test_wholesale_pricing_spelling_variants_trigger_b2b_handoff(text: str) -> None:
    decision = b2b_handoff_decision(text)
    assert decision.allowed is True
    assert decision.trigger == "wholesale_or_bulk_project"


def test_reseller_request_needs_explicit_trade_pricing() -> None:
    assert not b2b_handoff_decision("I resell furniture. I need six chairs.").allowed


@pytest.mark.parametrize(
    "text",
    [
        "Is it possible to make custom triangle table?",
        "custom triangle table",
        "Can you build a custom shape desk?",
        "custom sized conference table",
        "custom L-shape workstation",
    ],
)
def test_custom_shapes_and_modifiers_trigger_made_to_order_handoff(text: str) -> None:
    decision = b2b_handoff_decision(text)
    assert decision.allowed is True
    assert decision.trigger == "custom_made_to_order"


@pytest.mark.parametrize(
    "text",
    [
        "NOVO 2400 tables",
        "RAYA 1600 desk",
        "Is the 2400 mm NOVO table available?",
        "EVOQ 2200 table",
    ],
)
def test_catalog_series_dimensions_are_not_confused_with_bulk_quantities(
    text: str,
) -> None:
    assert wholesale_quantity(text) == 0
    decision = b2b_handoff_decision(text)
    assert decision.allowed is False


def test_residential_beds_boundary_in_faq_and_prompts() -> None:
    # Rule 14 in BASE_SYSTEM_PROMPT
    assert "residential beds / bedroom furniture" in BASE_SYSTEM_PROMPT
    assert "double beds, mattresses, or bedroom wardrobes" in BASE_SYSTEM_PROMPT

    # Canonical KB articles
    kb = canonical_kb_articles()
    faq26 = next(a for a in kb if "FAQ: Do you sell petty cash boxes" in a.title)
    assert "residential beds / bedroom furniture" in faq26.content.lower()

    prod_cat = next(a for a in kb if a.title == "Product categories Treejar supplies")
    assert "residential beds" in prod_cat.content.lower()
