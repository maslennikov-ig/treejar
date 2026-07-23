from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from arq import Retry

from src.integrations.zoho_oauth import ZohoOAuthError
from src.schemas.webhook import WazzupIncomingMessage
from src.services.chat import (
    InboundBatchTerminalError,
    _handle_escalation_fallback,
    process_incoming_batch,
)
from src.services.inbound_batch import inbound_chat_reference, inbound_queue_key
from src.services.proposal_followup import record_proposal_sent
from src.services.runtime_monitoring import ZOHO_OAUTH_FAILURES_KEY


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


def _assert_bot_reply_sent(
    mock_wazzup: AsyncMock,
    *,
    chat_id: str,
    text: str,
    conversation_id: str,
) -> None:
    mock_wazzup.send_text.assert_awaited_once()
    assert mock_wazzup.send_text.await_args.args == (chat_id, text)
    assert mock_wazzup.send_text.await_args.kwargs["crm_message_id"].startswith(
        f"bot:{conversation_id}:"
    )


@pytest.mark.asyncio
async def test_process_incoming_batch_requeues_transient_zoho_failure_with_backoff() -> (
    None
):
    redis = AsyncMock()
    raw_messages = [
        '{"messageId":"msg-1","chatId":"sensitive-chat","type":"text"}',
        '{"messageId":"msg-2","chatId":"sensitive-chat","type":"text"}',
    ]
    redis.lpop.side_effect = [*raw_messages, None]
    error = ZohoOAuthError("invalid_payload", retryable=True)

    with (
        patch(
            "src.services.chat._process_batch_inner",
            new=AsyncMock(side_effect=error),
        ),
        pytest.raises(Retry) as exc_info,
    ):
        await process_incoming_batch(
            {"redis": redis, "job_try": 1},
            "sensitive-chat",
        )

    redis.lpush.assert_awaited_once_with(
        "wazzup_msgs:sensitive-chat",
        *reversed(raw_messages),
    )
    oauth_call = redis.rpush.await_args
    assert oauth_call.args[0] == ZOHO_OAUTH_FAILURES_KEY
    oauth_record = json.loads(oauth_call.args[1])
    assert oauth_record["error_kind"] == "invalid_payload"
    assert "sensitive-chat" not in oauth_call.args[1]
    assert exc_info.value.defer_score == 2000


@pytest.mark.asyncio
async def test_process_incoming_batch_requeues_unexpected_failure_with_backoff(
    caplog: pytest.LogCaptureFixture,
) -> None:
    redis = AsyncMock()
    chat_id = "+971500001234"
    batch_ref = inbound_chat_reference(chat_id)
    raw_message = json.dumps(
        {
            "messageId": "msg-generic",
            "chatId": chat_id,
            "text": "private customer request",
            "type": "text",
        }
    )
    redis.lpop.side_effect = [raw_message, None]

    with (
        caplog.at_level(logging.INFO),
        patch(
            "src.services.chat._process_batch_inner",
            new=AsyncMock(side_effect=RuntimeError("database unavailable")),
        ),
        pytest.raises(Retry) as exc_info,
    ):
        await process_incoming_batch(
            {"redis": redis, "job_try": 1},
            batch_ref=batch_ref,
        )

    redis.lpush.assert_awaited_once_with(
        inbound_queue_key(batch_ref),
        raw_message,
    )
    assert exc_info.value.defer_score == 2000
    assert chat_id not in caplog.text
    assert "private customer request" not in caplog.text


