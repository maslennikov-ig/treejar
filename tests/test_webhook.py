from typing import Any
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)
EXPECTED_CHANNEL_ID = "b49b1b9d-757f-4104-b56d-8f43d62cc515"


@patch("src.api.v1.webhook._parse_allowed_networks", return_value=[])
def test_wazzup_webhook_endpoint(mock_networks: Any) -> None:
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
                "channelId": EXPECTED_CHANNEL_ID,
                "timestamp": 1234567890,
            }
        ]
    }

    with patch("src.api.v1.webhook.settings.wazzup_channel_id", EXPECTED_CHANNEL_ID):
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


@patch("src.api.v1.webhook._parse_allowed_networks", return_value=[])
def test_wazzup_webhook_test_ping(mock_networks: Any) -> None:
    """Test that Wazzup test ping returns 200 OK."""
    response = client.post("/api/v1/webhook/wazzup", json={"test": True})
    assert response.status_code == 200
    assert response.json() == {"ok": True}


@patch("src.api.v1.webhook._parse_allowed_networks", return_value=[])
def test_wazzup_webhook_empty_payload(mock_networks: Any) -> None:
    """Test that empty payload (no messages) returns 200 OK."""
    response = client.post("/api/v1/webhook/wazzup", json={})
    assert response.status_code == 200
    assert response.json() == {"ok": True}


@patch("src.api.v1.webhook._parse_allowed_networks", return_value=[])
def test_wazzup_webhook_status_only(mock_networks: Any) -> None:
    """Test that status-only payload returns 200 OK."""
    response = client.post(
        "/api/v1/webhook/wazzup",
        json={"statuses": [{"messageId": "123", "status": "delivered"}]},
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True}


@patch("src.api.v1.webhook._parse_allowed_networks", return_value=[])
def test_wazzup_webhook_status_only_updates_outbound_audit(mock_networks: Any) -> None:
    status_updater = AsyncMock(return_value=1)
    db = AsyncMock()
    db_cm = AsyncMock()
    db_cm.__aenter__.return_value = db
    db_cm.__aexit__.return_value = False

    with (
        patch("src.api.v1.webhook.async_session_factory", return_value=db_cm),
        patch("src.api.v1.webhook.update_wazzup_statuses", status_updater),
    ):
        response = client.post(
            "/api/v1/webhook/wazzup",
            json={
                "statuses": [
                    {
                        "messageId": "provider-msg-1",
                        "timestamp": "2026-04-26T12:00:00.000Z",
                        "status": "delivered",
                    }
                ]
            },
        )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    status_updater.assert_awaited_once_with(
        db,
        [
            {
                "messageId": "provider-msg-1",
                "timestamp": "2026-04-26T12:00:00.000Z",
                "status": "delivered",
            }
        ],
    )
    db.commit.assert_awaited_once()


def test_wazzup_webhook_rejects_disallowed_ip() -> None:
    """Test that webhook rejects requests from non-allowed IPs."""
    import ipaddress

    networks = [ipaddress.ip_network("10.0.0.0/8")]
    with patch("src.api.v1.webhook._parse_allowed_networks", return_value=networks):
        response = client.post(
            "/api/v1/webhook/wazzup",
            json={"messages": []},
        )
    assert response.status_code == 403
    assert response.json() == {"error": "forbidden"}


@patch("src.api.v1.webhook._parse_allowed_networks", return_value=[])
def test_wazzup_webhook_accepts_all_when_no_allowlist(mock_networks: Any) -> None:
    """Test that webhook accepts all requests when no allowlist is configured."""
    response = client.post(
        "/api/v1/webhook/wazzup",
        json={"test": True},
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True}
