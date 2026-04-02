from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from src.main import app

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
