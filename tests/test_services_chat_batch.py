from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.schemas.webhook import WazzupIncomingMessage
from src.services.chat import process_incoming_batch


class MockResult:
    def __init__(self, val: object) -> None:
        self.val = val

    def scalar_one_or_none(self) -> object:
        return self.val

    def scalar_one(self) -> object:
        return self.val

    def scalars(self) -> MockResult:
        return self

    def first(self) -> object:
        if isinstance(self.val, list):
            return self.val[0] if self.val else None
        return self.val

    def all(self) -> object:
        if isinstance(self.val, list):
            return self.val
        return [self.val] if self.val is not None else []


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

    # Mock conversation to return from scalar_one_or_none on 2nd call
    mock_conv = MagicMock()
    mock_conv.id = "conv-uuid-123"
    mock_conv.phone = "1234567890"
    mock_conv.escalation_status = "none"

    mock_session.execute.side_effect = [
        MockResult(None),  # bot_enabled
        MockResult(None),  # conv lookup (None = create new)
        MockResult([]),  # msg dedup check
        MockResult(2),  # total messages after assistant commit
        MockResult(None),  # no existing summary
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
    mock_redis.enqueue_job.assert_not_called()


@pytest.mark.asyncio
@patch("src.services.chat.async_session_factory")
@patch("src.services.chat.process_message")
@patch("src.services.chat.WazzupProvider")
@patch("src.services.chat.ZohoCRMClient")
@patch("src.services.chat.ZohoInventoryClient")
@patch("src.services.chat.EmbeddingEngine")
async def test_process_incoming_batch_prefers_non_empty_conversation_when_duplicates_exist(
    mock_embedding_cls: MagicMock,
    mock_zoho_inv_cls: MagicMock,
    mock_zoho_crm_cls: MagicMock,
    mock_wazzup_cls: MagicMock,
    mock_process_message: AsyncMock,
    mock_session_factory: MagicMock,
) -> None:
    mock_session = AsyncMock()
    mock_session_factory.return_value.__aenter__.return_value = mock_session

    duplicate_empty = MagicMock()
    duplicate_empty.id = "conv-empty"
    duplicate_empty.phone = "1234567890"
    duplicate_empty.escalation_status = "none"

    populated_conv = MagicMock()
    populated_conv.id = "conv-live"
    populated_conv.phone = "1234567890"
    populated_conv.escalation_status = "none"

    mock_session.execute.side_effect = [
        MockResult(None),  # bot_enabled
        MockResult([duplicate_empty, populated_conv]),  # duplicate conv lookup
        MockResult(["conv-live"]),  # conversations that already have messages
        MockResult([]),  # msg dedup check
        MockResult(10),  # total messages after assistant commit
        MockResult(None),  # no existing summary yet
    ]

    from src.llm import LLMResponse

    mock_process_message.return_value = LLMResponse(
        text="Hello from AI",
        tokens_in=10,
        tokens_out=20,
        cost=0.05,
        model="test-model",
    )
    mock_embedding_cls.return_value = MagicMock()

    mock_zoho_inv = AsyncMock()
    mock_zoho_inv_cls.return_value.__aenter__ = AsyncMock(return_value=mock_zoho_inv)
    mock_zoho_inv_cls.return_value.__aexit__ = AsyncMock(return_value=False)

    mock_zoho_crm = AsyncMock()
    mock_zoho_crm_cls.return_value.__aenter__ = AsyncMock(return_value=mock_zoho_crm)
    mock_zoho_crm_cls.return_value.__aexit__ = AsyncMock(return_value=False)

    mock_wazzup = AsyncMock()
    mock_wazzup_cls.return_value.__aenter__ = AsyncMock(return_value=mock_wazzup)
    mock_wazzup_cls.return_value.__aexit__ = AsyncMock(return_value=False)
    mock_wazzup.send_text.return_value = "msg_out_1"

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

    with patch("src.services.chat.settings.wazzup_channel_id", "chan-1"):
        await process_incoming_batch({"redis": mock_redis}, "1234567890")

    assert mock_process_message.await_args.kwargs["conversation_id"] == "conv-live"
    mock_wazzup.send_text.assert_awaited_once_with(
        chat_id="1234567890", text="Hello from AI"
    )
    mock_redis.enqueue_job.assert_awaited_once_with(
        "refresh_conversation_summary",
        "conv-live",
    )


@pytest.mark.asyncio
@patch("src.services.chat.async_session_factory")
@patch("src.services.chat.process_message")
@patch("src.services.chat.WazzupProvider")
@patch("src.services.chat.ZohoCRMClient")
@patch("src.services.chat.ZohoInventoryClient")
@patch("src.services.chat.EmbeddingEngine")
async def test_process_incoming_batch_enqueues_summary_refresh_when_summary_exists(
    mock_embedding_cls: MagicMock,
    mock_zoho_inv_cls: MagicMock,
    mock_zoho_crm_cls: MagicMock,
    mock_wazzup_cls: MagicMock,
    mock_process_message: AsyncMock,
    mock_session_factory: MagicMock,
) -> None:
    mock_session = AsyncMock()
    mock_session_factory.return_value.__aenter__.return_value = mock_session

    existing_conv = MagicMock()
    existing_conv.id = "conv-with-summary"
    existing_conv.phone = "1234567890"
    existing_conv.escalation_status = "none"

    mock_session.execute.side_effect = [
        MockResult(None),  # bot_enabled
        MockResult(existing_conv),  # single existing conversation
        MockResult([]),  # msg dedup check
        MockResult(4),  # still a short conversation
        MockResult("summary-row"),  # summary already exists
    ]

    from src.llm import LLMResponse

    mock_process_message.return_value = LLMResponse(
        text="Hello again",
        tokens_in=12,
        tokens_out=18,
        cost=0.04,
        model="test-model",
    )
    mock_embedding_cls.return_value = MagicMock()

    mock_zoho_inv = AsyncMock()
    mock_zoho_inv_cls.return_value.__aenter__ = AsyncMock(return_value=mock_zoho_inv)
    mock_zoho_inv_cls.return_value.__aexit__ = AsyncMock(return_value=False)

    mock_zoho_crm = AsyncMock()
    mock_zoho_crm_cls.return_value.__aenter__ = AsyncMock(return_value=mock_zoho_crm)
    mock_zoho_crm_cls.return_value.__aexit__ = AsyncMock(return_value=False)

    mock_wazzup = AsyncMock()
    mock_wazzup_cls.return_value.__aenter__ = AsyncMock(return_value=mock_wazzup)
    mock_wazzup_cls.return_value.__aexit__ = AsyncMock(return_value=False)
    mock_wazzup.send_text.return_value = "msg_out_1"

    mock_redis = AsyncMock()
    msg = WazzupIncomingMessage(
        messageId="msg-2",
        chatId="1234567890",
        chatType="whatsapp",
        type="text",
        text="Any update?",
        channelId="chan-1",
        timestamp=1704067201,
    )
    mock_redis.lpop.side_effect = [msg.model_dump_json(), None]

    with patch("src.services.chat.settings.wazzup_channel_id", "chan-1"):
        await process_incoming_batch({"redis": mock_redis}, "1234567890")

    mock_redis.enqueue_job.assert_awaited_once_with(
        "refresh_conversation_summary",
        "conv-with-summary",
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


@pytest.mark.asyncio
@patch("src.services.chat.async_session_factory")
@patch("src.services.chat.process_message")
@patch("src.services.chat.WazzupProvider")
@patch("src.services.chat.ZohoCRMClient")
@patch("src.services.chat.ZohoInventoryClient")
@patch("src.services.chat.EmbeddingEngine")
async def test_process_incoming_batch_persists_stable_created_at_for_batched_messages(
    mock_embedding_cls: MagicMock,
    mock_zoho_inv_cls: MagicMock,
    mock_zoho_crm_cls: MagicMock,
    mock_wazzup_cls: MagicMock,
    mock_process_message: AsyncMock,
    mock_session_factory: MagicMock,
) -> None:
    mock_session = AsyncMock()
    mock_session_factory.return_value.__aenter__.return_value = mock_session

    existing_conv = MagicMock()
    existing_conv.id = "conv-ordered"
    existing_conv.phone = "1234567890"
    existing_conv.escalation_status = "none"

    mock_session.execute.side_effect = [
        MockResult(None),  # bot_enabled
        MockResult(existing_conv),  # existing conversation
        MockResult([]),  # msg dedup check
        MockResult(3),  # total messages after assistant commit
        MockResult(None),  # no existing summary
    ]

    from src.llm import LLMResponse

    mock_process_message.return_value = LLMResponse(
        text="Ordered reply",
        tokens_in=5,
        tokens_out=7,
        cost=0.01,
        model="test-model",
    )
    mock_embedding_cls.return_value = MagicMock()

    mock_zoho_inv = AsyncMock()
    mock_zoho_inv_cls.return_value.__aenter__ = AsyncMock(return_value=mock_zoho_inv)
    mock_zoho_inv_cls.return_value.__aexit__ = AsyncMock(return_value=False)

    mock_zoho_crm = AsyncMock()
    mock_zoho_crm_cls.return_value.__aenter__ = AsyncMock(return_value=mock_zoho_crm)
    mock_zoho_crm_cls.return_value.__aexit__ = AsyncMock(return_value=False)

    mock_wazzup = AsyncMock()
    mock_wazzup_cls.return_value.__aenter__ = AsyncMock(return_value=mock_wazzup)
    mock_wazzup_cls.return_value.__aexit__ = AsyncMock(return_value=False)
    mock_wazzup.send_text.return_value = "msg_out_1"

    later_msg = WazzupIncomingMessage(
        messageId="msg-later",
        chatId="1234567890",
        chatType="whatsapp",
        type="text",
        text="second in time",
        channelId="chan-1",
        dateTime="2026-04-03T10:00:01.000",
    )
    earlier_msg = WazzupIncomingMessage(
        messageId="msg-earlier",
        chatId="1234567890",
        chatType="whatsapp",
        type="text",
        text="first in time",
        channelId="chan-1",
        dateTime="2026-04-03T10:00:00.000",
    )

    mock_redis = AsyncMock()
    mock_redis.lpop.side_effect = [
        later_msg.model_dump_json(),
        earlier_msg.model_dump_json(),
        None,
    ]

    with patch("src.services.chat.settings.wazzup_channel_id", "chan-1"):
        await process_incoming_batch({"redis": mock_redis}, "1234567890")

    added_messages = [
        call.args[0]
        for call in mock_session.add.call_args_list
        if getattr(call.args[0], "__class__", None).__name__ == "Message"
    ]
    inbound_messages = added_messages[:2]

    assert [message.content for message in inbound_messages] == [
        "first in time",
        "second in time",
    ]
    assert all(isinstance(message.created_at, datetime) for message in inbound_messages)
    assert inbound_messages[0].created_at < inbound_messages[1].created_at
