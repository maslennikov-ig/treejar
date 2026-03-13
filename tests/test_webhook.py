from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


@patch("src.api.v1.webhook.settings")
def test_wazzup_webhook_endpoint(mock_settings: object) -> None:
    mock_settings.wazzup_webhook_secret = ""  # Skip auth check in this test

    # Mock redis and arq_pool
    app.state.redis = AsyncMock()
    app.state.arq_pool = AsyncMock()

    payload = {
        "messages": [
            {
                "messageId": "123",
                "chatId": "79991234567",
                "chatType": "whatsapp",
                "text": "Hello bot!",
                "type": "text",
                "channelId": "ch1",
                "timestamp": 1234567890,
            }
        ]
    }

    response = client.post("/api/v1/webhook/wazzup", json=payload)

    assert response.status_code == 200
    assert response.json() == {"ok": True}

    app.state.redis.rpush.assert_called_once()
    # job_id now includes a time window suffix
    call_args = app.state.arq_pool.enqueue_job.call_args
    assert call_args.args[0] == "process_incoming_batch"
    assert call_args.kwargs["chat_id"] == "79991234567"
    assert call_args.kwargs["_job_id"].startswith("wazzup_batch_79991234567_")
    assert call_args.kwargs["_defer_by"] == 5


@patch("src.api.v1.webhook.settings")
def test_wazzup_webhook_test_ping(mock_settings: object) -> None:
    """Test that Wazzup test ping returns 200 OK."""
    mock_settings.wazzup_webhook_secret = ""
    response = client.post("/api/v1/webhook/wazzup", json={"test": True})
    assert response.status_code == 200
    assert response.json() == {"ok": True}


@patch("src.api.v1.webhook.settings")
def test_wazzup_webhook_empty_payload(mock_settings: object) -> None:
    """Test that empty payload (no messages) returns 200 OK."""
    mock_settings.wazzup_webhook_secret = ""
    response = client.post("/api/v1/webhook/wazzup", json={})
    assert response.status_code == 200
    assert response.json() == {"ok": True}


@patch("src.api.v1.webhook.settings")
def test_wazzup_webhook_status_only(mock_settings: object) -> None:
    """Test that status-only payload returns 200 OK."""
    mock_settings.wazzup_webhook_secret = ""
    response = client.post(
        "/api/v1/webhook/wazzup",
        json={"statuses": [{"messageId": "123", "status": "delivered"}]},
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True}


@patch("src.api.v1.webhook.settings")
def test_wazzup_webhook_rejects_unauthorized(mock_settings: object) -> None:
    """Test that webhook rejects unauthorized requests when secret is set."""
    mock_settings.wazzup_webhook_secret = "my-secret"

    response = client.post(
        "/api/v1/webhook/wazzup",
        json={"messages": []},
        headers={"Authorization": "Bearer wrong-secret"},
    )
    assert response.status_code == 403
    assert response.json() == {"error": "unauthorized"}


@patch("src.api.v1.webhook.settings")
def test_wazzup_webhook_accepts_valid_auth(mock_settings: object) -> None:
    """Test that webhook accepts requests with valid Bearer token."""
    mock_settings.wazzup_webhook_secret = "my-secret"

    app.state.redis = AsyncMock()
    app.state.arq_pool = AsyncMock()

    response = client.post(
        "/api/v1/webhook/wazzup",
        json={"test": True},
        headers={"Authorization": "Bearer my-secret"},
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True}
