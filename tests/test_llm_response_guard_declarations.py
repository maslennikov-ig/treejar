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
from src.llm.sales_turn_guard import commit_to_what_you_deferred

EXPECTED_MODES = {
    "closed_question": GuardMode.REPLACING,
    "premature_quote_details": GuardMode.REPLACING,
    "first_turn_opening": GuardMode.REPLACING,
    "selling_turn": GuardMode.REMOVING,
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


@pytest.mark.parametrize("guard_name", ["selling_turn", "grounding_output"])
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


def test_render_reply_keeps_removing_candidates_non_visible() -> None:
    selling_text = "Which category suits you? What quantity do you need?"
    grounding_text = (
        "We can assess your used desks. Would you like help choosing replacements?"
    )
    selling = render_reply(
        selling_text,
        state=ReplyPolicyState(language="en"),
        provenance="model",
    )
    grounding = render_reply(
        grounding_text,
        state=ReplyPolicyState(language="en"),
        provenance="model",
    )

    assert selling.text == selling_text
    assert [flag.guard_name for flag in selling.flags] == ["selling_turn"]
    assert selling.flags[0].candidate == "Which category suits you?"
    assert grounding.text == grounding_text
    assert [flag.guard_name for flag in grounding.flags] == ["grounding_output"]
    assert grounding.flags[0].candidate is not None
    assert "assess your used desks" not in grounding.flags[0].candidate.casefold()
