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
def test_render_reply_applies_grounding_to_every_provenance(
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

    assert "assess your used desks" not in rendered.text.casefold()
    assert "help choosing replacement desks" in rendered.text.casefold()
    assert rendered.provenance == provenance
    assert (
        GroundingViolation.UNVERIFIED_CUSTOMER_OWNED_FURNITURE_SERVICE
        in rendered.grounding.violations
    )


def test_render_reply_turns_a_deferral_into_an_explicit_commitment() -> None:
    rendered = render_reply(
        "Assembly remains unconfirmed.",
        state=ReplyPolicyState(language="en"),
        provenance="deterministic_static",
    )

    assert "I'll confirm assembly with our team" in rendered.text
