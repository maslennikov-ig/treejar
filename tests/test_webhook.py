import datetime
import logging
import uuid
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.models.conversation import Conversation
from src.services.inbound_batch import inbound_chat_reference, inbound_queue_key
from src.services.proposal_followup import record_proposal_sent

client = TestClient(app)
EXPECTED_CHANNEL_ID = "b49b1b9d-757f-4104-b56d-8f43d62cc515"


def _dt(value: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))


@pytest.mark.parametrize(
    ("headers", "expected_signal"),
    [
        ({}, "missing"),
        ({"Authorization": "Bearer wrong-secret"}, "mismatch"),
        ({"Authorization": "Bearer expected-secret"}, "match"),
    ],
)
@patch("src.api.v1.webhook._parse_allowed_networks", return_value=[])
def test_wazzup_webhook_observe_auth_logs_result_without_blocking_or_exposing_secrets(
    mock_networks: Any,
    headers: dict[str, str],
    expected_signal: str,
    caplog: Any,
) -> None:
    auth_settings = SimpleNamespace(
        wazzup_webhook_auth_mode="observe",
        wazzup_webhook_secret="expected-secret",
    )

    with (
        patch("src.api.v1.webhook.settings", auth_settings),
        caplog.at_level(logging.INFO, logger="uvicorn.error"),
    ):
        response = client.post(
            "/api/v1/webhook/wazzup",
            json={"test": True},
            headers=headers,
        )

    auth_logs = [
        record.getMessage()
        for record in caplog.records
        if record.getMessage().startswith("Wazzup webhook auth: ")
    ]
    assert response.status_code == 200
    assert auth_logs == [f"Wazzup webhook auth: {expected_signal}"]
    assert "expected-secret" not in caplog.text
    assert "wrong-secret" not in caplog.text


@pytest.mark.parametrize(
    "authorization",
    [None, "Basic credentials", "Bearer", "Bearer wrong-secret"],
    ids=["missing", "wrong-scheme", "missing-token", "wrong-token"],
)
@patch("src.api.v1.webhook._parse_allowed_networks", return_value=[])
def test_wazzup_webhook_enforce_auth_rejects_before_persistence_or_queue_work(
    mock_networks: Any,
    authorization: str | None,
) -> None:
    app.state.redis = AsyncMock()
    app.state.arq_pool = AsyncMock()
    auth_settings = SimpleNamespace(
        wazzup_webhook_auth_mode="enforce",
        wazzup_webhook_secret="expected-secret",
    )
    headers = {"Authorization": authorization} if authorization else {}

    with (
        patch("src.api.v1.webhook.settings", auth_settings),
        patch("src.api.v1.webhook.async_session_factory") as session_factory,
    ):
        response = client.post(
            "/api/v1/webhook/wazzup",
            json={
                "statuses": [
                    {
                        "messageId": "provider-msg-1",
                        "status": "delivered",
                    }
                ]
            },
            headers=headers,
        )

    assert response.status_code == 401
    assert response.json() == {"error": "unauthorized"}
    assert response.headers["www-authenticate"] == "Bearer"
    session_factory.assert_not_called()
    app.state.redis.rpush.assert_not_called()
    app.state.arq_pool.enqueue_job.assert_not_called()


@patch("src.api.v1.webhook._parse_allowed_networks", return_value=[])
def test_wazzup_webhook_enforce_auth_accepts_matching_bearer(
    mock_networks: Any,
) -> None:
    auth_settings = SimpleNamespace(
        wazzup_webhook_auth_mode="enforce",
        wazzup_webhook_secret="expected-secret",
    )

    with patch("src.api.v1.webhook.settings", auth_settings):
        response = client.post(
            "/api/v1/webhook/wazzup",
            json={"test": True},
            headers={"Authorization": "Bearer expected-secret"},
        )

    assert response.status_code == 200
    assert response.json() == {"ok": True}


class _ScalarResult:
    def __init__(self, value: object | None) -> None:
        self._value = value

    def scalar_one_or_none(self) -> object | None:
        return self._value


class _Scalars:
    def __init__(self, values: list[object]) -> None:
        self._values = values

    def all(self) -> list[object]:
        return self._values


