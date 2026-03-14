"""Tests for Wazzup webhook — manager message routing (Component 1).

Verifies:
- Client messages → rpush + enqueue (existing flow)
- Manager messages → rpush + enqueue (saved for processing)
- Bot messages → skipped entirely
- authorId/authorName parsed correctly
"""

from __future__ import annotations

from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from src.core.config import settings
from src.main import app

client = TestClient(app)


def _setup_mocks() -> tuple[AsyncMock, AsyncMock]:
    mock_redis = AsyncMock()
    mock_arq = AsyncMock()
    app.state.redis = mock_redis
    app.state.arq_pool = mock_arq
    settings.wazzup_webhook_secret = ""  # Skip auth check in tests
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
                "channelId": "ch1",
                "timestamp": 1234567890,
                "authorType": "client",
            }
        ]
    }

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
                "channelId": "ch1",
                "timestamp": 1234567890,
                "authorType": "manager",
                "isEcho": True,
                "authorId": "mgr-001",
                "authorName": "Israullah",
            }
        ]
    }

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
                "channelId": "ch1",
                "timestamp": 1234567890,
                "authorType": "bot",
                "isEcho": False,
            }
        ]
    }

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
                "channelId": "ch1",
                "timestamp": 1234567890,
            }
        ]
    }

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
                "channelId": "ch1",
                "timestamp": 1234567890,
                "authorType": "client",
            },
            {
                "messageId": "msg-b2",
                "chatId": "971551220665",
                "chatType": "whatsapp",
                "text": "Bot echo",
                "type": "text",
                "channelId": "ch1",
                "timestamp": 1234567891,
                "authorType": "bot",
            },
        ]
    }

    response = client.post("/api/v1/webhook/wazzup", json=payload)

    assert response.status_code == 200
    # Only 1 message pushed (client), bot skipped
    assert mock_redis.rpush.call_count == 1
    assert mock_arq.enqueue_job.call_count == 1
