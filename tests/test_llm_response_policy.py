from __future__ import annotations

import logging

import pytest

from src.llm.response_policy import apply_guard_with_reply_bound


@pytest.mark.parametrize(
    ("guard_name", "blank_result"),
    [
        ("closed_question", ""),
        ("premature_quote_details", " \n "),
        ("first_turn_opening", "..."),
        ("selling_turn", "؟!"),
        ("deferred_commitment", "\t"),
        ("grounding_output", "\n\n"),
        ("tool_disclosures", "—"),
    ],
    ids=lambda value: str(value).replace("\n", "newline").replace("\t", "tab"),
)
def test_each_existing_guard_cannot_blank_a_meaningful_reply(
    guard_name: str,
    blank_result: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    original = "A useful answer remains available."

    with caplog.at_level(logging.ERROR):
        result = apply_guard_with_reply_bound(
            original,
            guard_name=guard_name,
            guard=lambda _text: blank_result,
        )

    assert result == original
    assert guard_name in caplog.text
    assert original not in caplog.text


def test_a_short_meaningful_safe_repair_is_not_rejected() -> None:
    original = "A long answer can legitimately need a complete safety repair."

    result = apply_guard_with_reply_bound(
        original,
        guard_name="grounding_output",
        guard=lambda _text: "Safe.",
    )

    assert result == "Safe."


def test_a_guard_may_delete_one_sentence_when_another_remains() -> None:
    original = "Keep this sentence. Remove the other sentence."

    result = apply_guard_with_reply_bound(
        original,
        guard_name="selling_turn",
        guard=lambda _text: "Keep this sentence.",
    )

    assert result == "Keep this sentence."


def test_the_pre_fix_identity_guard_cannot_erase_a_curly_apostrophe_reply() -> None:
    def pre_fix_identity_guard(text: str) -> str:
        normalized = text.casefold()
        return "" if "noor" in normalized and "treejar" in normalized else text

    original = "Hi, I’m Noor from Treejar. How can I help?"

    result = apply_guard_with_reply_bound(
        original,
        guard_name="pre_fix_identity",
        guard=pre_fix_identity_guard,
    )

    assert result == original


def test_the_guard_receives_the_current_reply() -> None:
    received: list[str] = []

    def guard(text: str) -> str:
        received.append(text)
        return text

    result = apply_guard_with_reply_bound(
        "Current reply.",
        guard_name="identity",
        guard=guard,
    )

    assert result == "Current reply."
    assert received == ["Current reply."]
