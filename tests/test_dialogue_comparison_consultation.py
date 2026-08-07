"""The consultative move S04 was missing.

On 2026-08-07 S04 scored 14.6 with no template involved and no wrong action.
The bot compared exactly the two items it was asked to compare, recommended
one, and stopped. No acknowledgement of the design team it was buying for, no
mention of what else that workspace needs, no clarifying question. It is the
same failure as the deterministic templates arrived at from the other side:
correct, and not selling.

Like the sizing directive next to it, these tests are about the **customer
request**, never the reply text: a lexical backstop over generated text is on
the specification's rejected list.
"""

from __future__ import annotations

import pytest

from src.dialogue.claim_contract import (
    comparison_consultation_directive,
    requests_product_comparison,
)

# --- the trigger ------------------------------------------------------------


@pytest.mark.parametrize(
    "request_text",
    [
        # The two S04 turns, in the shape the customer sent them.
        (
            "Hello, my name is Nadia. Compare the current four-person LUMA "
            "workstation with the four-person NOVO setup for our design team."
        ),
        (
            "Compare privacy, collaboration, footprint, current price and "
            "stock, then recommend one for four designers."
        ),
        "What is the difference between the LUMA 9719-4 and the NOVO 2400?",
        "LUMA vs NOVO for a six-person team?",
        "Which one is better for an open-plan office, the pods or the booths?",
        "قارن بين محطة عمل لوما ومحطة نوفو لأربعة أشخاص.",
    ],
)
def test_a_direct_comparison_earns_the_consultative_directive(
    request_text: str,
) -> None:
    assert requests_product_comparison(request_text) is True


@pytest.mark.parametrize(
    "request_text",
    [
        # No comparison at all.
        "What is the price of the LUMA 9719-4?",
        "Please prepare a quotation for 12 CH 616 chairs.",
        "",
        # The customer has ruled out exactly what the directive would invite.
        (
            "Compare the two chairs but show me only those two, no "
            "alternatives and no upsell."
        ),
        "Just compare these two and nothing else, please.",
    ],
)
def test_a_turn_that_forbids_the_move_does_not_earn_it(request_text: str) -> None:
    """S06 is the reason for the second half of this list.

    That customer asked for one exact SKU with no alternatives and no
    quotation, and was marked down by the checklist for not consulting. The
    answer to that is not to consult anyway.
    """

    assert requests_product_comparison(request_text) is False


# --- the directive ----------------------------------------------------------


def test_the_directive_asks_for_the_sale_without_unlocking_a_fact() -> None:
    directive = comparison_consultation_directive()
    lowered = directive.casefold()

    # Answer the comparison first: the customer asked a question.
    assert "comparison" in lowered
    assert "recommend" in lowered
    # The three things the evaluator found missing.
    assert "acknowledge" in lowered
    assert "complete" in lowered
    assert "one question" in lowered or "one short question" in lowered
    # And nothing that would invent a fact or a discount to do it.
    assert "search_products" in lowered
    assert "discount" in lowered


def test_the_directive_does_not_grow_the_product_system_prompt() -> None:
    assert len(comparison_consultation_directive()) < 900