class _ScalarsResult:
    def __init__(self, values: list[object]) -> None:
        self._values = values

    def scalars(self) -> _Scalars:
        return _Scalars(self._values)


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
    batch_ref = inbound_chat_reference("79991234567")
    assert call_args.kwargs["batch_ref"] == batch_ref
    assert "chat_id" not in call_args.kwargs
    assert call_args.kwargs["_job_id"].startswith(f"wazzup_batch_{batch_ref}_")
    assert call_args.kwargs["_defer_by"] == 5
    assert app.state.redis.rpush.await_args.args[0] == inbound_queue_key(batch_ref)


@patch("src.api.v1.webhook._parse_allowed_networks", return_value=[])
def test_wazzup_webhook_logs_do_not_expose_customer_payload(
    mock_networks: Any,
    caplog: Any,
) -> None:
    app.state.redis = AsyncMock()
    app.state.arq_pool = AsyncMock()
    sensitive_chat_id = "+971500009999"
    sensitive_text = "Need a confidential quotation"
    sensitive_name = "Private Customer"
    payload = {
        "messages": [
            {
                "messageId": "privacy-msg-1",
                "chatId": sensitive_chat_id,
                "chatType": "whatsapp",
                "text": sensitive_text,
                "type": "text",
                "authorType": "manager",
                "authorName": sensitive_name,
                "channelId": EXPECTED_CHANNEL_ID,
                "timestamp": 1234567890,
            }
        ]
    }

    with (
        caplog.at_level(logging.INFO, logger="uvicorn.error"),
        patch("src.api.v1.webhook.settings.wazzup_channel_id", EXPECTED_CHANNEL_ID),
    ):
        response = client.post("/api/v1/webhook/wazzup", json=payload)

    assert response.status_code == 200
    assert sensitive_chat_id not in caplog.text
    assert sensitive_text not in caplog.text
    assert sensitive_name not in caplog.text


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


@patch("src.api.v1.webhook._parse_allowed_networks", return_value=[])
def test_wazzup_webhook_outbound_message_updates_delivery_audit(
    mock_networks: Any,
) -> None:
    app.state.redis = AsyncMock()
    app.state.arq_pool = AsyncMock()
    status_updater = AsyncMock(return_value=1)
    proposal_updater = AsyncMock(return_value=0)
    db = AsyncMock()
    db_cm = AsyncMock()
    db_cm.__aenter__.return_value = db
    db_cm.__aexit__.return_value = False

    with (
        patch("src.api.v1.webhook.async_session_factory", return_value=db_cm),
        patch("src.api.v1.webhook.update_wazzup_statuses", status_updater),
        patch(
            "src.api.v1.webhook.apply_proposal_read_statuses",
            proposal_updater,
        ),
    ):
        response = client.post(
            "/api/v1/webhook/wazzup",
            json={
                "messages": [
                    {
                        "messageId": "provider-msg-1",
                        "channelId": EXPECTED_CHANNEL_ID,
                        "chatId": "79991234567",
                        "chatType": "whatsapp",
                        "type": "text",
                        "text": "Delivered reply",
                        "dateTime": "2026-07-30T09:30:00.000Z",
                        "status": "delivered",
                        "isEcho": True,
                    }
                ]
            },
        )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    expected = [
        {
            "messageId": "provider-msg-1",
            "timestamp": "2026-07-30T09:30:00.000Z",
            "status": "delivered",
        }
    ]
    status_updater.assert_awaited_once_with(db, expected)
    proposal_updater.assert_awaited_once_with(db, expected)
    db.commit.assert_awaited_once()


@patch("src.api.v1.webhook._parse_allowed_networks", return_value=[])
def test_wazzup_webhook_ignores_malformed_message_status(
    mock_networks: Any,
) -> None:
    status_updater = AsyncMock(return_value=0)
    with patch("src.api.v1.webhook.update_wazzup_statuses", status_updater):
        response = client.post(
            "/api/v1/webhook/wazzup",
            json={
                "messages": [
                    {
                        "messageId": "provider-msg-1",
                        "status": {"unexpected": True},
                    }
                ]
            },
        )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    status_updater.assert_not_awaited()


