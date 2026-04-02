from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.schemas.webhook import WazzupIncomingMessage
from src.services.chat import process_incoming_batch


@pytest.mark.asyncio
@patch("src.services.chat.async_session_factory")
@patch("src.services.chat.process_message")
@patch("src.services.chat.WazzupProvider")
@patch("src.services.chat.ZohoCRMClient")
@patch("src.services.chat.ZohoInventoryClient")
@patch("src.services.chat.EmbeddingEngine")
async def test_process_incoming_batch_new_conversation(
    mock_embedding_cls: MagicMock,
    mock_zoho_inv_cls: MagicMock,
    mock_zoho_crm_cls: MagicMock,
    mock_wazzup_cls: MagicMock,
    mock_process_message: AsyncMock,
    mock_session_factory: MagicMock,
) -> None:
    # Set up mocks
    mock_session = AsyncMock()
    mock_session_factory.return_value.__aenter__.return_value = mock_session

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

        def all(self) -> Any:
            if isinstance(self.val, list):
                return self.val
            return [self.val] if self.val is not None else []

    # Mock conversation to return from scalar_one_or_none on 2nd call
    mock_conv = MagicMock()
    mock_conv.id = "conv-uuid-123"
    mock_conv.phone = "1234567890"
    mock_conv.escalation_status = "none"

    mock_session.execute.side_effect = [
        MockResult(None),  # bot_enabled
        MockResult(None),  # conv lookup (None = create new)
        MockResult([]),  # msg dedup check
    ]

    # Simulate LLM response
    from src.llm import LLMResponse

    mock_llm_response = LLMResponse(
        text="Hello from AI",
        tokens_in=10,
        tokens_out=20,
        cost=0.05,
        model="test-model",
    )
    mock_process_message.return_value = mock_llm_response

    # Mock EmbeddingEngine
    mock_embedding_cls.return_value = MagicMock()

    # Mock ZohoInventoryClient context manager
    mock_zoho_inv = AsyncMock()
    mock_zoho_inv_cls.return_value.__aenter__ = AsyncMock(return_value=mock_zoho_inv)
    mock_zoho_inv_cls.return_value.__aexit__ = AsyncMock(return_value=False)

    # Mock ZohoCRMClient context manager
    mock_zoho_crm = AsyncMock()
    mock_zoho_crm_cls.return_value.__aenter__ = AsyncMock(return_value=mock_zoho_crm)
    mock_zoho_crm_cls.return_value.__aexit__ = AsyncMock(return_value=False)

    # Mock WazzupProvider context manager
    mock_wazzup = AsyncMock()
    mock_wazzup_cls.return_value.__aenter__ = AsyncMock(return_value=mock_wazzup)
    mock_wazzup_cls.return_value.__aexit__ = AsyncMock(return_value=False)
    mock_wazzup.send_text.return_value = "msg_out_1"

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

    with patch("src.services.chat.settings.wazzup_channel_id", "chan-1"):
        await process_incoming_batch(ctx, chat_id)

    # Assertions
    mock_session.commit.assert_awaited()
    mock_process_message.assert_awaited_once()
    mock_wazzup.send_text.assert_awaited_once_with(
        chat_id=chat_id, text="Hello from AI"
    )


@pytest.mark.asyncio
@patch("src.services.chat.async_session_factory")
async def test_process_incoming_batch_skips_without_expected_channel(
    mock_session_factory: MagicMock,
) -> None:
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

    with patch("src.services.chat.settings.wazzup_channel_id", ""):
        await process_incoming_batch({"redis": mock_redis}, "1234567890")

    mock_session_factory.assert_not_called()