@pytest.mark.asyncio
async def test_process_incoming_batch_quarantines_exhausted_unexpected_failure() -> (
    None
):
    from src.services import chat

    redis = AsyncMock()
    redis.set.return_value = True
    chat_id = "+971500001235"
    batch_ref = inbound_chat_reference(chat_id)
    raw_message = json.dumps(
        {
            "messageId": "msg-generic-terminal",
            "chatId": chat_id,
            "text": "private terminal request",
            "type": "text",
        }
    )
    redis.lpop.side_effect = [raw_message, None]

    with (
        patch(
            "src.services.chat._process_batch_inner",
            new=AsyncMock(side_effect=RuntimeError("database unavailable")),
        ),
        pytest.raises(RuntimeError, match="database unavailable"),
    ):
        await process_incoming_batch(
            {"redis": redis, "job_try": chat.INBOUND_BATCH_MAX_TRIES},
            batch_ref=batch_ref,
        )

    quarantine_call = redis.set.await_args
    assert quarantine_call.args[0].startswith(chat.INBOUND_BATCH_QUARANTINE_PREFIX)
    assert quarantine_call.kwargs == {
        "ex": chat.settings.inbound_batch_quarantine_ttl_seconds,
        "nx": True,
    }
    assert json.loads(quarantine_call.args[1])["raw_messages"] == [raw_message]
    redis.lpush.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_incoming_batch_requeues_when_quarantine_write_fails() -> None:
    redis = AsyncMock()
    chat_id = "+971500001236"
    batch_ref = inbound_chat_reference(chat_id)
    raw_message = json.dumps(
        {
            "messageId": "msg-terminal-write",
            "chatId": chat_id,
            "type": "text",
        }
    )
    redis.lpop.side_effect = [raw_message, None]
    redis.set.side_effect = RuntimeError("quarantine storage unavailable")

    with (
        patch(
            "src.services.chat._process_batch_inner",
            new=AsyncMock(side_effect=InboundBatchTerminalError("invalid_payload")),
        ),
        pytest.raises(Retry),
    ):
        await process_incoming_batch(
            {"redis": redis, "job_try": 1},
            batch_ref=batch_ref,
        )

    redis.lpush.assert_awaited_once_with(
        inbound_queue_key(batch_ref),
        raw_message,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("retryable", "job_try"),
    [
        (True, 3),
        (False, 1),
    ],
)
async def test_process_incoming_batch_quarantines_terminal_zoho_failure(
    retryable: bool,
    job_try: int,
) -> None:
    from src.services import chat

    redis = AsyncMock()
    raw_message = '{"messageId":"msg-terminal","chatId":"sensitive-chat","type":"text"}'
    redis.lpop.side_effect = [raw_message, None]
    error = ZohoOAuthError(
        "invalid_payload" if retryable else "invalid_credentials",
        retryable=retryable,
    )

    with (
        patch(
            "src.services.chat._process_batch_inner",
            new=AsyncMock(side_effect=error),
        ),
        pytest.raises(ZohoOAuthError),
    ):
        await process_incoming_batch(
            {"redis": redis, "job_try": job_try},
            "sensitive-chat",
        )

    redis.lpush.assert_not_awaited()
    oauth_call, failure_call = redis.rpush.await_args_list
    assert oauth_call.args[0] == chat.ZOHO_OAUTH_FAILURES_KEY
    quarantine_call = redis.set.await_args
    quarantine_key = quarantine_call.args[0]
    assert quarantine_key.startswith(chat.INBOUND_BATCH_QUARANTINE_PREFIX)
    assert json.loads(quarantine_call.args[1])["raw_messages"] == [raw_message]
    assert quarantine_call.kwargs == {
        "ex": chat.settings.inbound_batch_quarantine_ttl_seconds,
        "nx": True,
    }
    assert failure_call.args[0] == chat.INBOUND_BATCH_FAILURES_KEY
    failure_record = json.loads(failure_call.args[1])
    assert (
        failure_record.items()
        >= {
            "attempt": job_try,
            "batch_id": quarantine_key.removeprefix(
                chat.INBOUND_BATCH_QUARANTINE_PREFIX
            ),
            "error_kind": error.kind,
            "message_count": 1,
            "retryable": retryable,
            "status": "terminal",
        }.items()
    )
    assert failure_record["failed_at"].endswith("+00:00")
    assert "sensitive-chat" not in failure_call.args[1]
    assert redis.ltrim.await_args_list[0].args == (
        chat.ZOHO_OAUTH_FAILURES_KEY,
        -1000,
        -1,
    )
    assert redis.ltrim.await_args_list[1].args == (
        chat.INBOUND_BATCH_FAILURES_KEY,
        -1000,
        -1,
    )


def test_bot_reply_id_is_stable_for_replayed_inbound_batch() -> None:
    from src.services.chat import _bot_reply_crm_message_id

    first = _bot_reply_crm_message_id(
        conversation_id="conv-1",
        source_message_id="msg-1",
        combined_text="Need two desks",
    )
    replay = _bot_reply_crm_message_id(
        conversation_id="conv-1",
        source_message_id="msg-1",
        combined_text="Need two desks",
    )

    assert first == replay == "bot:conv-1:msg-1"


