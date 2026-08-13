"""Declarations distinguish covered replacements from unreviewed removals."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from src.llm.response_policy import (
    RESPONSE_GUARD_DECLARATIONS,
    GuardMode,
    ReplyPolicyState,
    apply_declared_guard,
    apply_first_turn_opening_guard,
    guard_premature_quote_detail_collection,
    render_reply,
    repair_closed_questions,
)
from src.llm.sales_turn_guard import commit_to_what_you_deferred, only_asks_were_dropped

EXPECTED_MODES = {
    "closed_question": GuardMode.REPLACING,
    "premature_quote_details": GuardMode.REPLACING,
    "first_turn_opening": GuardMode.REPLACING,
    "question_form": GuardMode.REDUCING,
    "name_chase": GuardMode.REDUCING,
    "company_question": GuardMode.REPLACING,
    "deferred_commitment": GuardMode.REPLACING,
    "grounding_output": GuardMode.REMOVING,
}


def test_every_customer_text_guard_has_one_explained_declaration() -> None:
    assert {
        name: declaration.mode
        for name, declaration in RESPONSE_GUARD_DECLARATIONS.items()
    } == EXPECTED_MODES
    assert all(
        declaration.reason.strip()
        for declaration in RESPONSE_GUARD_DECLARATIONS.values()
    )
    assert all(
        declaration.replacement_covers is not None
        for declaration in RESPONSE_GUARD_DECLARATIONS.values()
        if declaration.mode is GuardMode.REPLACING
    )
    assert all(
        declaration.reduction_preserves is not None
        for declaration in RESPONSE_GUARD_DECLARATIONS.values()
        if declaration.mode is GuardMode.REDUCING
    )


def test_one_guard_per_declaration_so_no_member_inherits_a_stricter_mode() -> None:
    """The three selling-turn guards are declared apart, and here is why.

    They shared one declaration until 2026-08-11. The bundle had to take its
    strictest member's mode, so a purely additive question was suppressed as a
    removal and a measured fold was deferred to a paid judge.
    """

    assert "selling_turn" not in RESPONSE_GUARD_DECLARATIONS
    assert RESPONSE_GUARD_DECLARATIONS["company_question"].mode is GuardMode.REPLACING


@pytest.mark.parametrize(
    ("guard_name", "before", "guard", "uncovered_output"),
    [
        (
            "closed_question",
            "What is your name?",
            lambda text: repair_closed_questions(
                text,
                language="en",
                customer_name="Stored Name",
                company=None,
                customer_type=None,
                delivery_address=None,
            ),
            "Thank you.",
        ),
        (
            "premature_quote_details",
            "A suitable package is available.\n\n"
            "For a quotation, please share your delivery address.",
            lambda text: guard_premature_quote_detail_collection(
                text,
                language="en",
                quote_consent_granted=False,
            ),
            "Would you like me to prepare a formal quotation?",
        ),
        (
            "first_turn_opening",
            "Hi, I'm Noor from Treejar. The L-shaped desk fits a compact office.",
            lambda text: apply_first_turn_opening_guard(
                text,
                language="en",
                is_first_turn=True,
                customer_name="Stored Name",
                anchor_line=None,
            ),
            "Hello, I'm Noor from Treejar. We supply office furniture across the UAE.",
        ),
        (
            "deferred_commitment",
            "Assembly remains unconfirmed. The desk is available in oak.",
            lambda text: commit_to_what_you_deferred(text, language="en"),
            "I'll confirm assembly with our team and come back to you.",
        ),
    ],
)
def test_replacing_guard_requires_coverage_of_what_it_removed(
    guard_name: str,
    before: str,
    guard: Callable[[str], str],
    uncovered_output: str,
) -> None:
    declaration = RESPONSE_GUARD_DECLARATIONS[guard_name]
    covered = apply_declared_guard(
        before,
        declaration=declaration,
        guard=guard,
    )
    uncovered = apply_declared_guard(
        before,
        declaration=declaration,
        guard=lambda _text: uncovered_output,
    )

    assert covered.text == covered.candidate
    assert covered.text != before
    assert covered.flags == ()
    assert uncovered.text == before
    assert uncovered.candidate == uncovered_output
    assert [flag.reason for flag in uncovered.flags] == ["replacement_coverage_failed"]


@pytest.mark.parametrize("guard_name", ["question_form", "name_chase"])
def test_reducing_guard_drops_asks_but_refuses_to_lose_content(
    guard_name: str,
) -> None:
    original = "We stock 40 oak desks. What is your budget? How many seats?"
    declaration = RESPONSE_GUARD_DECLARATIONS[guard_name]

    reduced = apply_declared_guard(
        original,
        declaration=declaration,
        guard=lambda _text: "We stock 40 oak desks. What is your budget?",
    )
    lost_content = apply_declared_guard(
        original,
        declaration=declaration,
        guard=lambda _text: "What is your budget?",
        flag_details=("detected_example",),
    )
    invented = apply_declared_guard(
        original,
        declaration=declaration,
        guard=lambda _text: "We stock 40 oak desks. Shall I call you tomorrow?",
    )

    assert reduced.text == "We stock 40 oak desks. What is your budget?"
    assert reduced.flags == ()
    assert lost_content.text == original
    assert [flag.reason for flag in lost_content.flags] == ["reduction_lost_content"]
    assert lost_content.flags[0].details == ("detected_example",)
    assert invented.text == original
    assert [flag.reason for flag in invented.flags] == ["reduction_lost_content"]


@pytest.mark.parametrize("guard_name", ["grounding_output"])
def test_removing_guard_returns_the_original_text_and_a_flag(guard_name: str) -> None:
    original = "Keep this sentence. Remove this sentence."
    candidate = "Keep this sentence."

    application = apply_declared_guard(
        original,
        declaration=RESPONSE_GUARD_DECLARATIONS[guard_name],
        guard=lambda _text: candidate,
        flag_details=("detected_example",),
    )

    assert application.text == original
    assert application.candidate == candidate
    assert application.flags[0].guard_name == guard_name
    assert application.flags[0].reason == "removing_guard_triggered"
    assert application.flags[0].details == ("detected_example",)


def test_render_reply_folds_the_selling_turn_without_asking_anyone() -> None:
    """One question per reply, still deterministic and still free.

    Measured 2026-08-09 on S01 and R04: a customer handed a form answers none
    of it and leaves. Nothing here needs a second opinion, so nothing here
    raises a flag or spends a call.
    """

    selling = render_reply(
        "Which category suits you? What quantity do you need?",
        state=ReplyPolicyState(language="en"),
        provenance="model",
    )
    additive = render_reply(
        "We supply height-adjustable desks in oak and walnut.",
        state=ReplyPolicyState(language="en", owes_company_question=True),
        provenance="model",
    )

    assert selling.text == "Which category suits you?"
    assert selling.flags == ()
    assert additive.text.startswith("We supply height-adjustable desks")
    assert additive.text.endswith("?")
    assert additive.flags == ()


def test_first_turn_question_form_keeps_content_and_one_ask() -> None:
    original = "We found suitable desks. What size works? Which finish do you prefer?"

    rendered = render_reply(
        original,
        state=ReplyPolicyState(
            language="en",
            is_first_turn=True,
            customer_name="Binu",
        ),
        provenance="model",
    )

    assert "We found suitable desks." in rendered.text
    assert "What size works?" in rendered.text
    assert "Which finish" not in rendered.text
    assert rendered.flags == ()
    assert RESPONSE_GUARD_DECLARATIONS["question_form"].mode is GuardMode.REDUCING
    assert only_asks_were_dropped(
        "Hello, I'm Noor from Treejar. We supply office furniture across the UAE, "
        "and I quote from our own catalog with confirmed prices and stock.\n\n"
        + original,
        rendered.text,
    )


def test_the_name_ask_survives_the_one_question_bound_it_is_half_of() -> None:
    """`tj-l0e3`. The collapse used to delete the ask the opening guard added."""

    rendered = render_reply(
        "I can help. What are you furnishing? What is your budget? When do you need it?",
        state=ReplyPolicyState(
            language="en",
            is_first_turn=True,
            customer_name=None,
        ),
        provenance="model",
    )

    # One question from the model, and the canonical name ask folded onto it:
    # the directive's own bound, which counts a folded pair as one.
    assert "What are you furnishing?" in rendered.text
    assert "What is your budget?" not in rendered.text
    assert "When do you need it?" not in rendered.text
    assert rendered.text.endswith("And how should I address you?")
    assert rendered.flags == ()


def test_the_name_ask_is_not_added_twice_when_the_model_already_asked() -> None:
    """The collapse now runs first, so the model's own name ask reaches the guard."""

    rendered = render_reply(
        "Happy to help. May I know your name, and what are you furnishing?",
        state=ReplyPolicyState(
            language="en",
            is_first_turn=True,
            customer_name=None,
        ),
        provenance="model",
    )

    assert "May I know your name" in rendered.text
    assert "how should I address you" not in rendered.text


