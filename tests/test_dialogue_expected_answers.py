from __future__ import annotations

from datetime import UTC, datetime

from src.dialogue.expected_answers import (
    ExpectedAnswerMatch,
    match_expected_answer,
)
from src.dialogue.state import DialogueState, ExpectedAnswerFrame, ExpectedSlot


def test_product_preference_frame_matches_open_workspace_answer() -> None:
    state = DialogueState(
        active_flow="product_selection",
        expected_answer_frames=[_product_preference_frame()],
    )

    match = match_expected_answer(state, "I prefer more open for team")

    assert isinstance(match, ExpectedAnswerMatch)
    assert match.matched is True
    assert match.frame_id == "product_preference:test"
    assert match.confidence == "high"
    assert match.filled_slots == {"workspace_preference": "open"}
    assert match.route == "product_preference_answer"
    assert match.interruption is False
    assert match.blocker is None


def test_bounded_delivery_question_is_interruption_without_frame_fulfillment() -> None:
    state = DialogueState(
        active_flow="product_selection",
        expected_answer_frames=[_product_preference_frame()],
    )

    match = match_expected_answer(state, "Can delivery be arranged?")

    assert match.matched is False
    assert match.frame_id is None
    assert match.filled_slots == {}
    assert match.route == "legacy_fallback"
    assert match.interruption is True
    assert match.blocker is None


def test_hard_blockers_override_expected_answer_frames() -> None:
    state = DialogueState(
        active_flow="product_selection",
        expected_answer_frames=[_product_preference_frame()],
    )

    for text, blocker in [
        ("I prefer open but I need a human to help", "human_request"),
        ("I prefer open but I need a manager", "human_request"),
        ("I prefer open but this is a complaint", "complaint"),
        ("I prefer open but I need a refund", "refund"),
        ("I prefer open but need a discount", "discount"),
        ("I prefer open but can you do net 30 payment terms", "payment_terms"),
        ("I prefer open but can we use credit terms", "payment_terms"),
        ("I prefer open but what about warranty", "warranty"),
    ]:
        match = match_expected_answer(state, text)

        assert match.matched is False
        assert match.frame_id is None
        assert match.filled_slots == {}
        assert match.route == "legacy_fallback"
        assert match.interruption is False
        assert match.blocker == blocker


def test_terse_ordinal_across_multiple_frames_routes_to_clarification() -> None:
    state = DialogueState(
        active_flow="product_selection",
        expected_answer_frames=[
            _product_preference_frame(),
            ExpectedAnswerFrame(
                frame_id="quantity:test",
                flow="quotation_build",
                question_kind="sku_quantity",
                prompt_key="ask_quantity_for_choice",
                priority=70,
                expected_slots=[ExpectedSlot(slot="selected_option")],
                source_refs=[
                    {"kind": "sku", "value": "LUMA", "ordinal": 1},
                    {"kind": "sku", "value": "NOVO", "ordinal": 2},
                ],
            ),
        ],
    )

    match = match_expected_answer(state, "the second one")

    assert match.matched is False
    assert match.frame_id is None
    assert match.confidence == "ambiguous"
    assert match.route == "expected_answer_clarify"
    assert match.ambiguous_frame_ids == [
        "product_preference:test",
        "quantity:test",
    ]
    assert match.filled_slots == {}


def test_expired_frames_are_ignored_and_fall_back_safely() -> None:
    state = DialogueState(
        active_flow="product_selection",
        expected_answer_frames=[
            _product_preference_frame(
                expires_at="2026-06-02T10:00:00+00:00",
            )
        ],
    )

    match = match_expected_answer(
        state,
        "I prefer more open for team",
        now=datetime(2026, 6, 2, 10, 1, tzinfo=UTC),
    )

    assert match.matched is False
    assert match.frame_id is None
    assert match.filled_slots == {}
    assert match.route == "legacy_fallback"
    assert match.interruption is False
    assert match.blocker is None


def _product_preference_frame(
    *,
    expires_at: str | datetime | None = None,
) -> ExpectedAnswerFrame:
    return ExpectedAnswerFrame(
        frame_id="product_preference:test",
        flow="product_selection",
        question_kind="product_preference",
        prompt_key="workspace_luma_novo_preference",
        priority=80,
        expires_at=expires_at,
        max_customer_turns=6,
        expected_slots=[
            ExpectedSlot(
                slot="workspace_preference",
                accepted_values=["open", "private"],
                aliases={
                    "open": ["more open", "for team", "collaborative", "novo"],
                    "private": ["private", "more privacy", "luma", "individual"],
                },
            )
        ],
        source_refs=[
            {"kind": "product_family", "value": "LUMA", "ordinal": 1},
            {"kind": "product_family", "value": "SKYLAND NOVO", "ordinal": 2},
        ],
    )
