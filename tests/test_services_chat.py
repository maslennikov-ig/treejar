import json
import logging
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.message import Message
from src.services.chat import (
    INBOUND_EXECUTION_STARTED,
    InboundBatchTerminalError,
    _format_for_whatsapp,
    process_incoming_batch,
)


class MockResult:
    def __init__(self, val: Any) -> None:
        self.val = val

    def scalar_one_or_none(self) -> Any:
        return self.val

    def scalar_one(self) -> Any:
        return self.val

    def scalars(self) -> "MockResult":
        return self

    def first(self) -> Any:
        return self.val

    def all(self) -> Any:
        if isinstance(self.val, list):
            return self.val
        return [self.val] if self.val is not None else []


def test_format_for_whatsapp() -> None:
    assert _format_for_whatsapp("Hello") == "Hello"
    assert _format_for_whatsapp("## Header") == "*Header*"
    assert _format_for_whatsapp("### **Header Bold**") == "*Header Bold*"
    assert _format_for_whatsapp("**Bold Text**") == "*Bold Text*"
    assert _format_for_whatsapp("***Bold Italic***") == "*Bold Italic*"
    assert _format_for_whatsapp("*Already correct*") == "*Already correct*"
    assert (
        _format_for_whatsapp("Check this link: [OpenAI](https://openai.com)")
        == "Check this link: OpenAI: https://openai.com"
    )
    assert _format_for_whatsapp("![Image](https://image.com/img.png)") == "Image"
    assert _format_for_whatsapp("**🪑 Our Top Picks:**") == "*🪑 Our Top Picks:*"
    assert _format_for_whatsapp("## **1. Executive Chair**") == "*1. Executive Chair*"
    assert _format_for_whatsapp("`inline code`") == "```inline code```"
    assert (
        _format_for_whatsapp("This is `code1` and `code2`")
        == "This is ```code1``` and ```code2```"
    )


def test_format_for_whatsapp_tables() -> None:
    """Markdown tables should be converted to key-value lists."""
    # Simple 2-column table
    table = "| Product | Price |\n| --- | --- |\n| Chair | 1200 AED |"
    expected = "*Product:* Chair\n*Price:* 1200 AED"
    assert _format_for_whatsapp(table) == expected

    # Multi-row table
    table_multi = (
        "| Name | Price | Stock |\n"
        "| --- | --- | --- |\n"
        "| Chair | 1200 | 5 |\n"
        "| Desk | 3500 | 2 |"
    )
    expected_multi = (
        "*Name:* Chair\n*Price:* 1200\n*Stock:* 5\n"
        "\n"
        "*Name:* Desk\n*Price:* 3500\n*Stock:* 2"
    )
    assert _format_for_whatsapp(table_multi) == expected_multi

    # Table with surrounding text
    mixed = "Here is a comparison:\n| A | B |\n| --- | --- |\n| 1 | 2 |\nEnd of table."
    expected_mixed = "Here is a comparison:\n*A:* 1\n*B:* 2\nEnd of table."
    assert _format_for_whatsapp(mixed) == expected_mixed

    # No table — should pass through unchanged
    no_table = "Just regular text with | pipes | in it."
    assert _format_for_whatsapp(no_table) == no_table


def _seed_inbound_redis(redis: AsyncMock, raw_messages: list[str]) -> None:
    redis.set.return_value = True
    redis.get.return_value = None
    redis.lrange.return_value = []
    redis.lmove.side_effect = [*raw_messages, None]
    redis.eval.return_value = 0