def test_a_later_turn_is_the_same_text_under_either_guard_order() -> None:
    """The opening guard is a no-op after turn one, so only first turns moved."""

    original = "We found suitable desks. What size works? Which finish do you prefer?"

    rendered = render_reply(
        original,
        state=ReplyPolicyState(
            language="en",
            is_first_turn=False,
            customer_name="Binu",
            customer_name_asked=True,
        ),
        provenance="model",
    )

    assert rendered.text == "We found suitable desks. What size works?"
    assert rendered.flags == ()


def test_first_turn_name_chase_and_company_question_stay_gated() -> None:
    repeated_name_ask = "We found suitable desks. May I know your name?"

    rendered = render_reply(
        repeated_name_ask,
        state=ReplyPolicyState(
            language="en",
            is_first_turn=True,
            customer_name_asked=True,
            owes_company_question=True,
        ),
        provenance="model",
    )

    assert "May I know your name?" in rendered.text
    assert "company" not in rendered.text.casefold()


def test_render_reply_keeps_removing_candidates_non_visible() -> None:
    grounding_text = (
        "We can assess your used desks. Would you like help choosing replacements?"
    )
    grounding = render_reply(
        grounding_text,
        state=ReplyPolicyState(language="en"),
        provenance="model",
    )

    assert grounding.text == grounding_text
    assert [flag.guard_name for flag in grounding.flags] == ["grounding_output"]
    assert grounding.flags[0].candidate is not None
    assert "assess your used desks" not in grounding.flags[0].candidate.casefold()
