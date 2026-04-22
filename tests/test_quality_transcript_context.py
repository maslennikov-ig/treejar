from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from src.models.message import Message
from src.quality.config import AIQualityTranscriptMode
from src.quality.transcript_context import (
    MAX_BOT_QA_CONTEXT_CHARS,
    MAX_MANAGER_QA_CONTEXT_CHARS,
    MAX_RED_FLAG_CONTEXT_CHARS,
    ReviewContextPurpose,
    build_review_transcript_context,
)


def _message(
    *,
    conversation_id: uuid.UUID,
    idx: int,
    role: str,
    content: str,
) -> Message:
    return Message(
        id=uuid.uuid4(),
        conversation_id=conversation_id,
        role=role,
        content=content,
        created_at=datetime(2026, 4, 21, 9, 0, tzinfo=UTC) + timedelta(minutes=idx),
    )


def test_summary_context_includes_required_sections_and_stays_bounded() -> None:
    conversation_id = uuid.uuid4()
    messages = [
        _message(
            conversation_id=conversation_id,
            idx=0,
            role="user",
            content="FIRST CUSTOMER TURN: I need office chairs for my Dubai team.",
        ),
        _message(
            conversation_id=conversation_id,
            idx=1,
            role="assistant",
            content="FIRST BOT TURN: Hi, I am Siyyad from Treejar.",
        ),
        _message(
            conversation_id=conversation_id,
            idx=2,
            role="assistant",
            content="MIDDLE_BULK_SHOULD_NOT_APPEAR " + ("x" * 20_000),
        ),
        *[
            _message(
                conversation_id=conversation_id,
                idx=idx,
                role="assistant" if idx % 2 else "user",
                content=f"filler {idx}",
            )
            for idx in range(3, 13)
        ],
        _message(
            conversation_id=conversation_id,
            idx=13,
            role="assistant",
            content="PROMISE_MARKER: I will send the quotation tomorrow.",
        ),
        _message(
            conversation_id=conversation_id,
            idx=14,
            role="assistant",
            content="ESCALATION_MARKER: Our manager will review exact availability.",
        ),
        _message(
            conversation_id=conversation_id,
            idx=15,
            role="manager",
            content="MANAGER_SEGMENT_MARKER: I can confirm stock and delivery.",
        ),
        _message(
            conversation_id=conversation_id,
            idx=16,
            role="user",
            content="LAST_CUSTOMER_TURN: Please send the final quote.",
        ),
    ]

    context = build_review_transcript_context(
        messages,
        purpose=ReviewContextPurpose.BOT_QA,
        entity_type="conversation",
        entity_id=conversation_id,
        transcript_mode=AIQualityTranscriptMode.SUMMARY,
        activity_at=messages[-1].created_at,
        summary_text="Customer needs chairs for a Dubai office.",
    )

    assert context.used_full_transcript is False
    assert context.insufficient_evidence is False
    assert len(context.prompt) <= MAX_BOT_QA_CONTEXT_CHARS
    assert "FIRST CUSTOMER TURN" in context.prompt
    assert "LAST_CUSTOMER_TURN" in context.prompt
    assert "MANAGER_SEGMENT_MARKER" in context.prompt
    assert "PROMISE_MARKER" in context.prompt
    assert "ESCALATION_MARKER" in context.prompt
    assert "Customer needs chairs" in context.prompt
    assert "message_count: 17" in context.prompt
    assert "MIDDLE_BULK_SHOULD_NOT_APPEAR" not in context.prompt


def test_red_flag_summary_context_is_more_compact_than_final_review() -> None:
    conversation_id = uuid.uuid4()
    messages = [
        _message(
            conversation_id=conversation_id,
            idx=idx,
            role="assistant" if idx % 2 else "user",
            content=f"turn {idx} " + ("verbose " * 400),
        )
        for idx in range(30)
    ]

    context = build_review_transcript_context(
        messages,
        purpose=ReviewContextPurpose.RED_FLAGS,
        entity_type="conversation",
        entity_id=conversation_id,
        transcript_mode=AIQualityTranscriptMode.SUMMARY,
        activity_at=messages[-1].created_at,
    )

    assert len(context.prompt) <= MAX_RED_FLAG_CONTEXT_CHARS
    assert len(context.prompt) < MAX_BOT_QA_CONTEXT_CHARS
    assert "turn 0" in context.prompt
    assert "turn 29" in context.prompt