@pytest.fixture
def chat_context() -> dict[str, Any]:
    mock_redis = AsyncMock()
    _seed_inbound_redis(mock_redis, [])
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
    _seed_inbound_redis(
        mock_redis,
        [
            '{"messageId": "m1", "chatId": "79991234567", "chatType": "whatsapp", "text": "Hi", "type": "text", "channelId": "ch1", "timestamp": 12345}',
            '{"messageId": "m2", "chatId": "79991234567", "chatType": "whatsapp", "text": "I need help", "type": "text", "channelId": "ch1", "timestamp": 12346}',
        ],
    )

    # 2. Setup DB mocks
    mock_db = AsyncMock()
    mock_db_factory.return_value.__aenter__.return_value = mock_db

    class MockResult:
        def __init__(self, val: Any) -> None:
            self.val = val

        def scalar_one_or_none(self) -> Any:
            return self.val

        def scalar_one(self) -> Any:
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
        MockResult(None),  # outbound audit lookup
        MockResult(4),  # total messages after assistant commit
        MockResult(None),  # no existing summary
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
    with patch("src.services.chat.settings.wazzup_channel_id", "ch1"):
        await process_incoming_batch(chat_context, "79991234567")

    # Asserts
    mock_process_message.assert_awaited_once()
    mock_provider.send_text.assert_awaited_once()
    mock_redis.enqueue_job.assert_not_called()


@pytest.mark.asyncio
async def test_process_incoming_batch_empty_redis(chat_context: dict[str, Any]) -> None:
    """When Redis list is empty, should exit early without crashing."""
    mock_redis = chat_context["redis"]
    _seed_inbound_redis(mock_redis, [])

    await process_incoming_batch(chat_context, "79991234567")

    # Should not call anything else
    mock_redis.lrange.assert_awaited_once()
    mock_redis.lmove.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_incoming_batch_no_redis() -> None:
    """When context lacks redis entirely, should raise KeyError."""
    with pytest.raises(KeyError, match="redis"):
        await process_incoming_batch({}, "79991234567")


@pytest.mark.asyncio
@patch("src.services.chat.async_session_factory")
@patch("src.services.chat.WazzupProvider")
async def test_audio_transcription_is_not_replayed_after_late_failure(
    mock_provider_class: MagicMock,
    mock_db_factory: MagicMock,
) -> None:
    from arq import Retry

    chat_id = "79991234567"
    raw_message = json.dumps(
        {
            "messageId": "audio-replay-guard",
            "chatId": chat_id,
            "chatType": "whatsapp",
            "type": "voice",
            "channelId": "ch1",
            "status": "inbound",
            "authorType": "client",
            "dateTime": "2026-04-30T10:00:00.000",
            "media": {
                "url": "https://cdn.wazzup24.com/files/replay-guard.ogg",
                "mimeType": "audio/ogg",
            },
        }
    )
    redis = AsyncMock()
    _seed_inbound_redis(redis, [raw_message])

    provider = AsyncMock()
    provider.download_media.return_value = b"audio-bytes"
    mock_provider_class.return_value.__aenter__ = AsyncMock(return_value=provider)
    mock_provider_class.return_value.__aexit__ = AsyncMock(return_value=False)

    db = AsyncMock()
    db.execute.side_effect = RuntimeError("database unavailable after transcription")
    mock_db_factory.return_value.__aenter__.return_value = db

    transcription = SimpleNamespace(
        text="one external transcription",
        tokens_in=10,
        tokens_out=2,
        total_tokens=12,
        cost=0.001,
        model="openai/gpt-audio-mini",
    )
    transcribe_with_metadata = AsyncMock(return_value=transcription)

    with (
        patch(
            "src.integrations.voice.voxtral.transcribe_audio_with_metadata",
            transcribe_with_metadata,
            create=True,
        ),
        patch("src.services.chat.settings.wazzup_channel_id", "ch1"),
        pytest.raises(Retry),
    ):
        await process_incoming_batch(
            {"redis": redis, "job_try": 1},
            chat_id,
        )

    transcribe_with_metadata.assert_awaited_once()
    assert any(
        len(call.args) > 1 and call.args[1] == INBOUND_EXECUTION_STARTED
        for call in redis.set.await_args_list
    )

    redis.set.reset_mock()
    redis.set.return_value = True
    redis.get.return_value = INBOUND_EXECUTION_STARTED
    redis.lrange.return_value = [raw_message]
    redis.lmove.reset_mock(side_effect=True)
    inner = AsyncMock()

    with (
        patch("src.services.chat._process_batch_inner", inner),
        pytest.raises(InboundBatchTerminalError, match="uncertain_replay"),
    ):
        await process_incoming_batch(
            {"redis": redis, "job_try": 2},
            chat_id,
        )

    inner.assert_not_awaited()
    transcribe_with_metadata.assert_awaited_once()


