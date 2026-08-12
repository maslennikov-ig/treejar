"""The presentation turn the opening directive never reached (`tj-2m5m.4`)."""

from __future__ import annotations

import pytest

from src.dialogue.claim_contract import (
    consultative_opening_directive,
    earns_consultative_opening,
    earns_solution_consultation,
    solution_consultation_directive,
)


@pytest.mark.parametrize(
    "request_text",
    [
        # S02: two things asked for, one answered.
        "We need workstations and chairs for the new floor.",
        # S08: four turns of bulleted echo and no product ever searched.
        "Twelve people, mixed desk and meeting work, budget is flexible.",
        "مرحباً، نحتاج محطات عمل وكراسي للطابق الجديد.",
    ],
)
def test_the_presentation_turn_earns_the_directive(request_text: str) -> None:
    assert earns_solution_consultation(request_text, sales_stage="solution") is True


@pytest.mark.parametrize(
    "sales_stage",
    ["greeting", "qualifying", "needs_analysis", "company_details", "quoting", ""],
)
def test_no_other_stage_earns_it(sales_stage: str) -> None:
    """One stage, and the opening directive owns the three before it.

    Both firing on the same turn would put two "ask one question" bounds in one
    prompt, which is how a reply becomes an interrogation.
    """

    assert (
        earns_solution_consultation("We need desks", sales_stage=sales_stage) is False
    )


@pytest.mark.parametrize(
    "sales_stage",
    ["greeting", "qualifying", "needs_analysis", "solution"],
)
def test_the_two_directives_never_fire_on_the_same_turn(sales_stage: str) -> None:
    text = "We need workstations and chairs for twelve people."

    assert not (
        earns_consultative_opening(text, sales_stage=sales_stage)
        and earns_solution_consultation(text, sales_stage=sales_stage)
    )


@pytest.mark.parametrize(
    "request_text",
    [
        "Show me only these two, no alternatives and no upsell.",
        "Just the price of the LUMA 9719-4, nothing else.",
        (
            "Please prepare a formal quotation for exactly four CH 616 NEW "
            "black chairs at the current confirmed price."
        ),
        "لا تقترح بدائل، أريد هذا الصنف فقط.",
    ],
)
def test_a_customer_who_has_narrowed_is_left_alone_here_too(request_text: str) -> None:
    """The stand-down is the point, not a special case for the opening.

    S06 and S09 were marked down for not consulting on turns where the customer
    had ruled consultation out. Widening a deliberately narrowed request is
    friction wherever in the conversation it happens.
    """

    assert earns_solution_consultation(request_text, sales_stage="solution") is False


def test_an_empty_turn_earns_nothing() -> None:
    assert earns_solution_consultation("", sales_stage="solution") is False
    assert earns_solution_consultation("   ", sales_stage="solution") is False


def test_the_directive_binds_what_it_may_add() -> None:
    """Three constraints from the issue's design, each stated in the text.

    The loss this repairs is silence. Inventing a service to fill it would be a
    worse answer than the silence was, and no deterministic guard catches an
    invented service that is merely plausible.
    """

    directive = solution_consultation_directive()

    assert "everything they asked for" in directive
    assert "search_products" in directive
    assert "confirmed price and stock" in directive
    assert "leave it out rather than describing it" in directive
    assert "do not add a second one" in directive
    assert "never offer a discount" in directive


def test_it_does_not_repeat_the_opening_directive() -> None:
    """Rule 7 belongs to the opening. Saying what Treejar is at the
    presentation stage is padding, and the two texts must not converge."""

    assert "what Treejar offers" not in solution_consultation_directive()
    assert "search_products" not in consultative_opening_directive()


def test_the_turn_actually_carries_it_into_the_prompt() -> None:
    """A directive nothing appends is a docstring."""

    from src.llm.engine import _turn_runtime_directives

    solution = _turn_runtime_directives(
        "We need workstations and chairs for the new floor.",
        sales_stage="solution",
    )
    qualifying = _turn_runtime_directives(
        "We need workstations and chairs for the new floor.",
        sales_stage="qualifying",
    )
    narrowed = _turn_runtime_directives(
        "Show me only these two, no alternatives and no upsell.",
        sales_stage="solution",
    )

    assert solution_consultation_directive() in solution
    assert solution_consultation_directive() not in qualifying
    assert solution_consultation_directive() not in narrowed
