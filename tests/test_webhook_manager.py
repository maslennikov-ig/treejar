from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.services.auto_faq import AutoFAQSaveResult
from src.services.auto_faq_types import AutoFAQCandidate

client = TestClient(app)
EXPECTED_CHANNEL_ID = "b49b1b9d-757f-4104-b56d-8f43d62cc515"


@pytest.fixture(autouse=True)
def _skip_ip_check() -> None:  # type: ignore[misc]
    """Skip IP allowlist verification for all tests in this module."""
    with patch("src.api.v1.webhook._parse_allowed_networks", return_value=[]):
        yield


def _setup_mocks() -> tuple[AsyncMock, AsyncMock]:
    mock_redis = AsyncMock()
    mock_arq = AsyncMock()
    app.state.redis = mock_redis
    app.state.arq_pool = mock_arq
    return mock_redis, mock_arq


def test_client_message_processed() -> None:
    """Client messages (authorType=client) are pushed and enqueued."""
    mock_redis, mock_arq = _setup_mocks()

    payload = {
        "messages": [
            {
                "messageId": "msg-c1",
                "chatId": "971551220665",
                "chatType": "whatsapp",
                "text": "Hello!",
                "type": "text",
                "channelId": EXPECTED_CHANNEL_ID,
                "timestamp": 1234567890,
                "authorType": "client",
            }
        ]
    }

    with patch("src.api.v1.webhook.settings.wazzup_channel_id", EXPECTED_CHANNEL_ID):
        response = client.post("/api/v1/webhook/wazzup", json=payload)

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    mock_redis.rpush.assert_called_once()
    mock_arq.enqueue_job.assert_called_once()


def test_manager_message_processed() -> None:
    """Manager messages (authorType=manager) are pushed and enqueued."""
    mock_redis, mock_arq = _setup_mocks()

    payload = {
        "messages": [
            {
                "messageId": "msg-m1",
                "chatId": "971551220665",
                "chatType": "whatsapp",
                "text": "I'll handle this client",
                "type": "text",
                "channelId": EXPECTED_CHANNEL_ID,
                "timestamp": 1234567890,
                "authorType": "manager",
                "isEcho": True,
                "authorId": "mgr-001",
                "authorName": "Israullah",
            }
        ]
    }

    with patch("src.api.v1.webhook.settings.wazzup_channel_id", EXPECTED_CHANNEL_ID):
        response = client.post("/api/v1/webhook/wazzup", json=payload)

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    mock_redis.rpush.assert_called_once()
    mock_arq.enqueue_job.assert_called_once()


def test_bot_message_skipped() -> None:
    """Bot messages (authorType=bot) are skipped entirely."""
    mock_redis, mock_arq = _setup_mocks()

    payload = {
        "messages": [
            {
                "messageId": "msg-b1",
                "chatId": "971551220665",
                "chatType": "whatsapp",
                "text": "Bot auto-reply",
                "type": "text",
                "channelId": EXPECTED_CHANNEL_ID,
                "timestamp": 1234567890,
                "authorType": "bot",
                "isEcho": False,
            }
        ]
    }

    with patch("src.api.v1.webhook.settings.wazzup_channel_id", EXPECTED_CHANNEL_ID):
        response = client.post("/api/v1/webhook/wazzup", json=payload)

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    mock_redis.rpush.assert_not_called()
    mock_arq.enqueue_job.assert_not_called()


def test_missing_author_type_treated_as_client() -> None:
    """Messages without authorType are treated as client messages."""
    mock_redis, mock_arq = _setup_mocks()

    payload = {
        "messages": [
            {
                "messageId": "msg-no-author",
                "chatId": "971551220665",
                "chatType": "whatsapp",
                "text": "Hi there",
                "type": "text",
                "channelId": EXPECTED_CHANNEL_ID,
                "timestamp": 1234567890,
            }
        ]
    }

    with patch("src.api.v1.webhook.settings.wazzup_channel_id", EXPECTED_CHANNEL_ID):
        response = client.post("/api/v1/webhook/wazzup", json=payload)

    assert response.status_code == 200
    mock_redis.rpush.assert_called_once()
    mock_arq.enqueue_job.assert_called_once()


