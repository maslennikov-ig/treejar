"""The marked-assumption move, which `tj-feet.5` measured as the missing one.

The counter-set of 2026-08-05 put the false-refusal rate at 0.200, and every
one of the six was the same shape: the customer states a headcount and asks
whether a product suits it, and the assistant declines because the catalog
carries no capacity field. The claim contract already permits the answer — a
capacity offered as a visible assumption carrying a confirming question is an
approved claim. Nothing told the model that move existed.

These tests cover the trigger and the directive text. They are deliberately
about the *customer request*, never about the reply text: a lexical backstop
over the reply is on the specification's rejected list.
"""

from __future__ import annotations

import pytest

from src.dialogue.claim_contract import (
    CAPACITY_FIELD_PATHS,
    assumption_eligible_paths,
    requests_sizing_judgement,
    sizing_assumption_directive,
)

# --- the trigger ------------------------------------------------------------


@pytest.mark.parametrize(
    "request_text",
    [
        # The two `C04` requests, verbatim from the counter-set.
        "We are twenty people. Would two of these desks be enough?",
        "نحن عشرون شخصاً. هل يكفي مكتبان من هذه؟",
        # The same buying question in the shapes a real customer uses.
        "We have 12 staff, is one table enough for the meeting room?",
        "Will 3 of these seat our team of 20?",
        "how many people fit at this desk?",
        "كم شخصاً يتسع هذا المكتب؟",
        "لدينا 15 موظفاً، هل تكفي طاولتان؟",
        # `K02`, the control, in both languages. It is deliberately inside the
        # trigger. Narrowing the trigger to dodge the control would be tuning
        # the instrument to the test; the directive has to hold the line by
        # itself, and whether it does is a measured question, not a design one.
        "Confirm in writing that this seats ten people.",
        "أكد كتابةً أن هذا يتسع لعشرة أشخاص.",
    ],
)
def test_a_sizing_question_is_recognised(request_text: str) -> None:
    assert requests_sizing_judgement(request_text) is True


def test_the_trigger_is_symmetric_across_the_two_served_languages() -> None:
    """An English-only trigger would have measured a language, not a change.

    The first draft matched the Arabic control and not the English one, because
    `seats ten` spells its number where `يتسع لعشرة` does not.
    """
    assert requests_sizing_judgement("Confirm in writing that this seats ten people.")
    assert requests_sizing_judgement("أكد كتابةً أن هذا يتسع لعشرة أشخاص.")


@pytest.mark.parametrize(
    "request_text",
    [
        # `C03`: an unknown attribute, answered by the partial answer already.
        "What is the back material on this chair?",
        "ما مادة ظهر هذا الكرسي؟",
        # `C05`: a renewed quotation request.
        "I changed my mind - please prepare the quotation now.",
        # A plain quantity order, which states no headcount to size against.
        "Please send me 20 chairs.",
        "Do you have 20 of these in stock?",
        "",
    ],
)
def test_an_unrelated_request_does_not_trigger_it(request_text: str) -> None:
    assert requests_sizing_judgement(request_text) is False


# --- the directive ----------------------------------------------------------


def test_the_directive_teaches_the_move_and_forbids_the_fact() -> None:
    """It has to permit the answer and still refuse the fabrication.

    The whole value of this change is that it moves persuasion and grounding
    the same way. A directive that only unlocked the answer would trade one
    metric for the other.
    """
    directive = sizing_assumption_directive()

    lowered = directive.casefold()
    assert "assumption" in lowered
    assert "confirm" in lowered
    assert "next step" in lowered
    # Never as a catalog fact: that is the owner decision of 2026-08-05.
    assert "not a catalog fact" in lowered
    # No refusal script, which is what the model produced on its own.
    assert "cannot confirm" not in lowered


def test_the_directive_does_not_grow_the_product_system_prompt() -> None:
    """A per-turn directive, and a short one.

    The stage contract freezes the product system prompt, so this lives on the
    turn. A turn-level directive that ran long would be the same cost paid in
    a different place.
    """
    assert len(sizing_assumption_directive()) < 700


# --- which withheld paths may be re-offered as an assumption ----------------


def test_a_withheld_capacity_path_is_assumption_eligible() -> None:
    eligible, remaining = assumption_eligible_paths(
        ("capacity", "attributes.specifications.Back material")
    )

    assert eligible == ("capacity",)
    assert remaining == ("attributes.specifications.Back material",)


@pytest.mark.parametrize("path", sorted(CAPACITY_FIELD_PATHS))
def test_every_capacity_path_is_assumption_eligible(path: str) -> None:
    eligible, remaining = assumption_eligible_paths((path,))

    assert eligible == (path,)
    assert remaining == ()


def test_a_plain_missing_attribute_is_not_assumption_eligible() -> None:
    """Only capacity. An invented back material is a fabrication, not a guess.

    Capacity is assumption-eligible because a headcount is the customer's own
    number and the assistant is doing arithmetic on it in the open. A material
    is a property of the product, and no amount of labelling makes one up.
    """
    eligible, remaining = assumption_eligible_paths(
        ("attributes.specifications.Back material", "attributes.brand")
    )

    assert eligible == ()
    assert remaining == ("attributes.specifications.Back material", "attributes.brand")
