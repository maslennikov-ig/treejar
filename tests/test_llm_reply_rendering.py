from __future__ import annotations

import pytest

from src.llm.grounding_output import GroundingViolation
from src.llm.response_policy import ReplyPolicyState, ReplyProvenance, render_reply


@pytest.mark.parametrize(
    "provenance",
    [
        "model",
        "model_repaired",
        "deterministic_replacement",
        "deterministic_static",
    ],
)
def test_render_reply_classifies_grounding_without_editing_any_provenance(
    provenance: ReplyProvenance,
) -> None:
    text = (
        "We can assess your used desks. Would you like help choosing replacement desks?"
    )

    rendered = render_reply(
        text,
        state=ReplyPolicyState(language="en"),
        provenance=provenance,
    )

    assert rendered.text == text
    assert "help choosing replacement desks" in rendered.text.casefold()
    assert rendered.provenance == provenance
    assert (
        GroundingViolation.UNVERIFIED_CUSTOMER_OWNED_FURNITURE_SERVICE
        in rendered.grounding.violations
    )
    assert [flag.guard_name for flag in rendered.flags] == ["grounding_output"]
    assert rendered.flags[0].candidate is not None
    assert "assess your used desks" not in rendered.flags[0].candidate.casefold()


def test_render_reply_leaves_followup_commitment_to_model() -> None:
    rendered = render_reply(
        "Assembly remains unconfirmed.",
        state=ReplyPolicyState(language="en"),
        provenance="deterministic_static",
    )

    assert rendered.text == "Assembly remains unconfirmed."


def test_numbered_question_reduction_cannot_leave_an_orphan_marker() -> None:
    text = (
        "To issue a formal quotation, I just need to confirm a few details:\n\n"
        "1. Items: 1 × LUMA workstation — correct?\n"
        "2. Delivery address in Dubai for the quotation\n"
        "3. What company name should I use?\n\n"
        "Just share those three and I will prepare the quotation."
    )
    rendered = render_reply(
        text,
        state=ReplyPolicyState(language="en", quote_consent_granted=True),
        provenance="model",
    )
    assert "3. What company name should I use?" in rendered.text
    assert any(flag.guard_name == "question_form" for flag in rendered.flags)
    assert "\n3.\n" not in rendered.text


def test_empty_model_list_is_flagged_for_coherent_model_repair() -> None:
    text = "Please confirm:\n1. Desk\n2. Address\n3.\n\nShare those three."
    rendered = render_reply(
        text,
        state=ReplyPolicyState(language="en", quote_consent_granted=True),
        provenance="model",
    )
    assert any(flag.guard_name == "empty_list_items" for flag in rendered.flags)
