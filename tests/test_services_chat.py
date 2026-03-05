from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from src.services.chat import process_incoming_batch


@pytest.fixture
def chat_context() -> dict[str, Any]:
    mock_redis = AsyncMock()
    # Default: no messages in Redis
    mock_redis.lpop.return_value = None
    return {
        "redis": mock_redis,
    }


@pytest.mark.asyncio
@patch("src.services.chat.async_session_factory")
@patch("src.services.chat.WazzupProvider")
@patch("src.services.chat.process_message")
async def test_process_incoming_batch_success(
    mock_process_message: AsyncMock,
    mock_provider_class: AsyncMock,
    mock_db_factory: AsyncMock,
    chat_context: dict[str, Any],
) -> None:
    # 1. Setup Redis mocks — simulate messages in Redis list
    mock_redis = chat_context["redis"]
    mock_redis.lpop.side_effect = [
        '{"messageId": "m1", "chatId": "79991234567", "chatType": "whatsapp", "text": "Hi", "type": "text", "channelId": "ch1", "timestamp": 12345}',
        '{"messageId": "m2", "chatId": "79991234567", "chatType": "whatsapp", "text": "I need help", "type": "text", "channelId": "ch1", "timestamp": 12346}',
        None,  # sentinel: no more messages
    ]

    # 2. Setup DB mocks
    mock_db = AsyncMock()
    mock_db_factory.return_value.__aenter__.return_value = mock_db

    from typing import Any as AnyType

    class MockResult:
        def __init__(self, val: AnyType) -> None:
            self.val = val

        def scalar_one_or_none(self) -> AnyType:
            return self.val

        def scalars(self) -> "MockResult":
            return self

        def first(self) -> AnyType:
            return self.val

    # Simulate: no bot_enabled config, no existing conversation, no message duplicates
    mock_db.execute.side_effect = [
        MockResult(None),  # bot_enabled
        MockResult(None),  # conversation lookup
        MockResult(None),  # message m1 dedup check
        MockResult(None),  # message m2 dedup check
    ]

    # 3. Setup LLM response mock
    from src.llm import LLMResponse

    mock_llm_resp = LLMResponse(
        text="Hello! How can I help?",
        tokens_in=10,
        tokens_out=20,
        cost=0.001,
        model="test-model",
    )
    mock_process_message.return_value = mock_llm_resp

    # 4. Mock Wazzup Provider instance
    mock_provider = AsyncMock()
    mock_provider_class.return_value = mock_provider
    mock_provider.send_text.return_value = "msg_out_1"

    # Execute (no messages arg — reads from Redis)
    await process_incoming_batch(chat_context, "79991234567")

    # Asserts
    mock_process_message.assert_awaited_once()
    mock_provider.send_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_incoming_batch_empty_redis(chat_context: dict[str, Any]) -> None:
    """When Redis list is empty, should exit early without crashing."""
    mock_redis = chat_context["redis"]
    mock_redis.lpop.return_value = None  # no messages

    await process_incoming_batch(chat_context, "79991234567")

    # Should not call anything else
    assert mock_redis.lpop.await_count == 1


@pytest.mark.asyncio
async def test_process_incoming_batch_no_redis() -> None:
    """When context lacks redis entirely, should raise KeyError."""
    with pytest.raises(KeyError, match="redis"):
        await process_incoming_batch({}, "79991234567")