def test_full_mode_uses_complete_dialogue_only_when_explicitly_requested() -> None:
    conversation_id = uuid.uuid4()
    full_middle = "FULL_TRANSCRIPT_ONLY_MARKER " + ("full " * 3000)
    messages = [
        _message(conversation_id=conversation_id, idx=0, role="user", content="start"),
        _message(
            conversation_id=conversation_id,
            idx=1,
            role="assistant",
            content=full_middle,
        ),
        _message(conversation_id=conversation_id, idx=2, role="user", content="end"),
    ]

    context = build_review_transcript_context(
        messages,
        purpose=ReviewContextPurpose.BOT_QA,
        entity_type="conversation",
        entity_id=conversation_id,
        transcript_mode=AIQualityTranscriptMode.FULL,
        activity_at=messages[-1].created_at,
    )

    assert context.used_full_transcript is True
    assert context.insufficient_evidence is False
    assert "FULL_TRANSCRIPT_ONLY_MARKER" in context.prompt
    assert full_middle.strip() in context.prompt
    assert "<DIALOGUE>" in context.prompt


def test_disabled_mode_returns_insufficient_evidence_without_transcript() -> None:
    conversation_id = uuid.uuid4()
    messages = [
        _message(
            conversation_id=conversation_id,
            idx=0,
            role="user",
            content="DISABLED_MODE_MUST_NOT_LEAK_TRANSCRIPT",
        )
    ]

    context = build_review_transcript_context(
        messages,
        purpose=ReviewContextPurpose.BOT_QA,
        entity_type="conversation",
        entity_id=conversation_id,
        transcript_mode=AIQualityTranscriptMode.DISABLED,
        activity_at=messages[-1].created_at,
    )

    assert context.used_full_transcript is False
    assert context.insufficient_evidence is True
    assert "DISABLED_MODE_MUST_NOT_LEAK_TRANSCRIPT" not in context.prompt
    assert "transcript_mode: disabled" in context.prompt


def test_manager_context_prioritizes_post_escalation_segment_with_prior_context() -> (
    None
):
    conversation_id = uuid.uuid4()
    messages = [
        _message(
            conversation_id=conversation_id,
            idx=0,
            role="user",
            content="PRIOR_CONTEXT_MARKER: Need 20 desks for a school.",
        ),
        _message(
            conversation_id=conversation_id,
            idx=1,
            role="assistant",
            content="I will ask a manager to confirm bulk pricing.",
        ),
        _message(
            conversation_id=conversation_id,
            idx=2,
            role="manager",
            content="POST_ESCALATION_MANAGER_MARKER: I can confirm the discount.",
        ),
        _message(
            conversation_id=conversation_id,
            idx=3,
            role="user",
            content="POST_ESCALATION_CUSTOMER_MARKER: Please proceed.",
        ),
    ]

    context = build_review_transcript_context(
        messages,
        purpose=ReviewContextPurpose.MANAGER_QA,
        entity_type="escalation",
        entity_id=uuid.uuid4(),
        transcript_mode=AIQualityTranscriptMode.SUMMARY,
        activity_at=messages[-1].created_at,
        focus_after=messages[2].created_at,
        escalation_context="Reason: customer asked for manager.",
    )

    assert len(context.prompt) <= MAX_MANAGER_QA_CONTEXT_CHARS
    assert "PRIOR_CONTEXT_MARKER" in context.prompt
    assert "POST_ESCALATION_MANAGER_MARKER" in context.prompt
    assert "POST_ESCALATION_CUSTOMER_MARKER" in context.prompt
    assert "Reason: customer asked for manager" in context.prompt
