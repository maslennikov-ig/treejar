from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from src.core.config import settings
from src.llm.conversation_summary import (
    SUMMARY_TAIL_MESSAGES,
    refresh_conversation_summary_record,
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


@pytest.mark.asyncio
async def test_refresh_conversation_summary_initial_build_for_long_dialog() -> None:
    conv_id = uuid.uuid4()
    messages = [
        _build_message(
            conversation_id=conv_id,
            idx=idx,
            role="user" if idx % 2 == 0 else "assistant",
            content=f"Message {idx}",
        )
        for idx in range(10)
    ]

    mock_db = AsyncMock()
    mock_db.execute.side_effect = [
        MockResult(scalar_value=None),
        MockResult(items=messages),
    ]

    with patch(
        "src.llm.conversation_summary.summary_agent.run",
        new=AsyncMock(
            return_value=SimpleNamespace(output="Customer / company:\n- ACME")
        ),
    ) as mock_run:
        summary = await refresh_conversation_summary_record(mock_db, conv_id)

    assert isinstance(summary, ConversationSummary)
    assert summary.summary_text == "Customer / company:\n- ACME"
    assert summary.covered_through_message_id == messages[-SUMMARY_TAIL_MESSAGES - 1].id
    assert summary.model == settings.openrouter_model_fast
    assert summary.version == 1
    mock_db.add.assert_called_once_with(summary)
    mock_db.commit.assert_awaited_once()

    prompt = mock_run.await_args.args[0]
    assert messages[0].content in prompt
    assert messages[5].content in prompt
    assert messages[6].content not in prompt
    assert messages[9].content not in prompt


@pytest.mark.asyncio
async def test_refresh_conversation_summary_incremental_only_uses_overflowed_messages() -> (
    None
):
    conv_id = uuid.uuid4()
    messages = [
        _build_message(
            conversation_id=conv_id,
            idx=idx,
            role="user" if idx % 2 == 0 else "assistant",
            content=f"Message {idx}",
        )
        for idx in range(12)
    ]
    summary = ConversationSummary(
        conversation_id=conv_id,
        summary_text="Customer / company:\n- Existing summary",
        covered_through_message_id=messages[5].id,
        model="old-model",
        version=1,
    )

    mock_db = AsyncMock()
    mock_db.execute.side_effect = [
        MockResult(scalar_value=summary),
        MockResult(items=messages),
    ]

    with patch(
        "src.llm.conversation_summary.summary_agent.run",
        new=AsyncMock(return_value=SimpleNamespace(output="Updated summary")),
    ) as mock_run:
        result = await refresh_conversation_summary_record(mock_db, conv_id)

    assert result is summary
    assert summary.summary_text == "Updated summary"
    assert summary.covered_through_message_id == messages[7].id
    assert summary.model == settings.openrouter_model_fast
    mock_db.add.assert_not_called()
    mock_db.commit.assert_awaited_once()

    prompt = mock_run.await_args.args[0]
    assert "Existing summary" in prompt
    assert messages[6].content in prompt
    assert messages[7].content in prompt
    assert messages[5].content not in prompt
    assert messages[8].content not in prompt


@pytest.mark.asyncio
async def test_refresh_conversation_summary_excludes_newest_four_messages() -> None:
    conv_id = uuid.uuid4()
    messages = [
        _build_message(
            conversation_id=conv_id,
            idx=idx,
            role="user" if idx % 2 == 0 else "assistant",
            content=f"Message {idx}",
        )
        for idx in range(9)
    ]

    mock_db = AsyncMock()
    mock_db.execute.side_effect = [
        MockResult(scalar_value=None),
        MockResult(items=messages),
    ]

    with patch(
        "src.llm.conversation_summary.summary_agent.run",
        new=AsyncMock(return_value=SimpleNamespace(output="Summary")),
    ) as mock_run:
        await refresh_conversation_summary_record(mock_db, conv_id)

    prompt = mock_run.await_args.args[0]
    for message in messages[-SUMMARY_TAIL_MESSAGES:]:
        assert message.content not in prompt


@pytest.mark.asyncio
async def test_refresh_conversation_summary_noop_when_no_new_eligible_messages() -> (
    None
):
    conv_id = uuid.uuid4()
    messages = [
        _build_message(
            conversation_id=conv_id,
            idx=idx,
            role="user" if idx % 2 == 0 else "assistant",
            content=f"Message {idx}",
        )
        for idx in range(10)
    ]
    summary = ConversationSummary(
        conversation_id=conv_id,
        summary_text="Existing summary",
        covered_through_message_id=messages[5].id,
        model="fast-model",
        version=1,
    )

    mock_db = AsyncMock()
    mock_db.execute.side_effect = [
        MockResult(scalar_value=summary),
        MockResult(items=messages),
    ]

    with patch(
        "src.llm.conversation_summary.summary_agent.run",
        new=AsyncMock(),
    ) as mock_run:
        result = await refresh_conversation_summary_record(mock_db, conv_id)

    assert result is None
    mock_run.assert_not_awaited()
    mock_db.add.assert_not_called()
    mock_db.commit.assert_not_awaited()
