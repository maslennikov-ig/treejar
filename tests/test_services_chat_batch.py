from unittest.mock import AsyncMock, patch

import pytest

from src.schemas.webhook import WazzupIncomingMessage
from src.services.chat import process_incoming_batch


@pytest.mark.asyncio
@patch("src.services.chat.async_session_factory")
@patch("src.services.chat.process_message")
@patch("src.services.chat.WazzupProvider")
async def test_process_incoming_batch_new_conversation(
    mock_wazzup_cls: AsyncMock,
    mock_process_message: AsyncMock,
    mock_session_factory: AsyncMock,
) -> None:
    # Set up mocks
    mock_session = AsyncMock()
    mock_session_factory.return_value.__aenter__.return_value = mock_session
    mock_wazzup = AsyncMock()
    mock_wazzup_cls.return_value = mock_wazzup

    from typing import Any

    class MockResult:
        def __init__(self, val: Any) -> None:
            self.val = val

        def scalar_one_or_none(self) -> Any:
            return self.val

        def scalars(self) -> Any:
            return self

        def first(self) -> Any:
            return self.val

    mock_session.execute.side_effect = [
        MockResult(None),  # bot_enabled
        MockResult(None),  # conv
        MockResult(None),  # msg
    ]

    # Simulate LLM response
    mock_llm_response = AsyncMock()
    mock_llm_response.text = "Hello from AI"
    mock_llm_response.tokens_in = 10
    mock_llm_response.tokens_out = 20
    mock_llm_response.cost = 0.05
    mock_llm_response.model = "test-model"
    mock_process_message.return_value = mock_llm_response

    # Mock Redis lpop to return one message then None
    mock_redis = AsyncMock()
    msg = WazzupIncomingMessage(
        messageId="msg-1",
        chatId="1234567890",
        chatType="whatsapp",
        type="text",
        text="Hi there",
        channelId="chan-1",
        timestamp=1704067200,
    )
    mock_redis.lpop.side_effect = [msg.model_dump_json(), None]

    ctx = {"redis": mock_redis}
    chat_id = "1234567890"

    await process_incoming_batch(ctx, chat_id)

    # Assertions
    # Called to add Conversation and 2 Messages (user + ai)
    assert mock_session.add.call_count == 3
    mock_session.commit.assert_awaited()
    mock_process_message.assert_awaited_once()
    mock_wazzup.send_text.assert_awaited_once_with(
        chat_id=chat_id, text="Hello from AI"
    )