@pytest.mark.asyncio
@patch("src.services.chat.send_wazzup_text_with_audit", new_callable=AsyncMock)
async def test_escalation_fallback_normalizes_legacy_arabic_language_marker(
    mock_send_text: AsyncMock,
) -> None:
    conv = MagicMock()
    conv.id = "conv-arabic-fallback"
    conv.phone = "+971501234567"
    conv.language = "العربية"

    redis = AsyncMock()
    redis.get.side_effect = [None, "1"]
    db = AsyncMock()
    wazzup = AsyncMock()

    await _handle_escalation_fallback(
        conv,
        "Any update?",
        wazzup,
        redis,
        db,
    )

    assert "شكراً" in mock_send_text.await_args.kwargs["text"]
    assert "Thank you" not in mock_send_text.await_args.kwargs["text"]


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
    added_objects: list[object] = []
    mock_session.add = MagicMock(side_effect=added_objects.append)

    async def _assign_new_conversation_id() -> None:
        for obj in added_objects:
            if (
                obj.__class__.__name__ == "Conversation"
                and getattr(obj, "id", None) is None
            ):
                obj.id = "conv-uuid-123"

    mock_session.flush.side_effect = _assign_new_conversation_id

    # Mock conversation to return from scalar_one_or_none on 2nd call
    mock_conv = MagicMock()
    mock_conv.id = "conv-uuid-123"
    mock_conv.phone = "1234567890"
    mock_conv.escalation_status = "none"

    mock_session.execute.side_effect = [
        MockResult(None),  # bot_enabled
        MockResult(None),  # conv lookup (None = create new)
        MockResult([]),  # msg dedup check
        MockResult(None),  # outbound audit idempotency lookup
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
    mock_wazzup.resolve_channel_phone = AsyncMock(return_value="+971551220665")

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
    assert mock_process_message.await_args.kwargs["source_message_id"] == "msg-1"
    _assert_bot_reply_sent(
        mock_wazzup,
        chat_id=chat_id,
        text="Hello from AI",
        conversation_id="conv-uuid-123",
    )
    mock_redis.enqueue_job.assert_not_called()


@pytest.mark.asyncio
@patch("src.services.chat.async_session_factory")
@patch("src.services.chat.process_message")
@patch("src.services.chat.WazzupProvider")
@patch("src.services.chat.ZohoCRMClient")
@patch("src.services.chat.ZohoInventoryClient")
@patch("src.services.chat.EmbeddingEngine")
async def test_process_incoming_batch_keeps_batch_successful_when_bot_reply_send_fails(
    mock_embedding_cls: MagicMock,
    mock_zoho_inv_cls: MagicMock,
    mock_zoho_crm_cls: MagicMock,
    mock_wazzup_cls: MagicMock,
    mock_process_message: AsyncMock,
    mock_session_factory: MagicMock,
) -> None:
    from src.llm import LLMResponse

    mock_session = AsyncMock()
    mock_session_factory.return_value.__aenter__.return_value = mock_session
    mock_session.add = MagicMock()

    existing_conv = MagicMock()
    existing_conv.id = "conv-send-fail"
    existing_conv.phone = "1234567890"
    existing_conv.escalation_status = "none"
    existing_conv.metadata_ = {}

    mock_session.execute.side_effect = [
        MockResult(None),  # bot_enabled
        MockResult(existing_conv),  # conversation lookup
        MockResult([]),  # msg dedup check
        MockResult(None),  # outbound audit idempotency lookup
        MockResult(2),  # total messages after assistant commit
        MockResult(None),  # no existing summary
    ]

    mock_process_message.return_value = LLMResponse(
        text="I can help with that.",
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
    mock_wazzup.send_text.side_effect = RuntimeError("Wazzup send failed")
    mock_wazzup.resolve_channel_phone = AsyncMock(return_value="+971551220665")

    mock_redis = AsyncMock()
    msg = WazzupIncomingMessage(
        messageId="msg-send-fail",
        chatId="1234567890",
        chatType="whatsapp",
        type="text",
        text="Hi",
        channelId="chan-1",
        timestamp=1704067200,
    )
    mock_redis.lpop.side_effect = [msg.model_dump_json(), None]

    with patch("src.services.chat.settings.wazzup_channel_id", "chan-1"):
        await process_incoming_batch({"redis": mock_redis}, "1234567890")

    mock_process_message.assert_awaited_once()
    mock_wazzup.send_text.assert_awaited_once()
    added_messages = [
        call.args[0]
        for call in mock_session.add.call_args_list
        if getattr(call.args[0], "__class__", None).__name__ == "Message"
    ]
    assert any(
        message.role == "assistant" and message.content == "I can help with that."
        for message in added_messages
    )


@pytest.mark.asyncio
@patch("src.services.chat.async_session_factory")
@patch("src.services.chat.process_message")
@patch("src.services.chat.WazzupProvider")
@patch("src.services.chat.ZohoCRMClient")
@patch("src.services.chat.ZohoInventoryClient")
@patch("src.services.chat.EmbeddingEngine")
async def test_process_incoming_batch_sends_deferred_product_media_after_bot_reply(
    mock_embedding_cls: MagicMock,
    mock_zoho_inv_cls: MagicMock,
    mock_zoho_crm_cls: MagicMock,
    mock_wazzup_cls: MagicMock,
    mock_process_message: AsyncMock,
    mock_session_factory: MagicMock,
) -> None:
    from src.llm import LLMResponse
    from src.llm.engine import ProductMediaPayload

    mock_session = AsyncMock()
    mock_session_factory.return_value.__aenter__.return_value = mock_session
    mock_session.add = MagicMock()

    existing_conv = MagicMock()
    existing_conv.id = "conv-deferred-media"
    existing_conv.phone = "1234567890"
    existing_conv.escalation_status = "none"
    existing_conv.metadata_ = {}

    mock_session.execute.side_effect = [
        MockResult(None),  # bot_enabled
        MockResult(existing_conv),  # conversation lookup
        MockResult([]),  # msg dedup check
        MockResult(None),  # bot_reply audit idempotency lookup
        MockResult(2),  # total messages after assistant commit
        MockResult(None),  # no existing summary
        MockResult(None),  # product media audit idempotency lookup
        MockResult(None),  # product caption audit idempotency lookup
    ]

    mock_process_message.return_value = LLMResponse(
        text="Hello, here are table options.",
        tokens_in=10,
        tokens_out=20,
        cost=0.05,
        model="test-model",
        deferred_product_media=(
            ProductMediaPayload(
                url="https://example.com/table.jpg",
                caption="Operative table — 179.00 AED",
                product_key="table-1",
                zoho_item_id=None,
            ),
        ),
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
    mock_wazzup.send_text.return_value = "msg-text"
    mock_wazzup.send_media.return_value = "msg-media"
    mock_wazzup.resolve_channel_phone = AsyncMock(return_value="+971551220665")

    mock_redis = AsyncMock()
    msg = WazzupIncomingMessage(
        messageId="msg-1",
        chatId="1234567890",
        chatType="whatsapp",
        type="text",
        text="Hi! I need 15 table",
        channelId="chan-1",
        timestamp=1704067200,
    )
    mock_redis.lpop.side_effect = [msg.model_dump_json(), None]

    with patch("src.services.chat.settings.wazzup_channel_id", "chan-1"):
        await process_incoming_batch({"redis": mock_redis}, "1234567890")

    provider_calls = [call[0] for call in mock_wazzup.method_calls]
    assert provider_calls.index("send_text") < provider_calls.index("send_media")
    mock_wazzup.send_text.assert_awaited_once()
    assert mock_wazzup.send_text.await_args.args[1] == (
        "Hello, here are table options."
    )
    mock_wazzup.send_media.assert_awaited_once()
    assert mock_wazzup.send_media.await_args.kwargs["url"] == (
        "https://example.com/table.jpg"
    )
    assert mock_wazzup.send_media.await_args.kwargs["caption"] is None
    assert mock_wazzup.send_media.await_args.kwargs["caption_crm_message_id"] is None
    caption_audits = [
        call.args[0]
        for call in mock_session.add.call_args_list
        if getattr(call.args[0], "message_type", None) == "caption"
    ]
    assert len(caption_audits) == 1
    assert caption_audits[0].content == "Operative table — 179.00 AED"
    assert caption_audits[0].provider_message_id is None
    assert caption_audits[0].details == {"customer_visible": False}


@pytest.mark.asyncio
@patch("src.services.chat.async_session_factory")
@patch("src.services.chat.process_message")
@patch("src.services.chat.WazzupProvider")
@patch("src.services.chat.ZohoCRMClient")
@patch("src.services.chat.ZohoInventoryClient")
@patch("src.services.chat.EmbeddingEngine")
async def test_process_incoming_batch_refreshes_typing_while_llm_runs(
    mock_embedding_cls: MagicMock,
    mock_zoho_inv_cls: MagicMock,
    mock_zoho_crm_cls: MagicMock,
    mock_wazzup_cls: MagicMock,
    mock_process_message: AsyncMock,
    mock_session_factory: MagicMock,
) -> None:
    from src.llm import LLMResponse

    mock_session = AsyncMock()
    mock_session_factory.return_value.__aenter__.return_value = mock_session
    mock_session.add = MagicMock()

    existing_conv = MagicMock()
    existing_conv.id = "conv-typing"
    existing_conv.phone = "1234567890"
    existing_conv.escalation_status = "none"
    existing_conv.metadata_ = {}

    mock_session.execute.side_effect = [
        MockResult(None),  # bot_enabled
        MockResult(existing_conv),  # conversation lookup
        MockResult([]),  # msg dedup check
        MockResult(None),  # outbound audit idempotency lookup
        MockResult(2),  # total messages after assistant commit
        MockResult(None),  # no existing summary
    ]

    async def _slow_process_message(**_: object) -> LLMResponse:
        await asyncio.sleep(0.025)
        return LLMResponse(
            text="Typing-aware reply",
            tokens_in=10,
            tokens_out=20,
            cost=0.05,
            model="test-model",
        )

    mock_process_message.side_effect = _slow_process_message
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
    mock_wazzup.send_text.return_value = "msg-text"
    mock_wazzup.send_typing = AsyncMock()
    mock_wazzup.resolve_channel_phone = AsyncMock(return_value="+971551220665")

    mock_redis = AsyncMock()
    msg = WazzupIncomingMessage(
        messageId="msg-typing",
        chatId="1234567890",
        chatType="whatsapp",
        type="text",
        text="Hi",
        channelId="chan-1",
        timestamp=1704067200,
    )
    mock_redis.lpop.side_effect = [msg.model_dump_json(), None]

    with (
        patch("src.services.chat.settings.wazzup_channel_id", "chan-1"),
        patch("src.services.chat.TYPING_REFRESH_INTERVAL_SECONDS", 0.01),
    ):
        await process_incoming_batch({"redis": mock_redis}, "1234567890")

    assert mock_wazzup.send_typing.await_count >= 2
    mock_wazzup.send_typing.assert_any_await("1234567890")
    mock_wazzup.send_text.assert_awaited_once()
    mock_wazzup_cls.assert_called_once_with(channel_id="chan-1")


@pytest.mark.asyncio
@patch("src.services.chat.async_session_factory")
@patch("src.services.chat.process_message")
@patch("src.services.chat.WazzupProvider")
@patch("src.services.chat.ZohoCRMClient")
@patch("src.services.chat.ZohoInventoryClient")
@patch("src.services.chat.EmbeddingEngine")
async def test_process_incoming_batch_ignores_typing_failures(
    mock_embedding_cls: MagicMock,
    mock_zoho_inv_cls: MagicMock,
    mock_zoho_crm_cls: MagicMock,
    mock_wazzup_cls: MagicMock,
    mock_process_message: AsyncMock,
    mock_session_factory: MagicMock,
) -> None:
    from src.llm import LLMResponse

    mock_session = AsyncMock()
    mock_session_factory.return_value.__aenter__.return_value = mock_session
    mock_session.add = MagicMock()

    existing_conv = MagicMock()
    existing_conv.id = "conv-typing-failure"
    existing_conv.phone = "1234567890"
    existing_conv.escalation_status = "none"
    existing_conv.metadata_ = {}

    mock_session.execute.side_effect = [
        MockResult(None),  # bot_enabled
        MockResult(existing_conv),  # conversation lookup
        MockResult([]),  # msg dedup check
        MockResult(None),  # outbound audit idempotency lookup
        MockResult(2),  # total messages after assistant commit
        MockResult(None),  # no existing summary
    ]

    mock_process_message.return_value = LLMResponse(
        text="Reply despite typing failure",
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
    mock_wazzup.send_text.return_value = "msg-text"
    mock_wazzup.send_typing = AsyncMock(side_effect=RuntimeError("unsupported"))
    mock_wazzup.resolve_channel_phone = AsyncMock(return_value="+971551220665")

    mock_redis = AsyncMock()
    msg = WazzupIncomingMessage(
        messageId="msg-typing-failure",
        chatId="1234567890",
        chatType="whatsapp",
        type="text",
        text="Hi",
        channelId="chan-1",
        timestamp=1704067200,
    )
    mock_redis.lpop.side_effect = [msg.model_dump_json(), None]

    with patch("src.services.chat.settings.wazzup_channel_id", "chan-1"):
        await process_incoming_batch({"redis": mock_redis}, "1234567890")

    mock_wazzup.send_typing.assert_awaited()
    mock_wazzup.send_text.assert_awaited_once()


@pytest.mark.asyncio
@patch("src.services.chat.async_session_factory")
@patch("src.services.chat.process_message")
@patch("src.services.chat.WazzupProvider")
@patch("src.services.chat.ZohoCRMClient")
@patch("src.services.chat.ZohoInventoryClient")
@patch("src.services.chat.EmbeddingEngine")
async def test_process_incoming_batch_skips_typing_loop_when_provider_unsupported(
    mock_embedding_cls: MagicMock,
    mock_zoho_inv_cls: MagicMock,
    mock_zoho_crm_cls: MagicMock,
    mock_wazzup_cls: MagicMock,
    mock_process_message: AsyncMock,
    mock_session_factory: MagicMock,
) -> None:
    from src.llm import LLMResponse

    mock_session = AsyncMock()
    mock_session_factory.return_value.__aenter__.return_value = mock_session
    mock_session.add = MagicMock()

    existing_conv = MagicMock()
    existing_conv.id = "conv-no-typing-support"
    existing_conv.phone = "1234567890"
    existing_conv.escalation_status = "none"
    existing_conv.metadata_ = {}

    mock_session.execute.side_effect = [
        MockResult(None),  # bot_enabled
        MockResult(existing_conv),  # conversation lookup
        MockResult([]),  # msg dedup check
        MockResult(None),  # outbound audit idempotency lookup
        MockResult(2),  # total messages after assistant commit
        MockResult(None),  # no existing summary
    ]

    mock_process_message.return_value = LLMResponse(
        text="Reply without typing churn",
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
    mock_wazzup.supports_typing_indicator = False
    mock_wazzup_cls.return_value.__aenter__ = AsyncMock(return_value=mock_wazzup)
    mock_wazzup_cls.return_value.__aexit__ = AsyncMock(return_value=False)
    mock_wazzup.send_text.return_value = "msg-text"
    mock_wazzup.send_typing = AsyncMock()
    mock_wazzup.resolve_channel_phone = AsyncMock(return_value="+971551220665")

    mock_redis = AsyncMock()
    msg = WazzupIncomingMessage(
        messageId="msg-no-typing-support",
        chatId="1234567890",
        chatType="whatsapp",
        type="text",
        text="Hi",
        channelId="chan-1",
        timestamp=1704067200,
    )
    mock_redis.lpop.side_effect = [msg.model_dump_json(), None]

    with patch("src.services.chat.settings.wazzup_channel_id", "chan-1"):
        await process_incoming_batch({"redis": mock_redis}, "1234567890")

    mock_wazzup.send_typing.assert_not_awaited()
    mock_wazzup.send_text.assert_awaited_once()


@pytest.mark.asyncio
@patch("src.services.chat.async_session_factory")
@patch("src.services.chat.process_message")
@patch("src.services.chat.WazzupProvider")
@patch("src.services.chat.ZohoCRMClient")
@patch("src.services.chat.ZohoInventoryClient")
@patch("src.services.chat.EmbeddingEngine")
async def test_process_incoming_batch_stops_proposal_followup_on_customer_reply(
    mock_embedding_cls: MagicMock,
    mock_zoho_inv_cls: MagicMock,
    mock_zoho_crm_cls: MagicMock,
    mock_wazzup_cls: MagicMock,
    mock_process_message: AsyncMock,
    mock_session_factory: MagicMock,
) -> None:
    from src.llm import LLMResponse

    mock_session = AsyncMock()
    mock_session_factory.return_value.__aenter__.return_value = mock_session
    mock_session.add = MagicMock()

    existing_conv = MagicMock()
    existing_conv.id = "conv-proposal-followup"
    existing_conv.phone = "1234567890"
    existing_conv.escalation_status = "none"
    existing_conv.metadata_ = {}
    record_proposal_sent(
        existing_conv,
        sent_at=datetime.fromisoformat("2026-05-04T08:00:00+00:00"),
        kp_message_id="quotation-media-1",
    )

    mock_session.execute.side_effect = [
        MockResult(None),  # bot_enabled
        MockResult(existing_conv),  # conversation lookup
        MockResult([]),  # msg dedup check
        MockResult(None),  # outbound audit idempotency lookup
        MockResult(2),  # total messages after assistant commit
        MockResult(None),  # no existing summary
    ]

    mock_process_message.return_value = LLMResponse(
        text="I will update the quotation details.",
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
    mock_wazzup.send_text.return_value = "msg-text"
    mock_wazzup.resolve_channel_phone = AsyncMock(return_value="+971551220665")

    mock_redis = AsyncMock()
    msg = WazzupIncomingMessage(
        messageId="msg-proposal-reply",
        chatId="1234567890",
        chatType="whatsapp",
        type="text",
        text="Please update it for five chairs.",
        channelId="chan-1",
        timestamp=1777896000,
    )
    mock_redis.lpop.side_effect = [msg.model_dump_json(), None]

    with patch("src.services.chat.settings.wazzup_channel_id", "chan-1"):
        await process_incoming_batch({"redis": mock_redis}, "1234567890")

    proposal_state = existing_conv.metadata_["proposal_followup"]
    assert proposal_state["chain_stopped"] is True
    assert proposal_state["stop_reason"] == "customer_reply"
    mock_process_message.assert_awaited_once()
    mock_wazzup.send_text.assert_awaited_once()


@pytest.mark.asyncio
@patch("src.services.chat.async_session_factory")
@patch("src.services.chat.process_message")
@patch("src.services.chat.WazzupProvider")
@patch("src.services.chat.ZohoCRMClient")
@patch("src.services.chat.ZohoInventoryClient")
@patch("src.services.chat.EmbeddingEngine")
async def test_process_incoming_batch_typing_failure_does_not_block_timeout_fallback(
    mock_embedding_cls: MagicMock,
    mock_zoho_inv_cls: MagicMock,
    mock_zoho_crm_cls: MagicMock,
    mock_wazzup_cls: MagicMock,
    mock_process_message: AsyncMock,
    mock_session_factory: MagicMock,
) -> None:
    mock_session = AsyncMock()
    mock_session_factory.return_value.__aenter__.return_value = mock_session
    mock_session.add = MagicMock()

    existing_conv = MagicMock()
    existing_conv.id = "conv-typing-timeout"
    existing_conv.phone = "1234567890"
    existing_conv.escalation_status = "none"
    existing_conv.language = "en"
    existing_conv.metadata_ = {}

    mock_session.execute.side_effect = [
        MockResult(None),  # bot_enabled
        MockResult(existing_conv),  # conversation lookup
        MockResult([]),  # msg dedup check
        MockResult(None),  # timeout fallback audit idempotency lookup
    ]

    async def _never_finishes(**_: object) -> None:
        await asyncio.sleep(0.05)

    mock_process_message.side_effect = _never_finishes
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
    mock_wazzup.send_text.return_value = "msg-timeout"
    mock_wazzup.send_typing = AsyncMock(side_effect=RuntimeError("unsupported"))
    mock_wazzup.resolve_channel_phone = AsyncMock(return_value="+971551220665")

    mock_redis = AsyncMock()
    msg = WazzupIncomingMessage(
        messageId="msg-typing-timeout",
        chatId="1234567890",
        chatType="whatsapp",
        type="text",
        text="Hi",
        channelId="chan-1",
        timestamp=1704067200,
    )
    mock_redis.lpop.side_effect = [msg.model_dump_json(), None]

    with (
        patch("src.services.chat.settings.wazzup_channel_id", "chan-1"),
        patch("src.services.chat.LLM_TIMEOUT", 0.01),
    ):
        await process_incoming_batch({"redis": mock_redis}, "1234567890")

    mock_wazzup.send_typing.assert_awaited()
    mock_wazzup.send_text.assert_awaited_once()
    assert mock_wazzup.send_text.await_args.args == (
        "1234567890",
        "Sorry, I'm currently overloaded. Please try again in a minute.",
    )


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
        MockResult(None),  # outbound audit idempotency lookup
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
    mock_wazzup.resolve_channel_phone = AsyncMock(return_value="+971551220665")

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
    _assert_bot_reply_sent(
        mock_wazzup,
        chat_id="1234567890",
        text="Hello from AI",
        conversation_id="conv-live",
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
@patch(
    "src.services.chat._enqueue_summary_refresh_if_needed",
    new_callable=AsyncMock,
)
async def test_process_incoming_batch_enqueues_summary_refresh_when_summary_exists(
    mock_enqueue_summary: AsyncMock,
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
        MockResult(None),  # outbound audit idempotency lookup
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
    events: list[str] = []

    async def _send_text(*_: object, **__: object) -> str:
        events.append("text_sent")
        return "msg_out_1"

    async def _enqueue_summary(*_: object, **__: object) -> None:
        events.append("summary_enqueued")

    mock_wazzup.send_text.side_effect = _send_text
    mock_enqueue_summary.side_effect = _enqueue_summary
    mock_wazzup.resolve_channel_phone = AsyncMock(return_value="+971551220665")

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

    mock_enqueue_summary.assert_awaited_once_with(
        mock_redis,
        mock_session,
        "conv-with-summary",
    )
    assert events == ["text_sent", "summary_enqueued"]


@pytest.mark.asyncio
@patch("src.services.chat.async_session_factory")
@patch("src.services.chat.process_message")
@patch("src.services.chat.WazzupProvider")
@patch("src.services.chat.ZohoCRMClient")
@patch("src.services.chat.ZohoInventoryClient")
@patch("src.services.chat.EmbeddingEngine")
async def test_process_incoming_batch_persists_inbound_channel_metadata(
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
    existing_conv.id = "conv-with-inbound"
    existing_conv.phone = "1234567890"
    existing_conv.escalation_status = "none"
    existing_conv.metadata_ = {}

    mock_session.execute.side_effect = [
        MockResult(None),  # bot_enabled
        MockResult(existing_conv),  # existing conversation
        MockResult([]),  # msg dedup check
        MockResult(None),  # outbound audit idempotency lookup
        MockResult(2),  # total messages after assistant commit
        MockResult(None),  # no existing summary
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
    mock_wazzup.resolve_channel_phone = AsyncMock(return_value="+971551220665")

    mock_redis = AsyncMock()
    msg = WazzupIncomingMessage(
        messageId="msg-1",
        chatId="1234567890",
        chatType="whatsapp",
        type="text",
        text="Hi there",
        channelId="chan-1",
        timestamp=1704067200,
        source="instagram",
        utm_source="instagram",
        utm_campaign="retargeting",
    )
    mock_redis.lpop.side_effect = [msg.model_dump_json(), None]

    with patch("src.services.chat.settings.wazzup_channel_id", "chan-1"):
        await process_incoming_batch({"redis": mock_redis}, "1234567890")

    assert existing_conv.metadata_["inbound_channel_id"] == "chan-1"
    assert existing_conv.metadata_["inbound_channel_phone"] == "+971551220665"
    assert existing_conv.metadata_["source_attribution"]["original"] == {
        "source": "instagram",
        "channel": "whatsapp",
        "utm": {
            "utm_source": "instagram",
            "utm_campaign": "retargeting",
        },
    }
    assert existing_conv.metadata_["source_attribution"]["latest"] == {
        "source": "instagram",
        "channel": "whatsapp",
        "utm": {
            "utm_source": "instagram",
            "utm_campaign": "retargeting",
        },
    }


@pytest.mark.asyncio
@patch("src.services.chat.async_session_factory")
async def test_process_incoming_batch_quarantines_without_expected_channel(
    mock_session_factory: MagicMock,
) -> None:
    mock_redis = AsyncMock()
    mock_redis.set.return_value = True
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

    with (
        patch("src.services.chat.settings.wazzup_channel_id", ""),
        pytest.raises(
            InboundBatchTerminalError,
            match="wazzup_channel_not_configured",
        ),
    ):
        await process_incoming_batch({"redis": mock_redis}, "1234567890")

    mock_session_factory.assert_not_called()
    assert mock_redis.set.await_args.kwargs["ex"] > 0


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
        MockResult(None),  # outbound audit idempotency lookup
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
    mock_wazzup.resolve_channel_phone = AsyncMock(return_value="+971551220665")

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