def test_mixed_batch_routes_correctly() -> None:
    """Mixed batch: client msg processed, bot msg skipped."""
    mock_redis, mock_arq = _setup_mocks()

    payload = {
        "messages": [
            {
                "messageId": "msg-c2",
                "chatId": "971551220665",
                "chatType": "whatsapp",
                "text": "Client msg",
                "type": "text",
                "channelId": EXPECTED_CHANNEL_ID,
                "timestamp": 1234567890,
                "authorType": "client",
            },
            {
                "messageId": "msg-b2",
                "chatId": "971551220665",
                "chatType": "whatsapp",
                "text": "Bot echo",
                "type": "text",
                "channelId": EXPECTED_CHANNEL_ID,
                "timestamp": 1234567891,
                "authorType": "bot",
            },
        ]
    }

    with patch("src.api.v1.webhook.settings.wazzup_channel_id", EXPECTED_CHANNEL_ID):
        response = client.post("/api/v1/webhook/wazzup", json=payload)

    assert response.status_code == 200
    # Only 1 message pushed (client), bot skipped
    assert mock_redis.rpush.call_count == 1
    assert mock_arq.enqueue_job.call_count == 1


def test_unexpected_channel_skipped() -> None:
    """Messages from another Wazzup channel are ignored."""
    mock_redis, mock_arq = _setup_mocks()

    payload = {
        "messages": [
            {
                "messageId": "msg-foreign",
                "chatId": "971501234567",
                "chatType": "whatsapp",
                "text": "Need a manager now",
                "type": "text",
                "channelId": "foreign-channel-id",
                "timestamp": 1234567890,
                "authorType": "client",
            }
        ]
    }

    with patch("src.api.v1.webhook.settings.wazzup_channel_id", EXPECTED_CHANNEL_ID):
        response = client.post("/api/v1/webhook/wazzup", json=payload)

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    mock_redis.rpush.assert_not_called()
    mock_arq.enqueue_job.assert_not_called()


def test_missing_expected_channel_skips_all_messages() -> None:
    """Fail closed: without configured channel, webhook must not process messages."""
    mock_redis, mock_arq = _setup_mocks()

    payload = {
        "messages": [
            {
                "messageId": "msg-no-config",
                "chatId": "971551220665",
                "chatType": "whatsapp",
                "text": "Hello?",
                "type": "text",
                "channelId": EXPECTED_CHANNEL_ID,
                "timestamp": 1234567890,
                "authorType": "client",
            }
        ]
    }

    with patch("src.api.v1.webhook.settings.wazzup_channel_id", ""):
        response = client.post("/api/v1/webhook/wazzup", json=payload)

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    mock_redis.rpush.assert_not_called()
    mock_arq.enqueue_job.assert_not_called()


def test_missing_message_channel_id_skipped() -> None:
    """Fail closed: messages without channelId must not be processed."""
    mock_redis, mock_arq = _setup_mocks()

    payload = {
        "messages": [
            {
                "messageId": "msg-no-channel",
                "chatId": "971551220665",
                "chatType": "whatsapp",
                "text": "Hello?",
                "type": "text",
                "timestamp": 1234567890,
                "authorType": "client",
            }
        ]
    }

    with patch("src.api.v1.webhook.settings.wazzup_channel_id", EXPECTED_CHANNEL_ID):
        response = client.post("/api/v1/webhook/wazzup", json=payload)

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    mock_redis.rpush.assert_not_called()
    mock_arq.enqueue_job.assert_not_called()


@pytest.mark.asyncio
async def test_private_manager_reply_uses_one_adapter_call_without_kb_candidate() -> (
    None
):
    from src.api.telegram_webhook import _handle_manager_reply

    conv_id = str(uuid.uuid4())
    redis = AsyncMock()
    redis.get.return_value = json.dumps(
        {
            "conversation_id": conv_id,
            "mode": "faq_private",
            "question": "When can you deliver?",
        }
    )
    telegram = AsyncMock()

    with (
        patch("src.api.telegram_webhook.redis_client", redis),
        patch("src.api.telegram_webhook._get_telegram_client", return_value=telegram),
        patch(
            "src.api.telegram_webhook._get_conversation_phone_and_lang",
            new=AsyncMock(return_value=(None, "en")),
        ),
        patch(
            "src.llm.response_adapter.adapt_manager_response",
            new=AsyncMock(return_value="Delivery takes 3-5 business days."),
        ) as mock_adapter,
        patch(
            "src.llm.response_adapter.adapt_manager_response_with_faq_candidate",
            new=AsyncMock(side_effect=AssertionError("unexpected combined call")),
        ) as mock_combined,
        patch(
            "src.services.auto_faq.review_auto_faq_candidate",
            new=AsyncMock(side_effect=AssertionError("unexpected FAQ review")),
        ) as mock_review,
    ):
        await _handle_manager_reply({"chat": {"id": 42}, "text": "3-5 days"})

    mock_adapter.assert_awaited_once_with(
        "When can you deliver?",
        "3-5 days",
        "en",
    )
    mock_combined.assert_not_awaited()
    mock_review.assert_not_awaited()
    redis.delete.assert_awaited_once()