@patch("src.api.v1.webhook._parse_allowed_networks", return_value=[])
def test_wazzup_webhook_mixed_envelope_preserves_inbound_message(
    mock_networks: Any,
) -> None:
    app.state.redis = AsyncMock()
    app.state.arq_pool = AsyncMock()
    status_updater = AsyncMock(return_value=1)
    proposal_updater = AsyncMock(return_value=1)
    db = AsyncMock()
    db_cm = AsyncMock()
    db_cm.__aenter__.return_value = db
    db_cm.__aexit__.return_value = False

    with (
        patch("src.api.v1.webhook.async_session_factory", return_value=db_cm),
        patch("src.api.v1.webhook.update_wazzup_statuses", status_updater),
        patch(
            "src.api.v1.webhook.apply_proposal_read_statuses",
            proposal_updater,
        ),
        patch("src.api.v1.webhook.settings.wazzup_channel_id", EXPECTED_CHANNEL_ID),
    ):
        response = client.post(
            "/api/v1/webhook/wazzup",
            json={
                "messages": [
                    {
                        "messageId": "inbound-msg-1",
                        "channelId": EXPECTED_CHANNEL_ID,
                        "chatId": "79991234567",
                        "chatType": "whatsapp",
                        "type": "text",
                        "text": "Need four chairs",
                        "dateTime": "2026-07-30T09:31:00.000Z",
                        "status": "inbound",
                    },
                    {
                        "messageId": "outbound-msg-1",
                        "dateTime": "2026-07-30T09:30:00.000Z",
                        "status": "read",
                    },
                ]
            },
        )

    assert response.status_code == 200
    status_updater.assert_awaited_once()
    proposal_updater.assert_awaited_once()
    app.state.redis.rpush.assert_awaited_once()
    app.state.arq_pool.enqueue_job.assert_awaited_once()


@patch("src.api.v1.webhook._parse_allowed_networks", return_value=[])
def test_wazzup_webhook_deduplicates_identical_status_envelopes(
    mock_networks: Any,
) -> None:
    status_updater = AsyncMock(return_value=1)
    proposal_updater = AsyncMock(return_value=0)
    db = AsyncMock()
    db_cm = AsyncMock()
    db_cm.__aenter__.return_value = db
    db_cm.__aexit__.return_value = False
    status = {
        "messageId": "provider-msg-1",
        "timestamp": "2026-07-30T09:30:00.000Z",
        "status": "delivered",
    }

    with (
        patch("src.api.v1.webhook.async_session_factory", return_value=db_cm),
        patch("src.api.v1.webhook.update_wazzup_statuses", status_updater),
        patch(
            "src.api.v1.webhook.apply_proposal_read_statuses",
            proposal_updater,
        ),
    ):
        response = client.post(
            "/api/v1/webhook/wazzup",
            json={
                "statuses": [status],
                "messages": [
                    {
                        "messageId": status["messageId"],
                        "dateTime": status["timestamp"],
                        "status": status["status"],
                    }
                ],
            },
        )

    assert response.status_code == 200
    status_updater.assert_awaited_once_with(db, [status])
    proposal_updater.assert_awaited_once_with(db, [status])


@patch("src.api.v1.webhook._parse_allowed_networks", return_value=[])
def test_wazzup_webhook_invalid_read_timestamp_does_not_mark_proposal_read(
    mock_networks: Any,
) -> None:
    conv = Conversation(
        id=uuid.uuid4(),
        phone="+971501234567",
        status="active",
        deal_status="pending",
        metadata_={},
    )
    record_proposal_sent(
        conv,
        sent_at=_dt("2026-07-30T08:00:00Z"),
        kp_message_id="kp-provider-1",
    )
    db = AsyncMock()
    db.execute.side_effect = [
        _ScalarResult(None),
        _ScalarsResult([conv]),
    ]
    db_cm = AsyncMock()
    db_cm.__aenter__.return_value = db
    db_cm.__aexit__.return_value = False

    with (
        patch("src.api.v1.webhook.async_session_factory", return_value=db_cm),
        patch(
            "src.api.v1.webhook.update_wazzup_statuses",
            AsyncMock(return_value=0),
        ),
    ):
        response = client.post(
            "/api/v1/webhook/wazzup",
            json={
                "messages": [
                    {
                        "messageId": "kp-provider-1",
                        "dateTime": "not-a-datetime",
                        "status": "read",
                    }
                ]
            },
        )

    assert response.status_code == 200
    state = conv.metadata_["proposal_followup"]
    assert state["kp_read"] is False
    assert state["kp_read_at"] is None


