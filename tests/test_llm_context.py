import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, UserPromptPart

from src.llm.context import MAX_RAW_MESSAGES, build_message_history
from src.models.message import Message


@pytest.fixture
def mock_messages() -> list[Message]:
    conv_id = uuid.uuid4()
    messages = []
    # Create 15 messages (more than MAX_RAW_MESSAGES)
    for i in range(15):
        role = "user" if i % 2 == 0 else "assistant"
        msg = Message(
            id=uuid.uuid4(),
            conversation_id=conv_id,
            role=role,
            content=f"Test content {i} test@example.com",
            wazzup_message_id=f"msg_{i}",
        )
        messages.append(msg)
    return messages


@pytest.mark.asyncio
async def test_build_message_history_truncation(mock_messages: list[Message]) -> None:
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = mock_messages
    mock_db.execute.return_value = mock_result

    conv_id = mock_messages[0].conversation_id
    pii_map: dict[str, str] = {}

    history = await build_message_history(mock_db, conv_id, pii_map)

    # Assert truncation to MAX_RAW_MESSAGES
    assert len(history) == MAX_RAW_MESSAGES

    # Assert proper PydanticAI conversion and PII masking
    for model_msg in history:
        assert isinstance(model_msg, (ModelRequest, ModelResponse))
        if isinstance(model_msg, ModelRequest):
            part = model_msg.parts[0]
            assert isinstance(part, UserPromptPart)
            # User messages must be masked
            text_content = str(part.content)
            assert "test@example.com" not in text_content
            assert "[PII-" in text_content
        else:
            resp_part = model_msg.parts[0]
            assert isinstance(resp_part, TextPart)
            # Assistant messages stay as is from DB setup
            assert "Test content" in str(resp_part.content)

    # Validate PII map is populated
    assert "test@example.com" in pii_map.values()


@pytest.mark.asyncio
async def test_build_message_history_empty() -> None:
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = mock_result

    history = await build_message_history(mock_db, uuid.uuid4(), {})
    assert history == []