@pytest.mark.asyncio
async def test_private_manager_reply_persists_message_after_successful_wazzup_send() -> (
    None
):
    from src.api.telegram_webhook import _handle_manager_reply
    from src.models.message import Message

    conv_uuid = uuid.uuid4()
    redis = AsyncMock()
    redis.get.return_value = json.dumps(
        {
            "conversation_id": str(conv_uuid),
            "mode": "faq_private",
            "question": "When can you deliver?",
        }
    )
    telegram = AsyncMock()
    db = AsyncMock()
    db.add = MagicMock()
    db.execute.return_value.scalar_one_or_none = MagicMock(return_value=None)
    db_cm = AsyncMock()
    db_cm.__aenter__.return_value = db
    db_cm.__aexit__.return_value = False
    wazzup = AsyncMock()
    wazzup.send_text = AsyncMock(return_value="wazzup-message-123")
    wazzup.close = AsyncMock()

    with (
        patch("src.api.telegram_webhook.redis_client", redis),
        patch("src.api.telegram_webhook._get_telegram_client", return_value=telegram),
        patch(
            "src.api.telegram_webhook._get_conversation_phone_and_lang",
            new=AsyncMock(return_value=("+971501234567", "en")),
        ),
        patch(
            "src.api.telegram_webhook.async_session_factory",
            MagicMock(return_value=db_cm),
        ),
        patch(
            "src.api.telegram_webhook.resolve_conversation_pending_escalations",
            new=AsyncMock(return_value=1),
        ) as mock_resolve,
        patch("src.integrations.messaging.wazzup.WazzupProvider", return_value=wazzup),
        patch(
            "src.llm.response_adapter.adapt_manager_response",
            new=AsyncMock(return_value="Delivery takes 3-5 business days."),
        ),
    ):
        await _handle_manager_reply({"chat": {"id": 42}, "text": "3-5 days"})

    wazzup.send_text.assert_awaited_once()
    assert wazzup.send_text.await_args.args == (
        "+971501234567",
        "Delivery takes 3-5 business days.",
    )
    assert wazzup.send_text.await_args.kwargs["crm_message_id"] == (
        f"manager:{conv_uuid}:42:private"
    )
    added_messages = [
        call.args[0]
        for call in db.add.call_args_list
        if isinstance(call.args[0], Message)
    ]
    assert len(added_messages) == 1
    msg = added_messages[0]
    assert isinstance(msg, Message)
    assert msg.conversation_id == conv_uuid
    assert msg.role == "assistant"
    assert msg.content == "Delivery takes 3-5 business days."
    assert msg.model == "manager_reply"
    assert msg.wazzup_message_id == "wazzup-message-123"
    mock_resolve.assert_awaited_once_with(db, conv_uuid)
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_private_manager_reply_send_failure_does_not_persist_or_resolve() -> None:
    from src.api.telegram_webhook import _handle_manager_reply
    from src.models.message import Message

    conv_uuid = uuid.uuid4()
    redis = AsyncMock()
    redis.get.return_value = json.dumps(
        {
            "conversation_id": str(conv_uuid),
            "mode": "faq_private",
            "question": "When can you deliver?",
        }
    )
    telegram = AsyncMock()
    session_factory = MagicMock()
    db = AsyncMock()
    db.add = MagicMock()
    db.execute.return_value.scalar_one_or_none = MagicMock(return_value=None)
    db_cm = AsyncMock()
    db_cm.__aenter__.return_value = db
    db_cm.__aexit__.return_value = False
    session_factory.return_value = db_cm
    wazzup = AsyncMock()
    wazzup.send_text = AsyncMock(side_effect=RuntimeError("Wazzup unavailable"))
    wazzup.close = AsyncMock()

    with (
        patch("src.api.telegram_webhook.redis_client", redis),
        patch("src.api.telegram_webhook._get_telegram_client", return_value=telegram),
        patch(
            "src.api.telegram_webhook._get_conversation_phone_and_lang",
            new=AsyncMock(return_value=("+971501234567", "en")),
        ),
        patch("src.api.telegram_webhook.async_session_factory", session_factory),
        patch(
            "src.api.telegram_webhook.resolve_conversation_pending_escalations",
            new=AsyncMock(return_value=1),
        ) as mock_resolve,
        patch("src.integrations.messaging.wazzup.WazzupProvider", return_value=wazzup),
        patch(
            "src.llm.response_adapter.adapt_manager_response",
            new=AsyncMock(return_value="Delivery takes 3-5 business days."),
        ),
    ):
        await _handle_manager_reply({"chat": {"id": 42}, "text": "3-5 days"})

    wazzup.send_text.assert_awaited_once()
    wazzup.close.assert_awaited_once()
    added_messages = [
        call.args[0]
        for call in db.add.call_args_list
        if isinstance(call.args[0], Message)
    ]
    assert added_messages == []
    mock_resolve.assert_not_awaited()