@patch("src.api.v1.webhook._parse_allowed_networks", return_value=[])
def test_wazzup_webhook_normalizes_numeric_message_timestamp(
    mock_networks: Any,
) -> None:
    status_updater = AsyncMock(return_value=1)
    proposal_updater = AsyncMock(return_value=1)
    db = AsyncMock()
    db_cm = AsyncMock()
    db_cm.__aenter__.return_value = db
    db_cm.__aexit__.return_value = False

    with (
        patch("src.api.v1.webhook.async_session_factory", return_value=db_cm),
        patch("src.api.v1.webhook.update_wazzup_statuses", status_updater),
        patch(
            "src.api.v1.webhook.apply_proposal_read_statuses",
            proposal_updater,
        ),
    ):
        response = client.post(
            "/api/v1/webhook/wazzup",
            json={
                "messages": [
                    {
                        "messageId": "provider-msg-1",
                        "timestamp": 946684800,
                        "status": "read",
                    }
                ]
            },
        )

    expected = [
        {
            "messageId": "provider-msg-1",
            "timestamp": "2000-01-01T00:00:00+00:00",
            "status": "read",
        }
    ]
    assert response.status_code == 200
    status_updater.assert_awaited_once_with(db, expected)
    proposal_updater.assert_awaited_once_with(db, expected)


@patch("src.api.v1.webhook._parse_allowed_networks", return_value=[])
def test_wazzup_webhook_read_status_records_proposal_read_without_reschedule(
    mock_networks: Any,
) -> None:
    conv = Conversation(
        id=uuid.uuid4(),
        phone="+971501234567",
        status="active",
        deal_status="pending",
        metadata_={},
    )
    record_proposal_sent(
        conv,
        sent_at=_dt("2026-05-04T08:00:00Z"),
        kp_message_id="kp-provider-1",
    )

    db = AsyncMock()
    db.execute.side_effect = [
        _ScalarResult(None),
        _ScalarsResult([conv]),
    ]
    db_cm = AsyncMock()
    db_cm.__aenter__.return_value = db
    db_cm.__aexit__.return_value = False

    with (
        patch("src.api.v1.webhook.async_session_factory", return_value=db_cm),
        patch("src.api.v1.webhook.update_wazzup_statuses", AsyncMock(return_value=1)),
    ):
        response = client.post(
            "/api/v1/webhook/wazzup",
            json={
                "statuses": [
                    {
                        "messageId": "kp-provider-1",
                        "timestamp": "2026-05-04T09:00:00.000Z",
                        "status": "read",
                    }
                ]
            },
        )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    state = conv.metadata_["proposal_followup"]
    assert state["kp_read"] is True
    assert state["kp_read_at"] == "2026-05-04T09:00:00+00:00"
    assert state["steps"]["1"]["scheduled_at"] == "2026-05-05T07:00:00+00:00"
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


@patch("src.api.v1.webhook._parse_allowed_networks", return_value=[])
def test_a_refused_channel_is_logged_with_both_ids(
    mock_networks: Any, caplog: Any
) -> None:
    """tj-ppid: a refusal has to say which channel it refused.

    The warning reported only `channel_present=true`. Five inbound messages
    were refused between 2026-08-06 and 2026-08-07 and the logs could not say
    whether the account had grown a second channel or the configured one had
    gone stale; it took a read-only call to the Wazzup account to find out.
    Both values are channel identifiers, not customer data.
    """
    app.state.redis = AsyncMock()
    app.state.arq_pool = AsyncMock()
    other_channel = "13c71a7f-cf9d-4df2-8b27-11ea67e6b0d9"

    payload = {
        "messages": [
            {
                "messageId": "ch-1",
                "chatId": "79991234567",
                "chatType": "whatsapp",
                "text": "Hello bot!",
                "type": "text",
                "channelId": other_channel,
                "timestamp": 1234567890,
            }
        ]
    }

    with (
        patch("src.api.v1.webhook.settings.wazzup_channel_id", EXPECTED_CHANNEL_ID),
        caplog.at_level(logging.WARNING),
    ):
        response = client.post("/api/v1/webhook/wazzup", json=payload)

    assert response.status_code == 200
    assert other_channel in caplog.text
    assert EXPECTED_CHANNEL_ID in caplog.text
    app.state.redis.rpush.assert_not_called()
