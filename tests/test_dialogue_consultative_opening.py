"""The three sentences Noor never says.

Measured on 2026-08-07 by scoring all ten stored acceptance transcripts
criterion by criterion. Rule 7, Treejar's value proposition: zero in ten of
ten. Rule 13, asking what the customer's company does: zero in five of five
where it applies. Rule 6, a compliment or thanks: four of a possible twenty.
Rules 1 and 2, the greeting and the introduction, are a perfect twenty of
twenty — so this is not a bot that cannot open a conversation. It is one that
opens it and then never says why the customer should care, never asks who they
are, and rarely thanks them.

Like the sizing and comparison directives beside it, these tests are about the
**customer request** and the typed stage, never the reply text: a lexical
backstop over generated text is on the specification's rejected list.
"""

from __future__ import annotations

import pytest

from src.dialogue.claim_contract import (
    consultative_opening_directive,
    earns_consultative_opening,
)

# --- the trigger ------------------------------------------------------------


@pytest.mark.parametrize(
    "request_text",
    [
        # The opening turns of the stored scenarios, as the customer sent them.
        "Hi! We are furnishing a new office and I need help choosing furniture.",
        "We need chairs for twelve call-center staff below AED 400 each.",
        "Do you sell laboratory fume hoods and chemical-resistant lab benches?",
        # And the reply to the name gate, which carries no request at all and is
        # exactly where the value proposition and the company question belong.
        "My name is Maya, and I am the facilities manager at Cedarline Test.",
        "My name is Samir.",
        "مرحباً، نجهز مكتباً في دبي لستة موظفين ونحتاج محطات عمل خاصة.",
    ],
)
def test_a_turn_that_is_still_building_the_sale_earns_the_directive(
    request_text: str,
) -> None:
    assert earns_consultative_opening(request_text, sales_stage="qualifying") is True


@pytest.mark.parametrize(
    "sales_stage",
    ["greeting", "qualifying", "needs_analysis"],
)
def test_every_early_stage_earns_it(sales_stage: str) -> None:
    assert earns_consultative_opening("We need desks", sales_stage=sales_stage) is True


@pytest.mark.parametrize(
    "sales_stage",
    ["solution", "company_details", "quoting", "closing", "feedback", "", "unknown"],
)
def test_a_conversation_past_the_opening_does_not_earn_it(sales_stage: str) -> None:
    """Rule 7 belongs to the opening. Repeating what Treejar is at the quoting
    stage is not selling, it is padding."""

    assert earns_consultative_opening("We need desks", sales_stage=sales_stage) is False


@pytest.mark.parametrize(
    "request_text",
    [
        # S06: one exact SKU, no alternatives, no quotation.
        (
            "Please check the exact live price and stock for SKU CH 616 NEW "
            "black. I may need twelve units, but I do not want a quotation."
        ),
        (
            "Confirm from live inventory whether twelve units of that exact "
            "SKU are available and state the unit price. Do not suggest "
            "alternatives or offer a quotation."
        ),
        # S09: a quotation for an exact quantity at a confirmed price.
        (
            "Please prepare a formal quotation for exactly four CH 616 NEW "
            "black chairs at the current confirmed price."
        ),
        "Show me only these two, no alternatives and no upsell.",
        "Just the price of the LUMA 9719-4, nothing else.",
        "لا تقترح بدائل، أريد هذا الصنف فقط.",
    ],
)
def test_a_customer_who_has_narrowed_the_request_is_left_alone(
    request_text: str,
) -> None:
    """S06 and S09 are the reason this half exists.

    Both were marked down by the checklist for not consulting on turns where
    the customer had ruled consultation out. The answer to that is not to
    consult anyway; it is `tj-swgu.11` on the scoring side and this stand-down
    on the dialogue side.
    """

    assert earns_consultative_opening(request_text, sales_stage="qualifying") is False


def test_an_empty_turn_earns_nothing() -> None:
    """Same as the two detectors beside it: no text, no directive."""

    assert earns_consultative_opening("", sales_stage="qualifying") is False
    assert earns_consultative_opening("   ", sales_stage="qualifying") is False


# --- the directive ----------------------------------------------------------


def test_the_directive_names_the_three_moves_that_scored_zero() -> None:
    directive = consultative_opening_directive()
    lowered = directive.casefold()

    # Rule 7, zero in ten of ten.
    assert "treejar is" in lowered
    assert "one short clause" in lowered
    # Rule 6, four of twenty.
    assert "thank" in lowered
    # Rule 13, zero in five of five where it applies.
    assert "what their company does" in lowered


def test_the_directive_bounds_itself_against_the_reply_it_shares_a_turn_with() -> None:
    """Two directives can fire on one turn, and both want a question. Without
    this bound the customer gets an interrogation instead of an answer."""

    lowered = consultative_opening_directive().casefold()

    assert "at most one question" in lowered
    assert "before answering" in lowered


def test_the_directive_unlocks_no_fact_and_no_commercial_term() -> None:
    """Rule 11 wants an incentive and stays at zero on purpose: a discount is a
    commitment nobody has authorised. The sibling comparison directive forbids
    one in the same words."""

    lowered = consultative_opening_directive().casefold()

    assert "never offer a discount or a bonus" in lowered
    assert "you have not verified" in lowered


def test_the_directive_does_not_grow_the_product_system_prompt() -> None:
    assert len(consultative_opening_directive()) < 900