@pytest.mark.asyncio
@patch("src.services.chat.async_session_factory")
@patch("src.services.chat.WazzupProvider")
@patch("src.services.chat.ZohoCRMClient")
@patch("src.services.chat.ZohoInventoryClient")
@patch("src.services.chat.process_message")
@patch("src.services.chat.EmbeddingEngine")
async def test_audio_transcription_metadata_is_persisted_for_user_message(
    mock_embedding_cls: MagicMock,
    mock_process_message: AsyncMock,
    mock_zoho_inv_cls: MagicMock,
    mock_zoho_crm_cls: MagicMock,
    mock_provider_class: MagicMock,
    mock_db_factory: MagicMock,
    chat_context: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    chat_id = "79991234567"
    audio_url = "https://cdn.wazzup24.com/files/voice.ogg"
    mock_redis = chat_context["redis"]
    _seed_inbound_redis(
        mock_redis,
        [
            json.dumps(
                {
                    "messageId": "audio-001",
                    "chatId": chat_id,
                    "chatType": "whatsapp",
                    "type": "voice",
                    "channelId": "ch1",
                    "status": "inbound",
                    "authorType": "client",
                    "dateTime": "2026-04-30T10:00:00.000",
                    "media": {"url": audio_url, "mimeType": "audio/ogg"},
                }
            ),
        ],
    )

    mock_db = AsyncMock()
    mock_db_factory.return_value.__aenter__.return_value = mock_db

    mock_conv = MagicMock()
    mock_conv.id = "conv-uuid-123"
    mock_conv.phone = chat_id
    mock_conv.escalation_status = "none"
    mock_conv.language = "en"
    mock_conv.metadata_ = {}
    mock_db.execute.side_effect = [
        MockResult(None),  # bot_enabled config lookup
        MockResult(mock_conv),  # conversation lookup
        MockResult([]),  # batch messages dedup check
        MockResult(None),  # outbound audit lookup
        MockResult(2),  # total messages after assistant commit
        MockResult(None),  # no existing summary
    ]

    from src.llm import LLMResponse

    mock_process_message.return_value = LLMResponse(
        text="Sure, I can help with chairs.",
        tokens_in=10,
        tokens_out=20,
        cost=0.001,
        model="test-model",
    )
    mock_embedding_cls.return_value = MagicMock()

    mock_zoho_inv = AsyncMock()
    mock_zoho_inv_cls.return_value.__aenter__ = AsyncMock(return_value=mock_zoho_inv)
    mock_zoho_inv_cls.return_value.__aexit__ = AsyncMock(return_value=False)
    mock_zoho_crm = AsyncMock()
    mock_zoho_crm_cls.return_value.__aenter__ = AsyncMock(return_value=mock_zoho_crm)
    mock_zoho_crm_cls.return_value.__aexit__ = AsyncMock(return_value=False)

    mock_provider = AsyncMock()
    mock_provider.download_media.return_value = b"audio-bytes"
    mock_provider.resolve_channel_phone.return_value = None
    mock_provider.send_text.return_value = "msg_out_1"
    mock_provider_class.return_value.__aenter__ = AsyncMock(return_value=mock_provider)
    mock_provider_class.return_value.__aexit__ = AsyncMock(return_value=False)

    transcription = SimpleNamespace(
        text="I need two office chairs",
        tokens_in=120,
        tokens_out=8,
        total_tokens=128,
        cost=0.00042,
        model="openai/gpt-audio-mini",
    )
    transcribe_with_metadata = AsyncMock(return_value=transcription)
    legacy_transcribe = AsyncMock(
        side_effect=AssertionError("legacy string-only transcription path used")
    )

    with (
        patch(
            "src.integrations.voice.voxtral.transcribe_audio_with_metadata",
            transcribe_with_metadata,
            create=True,
        ),
        patch("src.integrations.voice.voxtral.transcribe_audio", legacy_transcribe),
        patch("src.services.chat.settings.wazzup_channel_id", "ch1"),
        caplog.at_level(logging.INFO, logger="src.services.chat"),
    ):
        await process_incoming_batch(chat_context, chat_id)

    legacy_transcribe.assert_not_awaited()
    transcribe_with_metadata.assert_awaited_once()
    mock_process_message.assert_awaited_once()
    assert (
        mock_process_message.await_args.kwargs["combined_text"]
        == "I need two office chairs"
    )

    added_messages = [
        call.args[0]
        for call in mock_db.add.call_args_list
        if isinstance(call.args[0], Message)
    ]
    user_message = next(msg for msg in added_messages if msg.role == "user")
    assert user_message.message_type == "voice"
    assert user_message.audio_url == audio_url
    assert user_message.transcription == "I need two office chairs"
    assert user_message.tokens_in == 120
    assert user_message.tokens_out == 8
    assert user_message.cost == 0.00042
    assert user_message.model == "openai/gpt-audio-mini"
    assert chat_id not in caplog.text
    assert audio_url not in caplog.text
    assert transcription.text not in caplog.text


@pytest.mark.asyncio
@patch("src.services.chat.async_session_factory")
@patch("src.services.chat.WazzupProvider")
@patch("src.services.chat.process_message")
async def test_audio_only_oversized_message_sends_safe_fallback_without_llm(
    mock_process_message: AsyncMock,
    mock_provider_class: MagicMock,
    mock_db_factory: MagicMock,
    chat_context: dict[str, Any],
) -> None:
    from src.integrations.voice.voxtral import MAX_AUDIO_SIZE

    chat_id = "79991234567"
    audio_url = "https://cdn.wazzup24.com/files/too-large.ogg"
    mock_redis = chat_context["redis"]
    _seed_inbound_redis(
        mock_redis,
        [
            json.dumps(
                {
                    "messageId": "audio-too-large",
                    "chatId": chat_id,
                    "chatType": "whatsapp",
                    "type": "voice",
                    "channelId": "ch1",
                    "status": "inbound",
                    "authorType": "client",
                    "dateTime": "2026-04-30T10:00:00.000",
                    "media": {"url": audio_url, "mimeType": "audio/ogg"},
                }
            ),
        ],
    )

    mock_db = AsyncMock()
    mock_db_factory.return_value.__aenter__.return_value = mock_db
    mock_conv = MagicMock()
    mock_conv.id = "conv-uuid-123"
    mock_conv.phone = chat_id
    mock_conv.escalation_status = "none"
    mock_conv.language = "en"
    mock_conv.metadata_ = {}
    mock_db.execute.side_effect = [
        MockResult(None),  # bot_enabled config lookup
        MockResult(mock_conv),  # conversation lookup
        MockResult([]),  # batch messages dedup check
        MockResult(None),  # outbound audit lookup for voice fallback
    ]

    mock_provider = AsyncMock()
    mock_provider.download_media.return_value = b"x" * (MAX_AUDIO_SIZE + 1)
    mock_provider.resolve_channel_phone.return_value = None
    mock_provider.send_text.return_value = "voice_fallback_1"
    mock_provider_class.return_value.__aenter__ = AsyncMock(return_value=mock_provider)
    mock_provider_class.return_value.__aexit__ = AsyncMock(return_value=False)
    transcribe_with_metadata = AsyncMock(
        side_effect=AssertionError("oversized audio should not reach transcription")
    )

    with (
        patch(
            "src.integrations.voice.voxtral.transcribe_audio_with_metadata",
            transcribe_with_metadata,
            create=True,
        ),
        patch("src.services.chat.settings.wazzup_channel_id", "ch1"),
    ):
        await process_incoming_batch(chat_context, chat_id)

    transcribe_with_metadata.assert_not_awaited()
    mock_process_message.assert_not_awaited()
    mock_provider.send_text.assert_awaited_once()
    sent_text = mock_provider.send_text.await_args.args[1]
    assert "couldn't understand the voice message" in sent_text

    added_messages = [
        call.args[0]
        for call in mock_db.add.call_args_list
        if isinstance(call.args[0], Message)
    ]
    user_message = next(msg for msg in added_messages if msg.role == "user")
    assistant_message = next(msg for msg in added_messages if msg.role == "assistant")
    assert user_message.audio_url == audio_url
    assert "file too large" in (user_message.transcription or "")
    assert assistant_message.model == "voice_fallback"


@pytest.mark.asyncio
@patch("src.services.chat.async_session_factory")
@patch("src.services.chat.WazzupProvider")
@patch("src.services.chat.process_message")
async def test_audio_only_transcription_error_sends_safe_fallback_without_llm(
    mock_process_message: AsyncMock,
    mock_provider_class: MagicMock,
    mock_db_factory: MagicMock,
    chat_context: dict[str, Any],
) -> None:
    chat_id = "79991234567"
    audio_url = "https://cdn.wazzup24.com/files/unreadable.ogg"
    mock_redis = chat_context["redis"]
    _seed_inbound_redis(
        mock_redis,
        [
            json.dumps(
                {
                    "messageId": "audio-unreadable",
                    "chatId": chat_id,
                    "chatType": "whatsapp",
                    "type": "audio",
                    "channelId": "ch1",
                    "status": "inbound",
                    "authorType": "client",
                    "dateTime": "2026-04-30T10:00:00.000",
                    "media": {"url": audio_url, "mimeType": "audio/ogg"},
                }
            ),
        ],
    )

    mock_db = AsyncMock()
    mock_db_factory.return_value.__aenter__.return_value = mock_db
    mock_conv = MagicMock()
    mock_conv.id = "conv-uuid-123"
    mock_conv.phone = chat_id
    mock_conv.escalation_status = "none"
    mock_conv.language = "en"
    mock_conv.metadata_ = {}
    mock_db.execute.side_effect = [
        MockResult(None),  # bot_enabled config lookup
        MockResult(mock_conv),  # conversation lookup
        MockResult([]),  # batch messages dedup check
        MockResult(None),  # outbound audit lookup for voice fallback
    ]

    mock_provider = AsyncMock()
    mock_provider.download_media.return_value = b"audio-bytes"
    mock_provider.resolve_channel_phone.return_value = None
    mock_provider.send_text.return_value = "voice_fallback_1"
    mock_provider_class.return_value.__aenter__ = AsyncMock(return_value=mock_provider)
    mock_provider_class.return_value.__aexit__ = AsyncMock(return_value=False)
    transcribe_with_metadata = AsyncMock(side_effect=ValueError("bad audio"))

    with (
        patch(
            "src.integrations.voice.voxtral.transcribe_audio_with_metadata",
            transcribe_with_metadata,
            create=True,
        ),
        patch("src.services.chat.settings.wazzup_channel_id", "ch1"),
    ):
        await process_incoming_batch(chat_context, chat_id)

    transcribe_with_metadata.assert_awaited_once()
    mock_process_message.assert_not_awaited()
    mock_provider.send_text.assert_awaited_once()

    added_messages = [
        call.args[0]
        for call in mock_db.add.call_args_list
        if isinstance(call.args[0], Message)
    ]
    user_message = next(msg for msg in added_messages if msg.role == "user")
    assistant_message = next(msg for msg in added_messages if msg.role == "assistant")
    assert user_message.audio_url == audio_url
    assert "error during processing" in (user_message.transcription or "")
    assert assistant_message.model == "voice_fallback"
