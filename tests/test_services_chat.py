from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

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
@patch("src.services.chat.ZohoCRMClient")
@patch("src.services.chat.ZohoInventoryClient")
@patch("src.services.chat.process_message")
@patch("src.services.chat.EmbeddingEngine")
async def test_process_incoming_batch_success(
    mock_embedding_cls: MagicMock,
    mock_process_message: AsyncMock,
    mock_zoho_inv_cls: MagicMock,
    mock_zoho_crm_cls: MagicMock,
    mock_provider_class: MagicMock,
    mock_db_factory: MagicMock,
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

    class MockResult:
        def __init__(self, val: Any) -> None:
            self.val = val

        def scalar_one_or_none(self) -> Any:
            return self.val

        def scalars(self) -> "MockResult":
            return self

        def first(self) -> Any:
            return self.val

        def all(self) -> Any:
            if isinstance(self.val, list):
                return self.val
            return [self.val] if self.val is not None else []

    # Mock conversation to return from scalar_one_or_none
    mock_conv = MagicMock()
    mock_conv.id = "conv-uuid-123"
    mock_conv.phone = "79991234567"
    mock_conv.escalation_status = "none"

    # Simulate: no bot_enabled config, existing conversation found, empty message dedup
    mock_db.execute.side_effect = [
        MockResult(None),  # bot_enabled config lookup
        MockResult(mock_conv),  # conversation lookup
        MockResult([]),  # batch messages dedup check
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

    # 4. Mock EmbeddingEngine
    mock_embedding_cls.return_value = MagicMock()

    # 5. Mock ZohoInventoryClient context manager
    mock_zoho_inv = AsyncMock()
    mock_zoho_inv_cls.return_value.__aenter__ = AsyncMock(return_value=mock_zoho_inv)
    mock_zoho_inv_cls.return_value.__aexit__ = AsyncMock(return_value=False)

    # 6. Mock ZohoCRMClient context manager
    mock_zoho_crm = AsyncMock()
    mock_zoho_crm_cls.return_value.__aenter__ = AsyncMock(return_value=mock_zoho_crm)
    mock_zoho_crm_cls.return_value.__aexit__ = AsyncMock(return_value=False)

    # 7. Mock WazzupProvider context manager
    mock_provider = AsyncMock()
    mock_provider_class.return_value.__aenter__ = AsyncMock(return_value=mock_provider)
    mock_provider_class.return_value.__aexit__ = AsyncMock(return_value=False)
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