@pytest.mark.asyncio
async def test_faq_manager_reply_uses_combined_call_and_requires_confirmation() -> None:
    from src.api.telegram_webhook import _handle_manager_reply
    from src.llm.response_adapter import ManagerReplyWithAutoFAQResult

    conv_id = str(uuid.uuid4())
    redis = AsyncMock()
    redis.get.return_value = json.dumps(
        {
            "conversation_id": conv_id,
            "mode": "faq_global",
            "question": "When can you deliver?",
        }
    )
    telegram = AsyncMock()
    db_cm = AsyncMock()
    db_cm.__aenter__.return_value = AsyncMock()
    db_cm.__aexit__.return_value = False
    candidate = AutoFAQCandidate(
        question="What is the delivery time in the UAE?",
        answer="Delivery takes 3-5 business days in the UAE.",
        confidence=0.93,
    )
    combined_output = ManagerReplyWithAutoFAQResult(
        customer_message="Delivery takes 3-5 business days in the UAE.",
        kb_candidate=candidate,
    )

    with (
        patch("src.api.telegram_webhook.redis_client", redis),
        patch("src.api.telegram_webhook._get_telegram_client", return_value=telegram),
        patch(
            "src.api.telegram_webhook._get_conversation_phone_and_lang",
            new=AsyncMock(return_value=(None, "en")),
        ),
        patch(
            "src.api.telegram_webhook.async_session_factory",
            MagicMock(return_value=db_cm),
        ),
        patch("src.rag.embeddings.EmbeddingEngine", MagicMock()),
        patch(
            "src.llm.response_adapter.adapt_manager_response",
            new=AsyncMock(side_effect=AssertionError("unexpected normal adapter call")),
        ) as mock_adapter,
        patch(
            "src.llm.response_adapter.adapt_manager_response_with_faq_candidate",
            new=AsyncMock(return_value=combined_output),
        ) as mock_combined,
        patch(
            "src.services.auto_faq.review_auto_faq_candidate",
            new=AsyncMock(
                return_value=AutoFAQSaveResult(
                    status="needs_confirmation",
                    candidate=candidate,
                )
            ),
        ) as mock_review,
    ):
        await _handle_manager_reply({"chat": {"id": 42}, "text": "3-5 days"})

    mock_adapter.assert_not_awaited()
    mock_combined.assert_awaited_once_with(
        "When can you deliver?",
        "3-5 days",
        "en",
    )
    mock_review.assert_awaited_once()
    assert mock_review.await_args.kwargs["candidate"] == candidate
    assert mock_review.await_args.kwargs["customer_message"] == (
        "Delivery takes 3-5 business days in the UAE."
    )
    sent_texts = [call.args[0] for call in telegram.send_message.await_args_list]
    assert any("Требуется подтверждение админа" in text for text in sent_texts)
