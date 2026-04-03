from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock

import pytest
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    SystemPromptPart,
    TextPart,
    UserPromptPart,
)

from src.llm.context import (
    MAX_RAW_CHARS,
    VERBATIM_TAIL_MESSAGES,
    build_message_history,
)
from src.models.conversation_summary import ConversationSummary
from src.models.message import Message


class MockResult:
    def __init__(
        self, scalar_value: Any = None, items: list[Any] | None = None
    ) -> None:
        self.scalar_value = scalar_value
        self.items = items or []

    def scalar_one_or_none(self) -> Any:
        return self.scalar_value

    def scalars(self) -> MockResult:
        return self

    def all(self) -> list[Any]:
        return self.items


def _build_message(
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
        created_at=datetime.now(UTC) + timedelta(seconds=idx),
    )


def _content(model_message: ModelMessage) -> str:
    part = model_message.parts[0]
    if isinstance(part, (UserPromptPart, TextPart, SystemPromptPart)):
        return str(part.content)
    raise AssertionError(f"Unexpected part type: {type(part)!r}")


@pytest.mark.asyncio
async def test_build_message_history_short_dialog_without_summary() -> None:
    conv_id = uuid.uuid4()
    messages = [
        _build_message(
            conversation_id=conv_id,
            idx=idx,
            role="user" if idx % 2 == 0 else "assistant",
            content=f"Short message {idx}",
        )
        for idx in range(4)
    ]

    mock_db = AsyncMock()
    mock_db.execute.side_effect = [
        MockResult(scalar_value=None),
        MockResult(items=list(reversed(messages))),
    ]

    history = await build_message_history(mock_db, conv_id, {})

    assert len(history) == len(messages)
    assert all(
        not any(isinstance(part, SystemPromptPart) for part in model_message.parts)
        for model_message in history
    )
    assert [_content(model_message) for model_message in history] == [
        message.content for message in messages
    ]


@pytest.mark.asyncio
async def test_build_message_history_long_dialog_with_summary_injected_first() -> None:
    conv_id = uuid.uuid4()
    messages = [
        _build_message(
            conversation_id=conv_id,
            idx=idx,
            role="user" if idx % 2 == 0 else "assistant",
            content=f"Message {idx} " + ("x" * 240),
        )
        for idx in range(10)
    ]
    summary = ConversationSummary(
        conversation_id=conv_id,
        summary_text="Customer / company: ACME. Reach me via buyer@example.com",
        covered_through_message_id=messages[5].id,
        model="fast-model",
        version=1,
    )

    mock_db = AsyncMock()
    mock_db.execute.side_effect = [
        MockResult(scalar_value=summary),
        MockResult(items=list(reversed(messages))),
    ]

    history = await build_message_history(mock_db, conv_id, {})

    assert len(history) == 1 + VERBATIM_TAIL_MESSAGES

    summary_message = history[0]
    assert isinstance(summary_message, ModelRequest)
    assert isinstance(summary_message.parts[0], SystemPromptPart)
    assert "[EARLIER CONVERSATION SUMMARY - FACTS ONLY]" in _content(summary_message)
    assert "buyer@example.com" not in _content(summary_message)
    assert "[PII-" in _content(summary_message)

    raw_history = history[1:]
    raw_contents = [_content(model_message) for model_message in raw_history]
    assert raw_contents == [message.content for message in messages[6:]]
    assert raw_contents[-VERBATIM_TAIL_MESSAGES:] == [
        message.content for message in messages[-VERBATIM_TAIL_MESSAGES:]
    ]
    assert messages[5].content not in raw_contents
    assert sum(len(content) for content in raw_contents) <= MAX_RAW_CHARS


@pytest.mark.asyncio
async def test_build_message_history_limits_raw_tail_by_char_budget() -> None:
    conv_id = uuid.uuid4()
    messages = [
        _build_message(
            conversation_id=conv_id,
            idx=0,
            role="user",
            content="Early message 0",
        ),
        _build_message(
            conversation_id=conv_id,
            idx=1,
            role="assistant",
            content="Early message 1",
        ),
        _build_message(
            conversation_id=conv_id,
            idx=2,
            role="user",
            content="X" * MAX_RAW_CHARS,
        ),
        _build_message(
            conversation_id=conv_id,
            idx=3,
            role="assistant",
            content="fits-before-budget",
        ),
        _build_message(
            conversation_id=conv_id,
            idx=4,
            role="user",
            content="tail-4",
        ),
        _build_message(
            conversation_id=conv_id,
            idx=5,
            role="assistant",
            content="tail-5",
        ),
        _build_message(
            conversation_id=conv_id,
            idx=6,
            role="user",
            content="tail-6",
        ),
        _build_message(
            conversation_id=conv_id,
            idx=7,
            role="assistant",
            content="tail-7",
        ),
    ]

    mock_db = AsyncMock()
    mock_db.execute.side_effect = [
        MockResult(scalar_value=None),
        MockResult(items=list(reversed(messages))),
    ]

    history = await build_message_history(mock_db, conv_id, {})
    raw_contents = [_content(model_message) for model_message in history]

    assert raw_contents == [message.content for message in messages[3:]]
    assert messages[2].content not in raw_contents
    assert raw_contents[-VERBATIM_TAIL_MESSAGES:] == [
        message.content for message in messages[-VERBATIM_TAIL_MESSAGES:]
    ]
    assert sum(len(content) for content in raw_contents) <= MAX_RAW_CHARS


@pytest.mark.asyncio
async def test_build_message_history_masks_pii_in_raw_messages_and_summary() -> None:
    conv_id = uuid.uuid4()
    messages = [
        _build_message(
            conversation_id=conv_id,
            idx=0,
            role="user",
            content="Email me at sales@example.com",
        ),
        _build_message(
            conversation_id=conv_id,
            idx=1,
            role="assistant",
            content="Sure, I can help.",
        ),
    ]
    summary = ConversationSummary(
        conversation_id=conv_id,
        summary_text="Commercial facts: call +971501234567 tomorrow",
        covered_through_message_id=None,
        model="fast-model",
        version=1,
    )

    mock_db = AsyncMock()
    mock_db.execute.side_effect = [
        MockResult(scalar_value=summary),
        MockResult(items=list(reversed(messages))),
    ]

    pii_map: dict[str, str] = {}
    history = await build_message_history(mock_db, conv_id, pii_map)

    summary_text = _content(history[0])
    user_text = _content(history[1])

    assert "+971501234567" not in summary_text
    assert "[PII-" in summary_text
    assert "sales@example.com" not in user_text
    assert "[PII-" in user_text
    assert "sales@example.com" in pii_map.values()
    assert "+971501234567" in pii_map.values()


@pytest.mark.asyncio
async def test_build_message_history_empty() -> None:
    mock_db = AsyncMock()
    mock_db.execute.side_effect = [
        MockResult(scalar_value=None),
        MockResult(items=[]),
    ]

    history = await build_message_history(mock_db, uuid.uuid4(), {})
    assert history == []
