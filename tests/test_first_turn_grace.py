"""AC08: configurable first-turn manager grace window and manager takeover."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.schemas.webhook import WazzupIncomingMessage
from src.services import inbound_batch
from src.services.chat import process_incoming_batch
from src.services.inbound_batch import (
    FIRST_TURN_GRACE_WEEKDAYS_ONLY_KEY,
    FIRST_TURN_MANAGER_GRACE_SECONDS_KEY,
    inbound_chat_reference,
    inbound_grace_key,
    inbound_queue_key,
    resolve_inbound_batch_defer_seconds,
)

client = TestClient(app)
EXPECTED_CHANNEL_ID = "b49b1b9d-757f-4104-b56d-8f43d62cc515"
CHAT_ID = "971500001111"
# 2026-10-22 is a Thursday; 2026-10-24 is a Saturday (both 14:00 in Dubai).
WEEKDAY_UTC = datetime(2026, 10, 22, 10, 0, tzinfo=UTC)
SATURDAY_UTC = datetime(2026, 10, 24, 10, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# resolve_inbound_batch_defer_seconds
# ---------------------------------------------------------------------------


class _Result:
    def __init__(self, value: object | None) -> None:
        self._value = value

    def scalar_one_or_none(self) -> object | None:
        return self._value

    def scalars(self) -> _Result:
        return self

    def first(self) -> object | None:
        return self._value


def _db(config: dict[str, object], *, has_messages: bool = False) -> AsyncMock:
    """Fake session answering SystemConfig lookups and the prior-message probe."""

    async def execute(stmt: Any) -> _Result:
        if "system_configs" in str(stmt):
            key = next(iter(stmt.compile().params.values()))
            if key not in config:
                return _Result(None)
            config_row = MagicMock()
            config_row.value = config[key]
            return _Result(config_row)
        return _Result("message-id" if has_messages else None)

    db = AsyncMock()
    db.execute.side_effect = execute
    return db


@pytest.mark.asyncio
async def test_default_grace_absent_uses_standard_defer() -> None:
    db = _db({})
    assert (
        await resolve_inbound_batch_defer_seconds(
            db, phone=CHAT_ID, now_utc=WEEKDAY_UTC
        )
        == 5
    )


@pytest.mark.asyncio
async def test_grace_zero_uses_standard_defer() -> None:
    db = _db({FIRST_TURN_MANAGER_GRACE_SECONDS_KEY: 0})
    assert (
        await resolve_inbound_batch_defer_seconds(
            db, phone=CHAT_ID, now_utc=WEEKDAY_UTC
        )
        == 5
    )


@pytest.mark.asyncio
async def test_weekday_first_turn_uses_grace() -> None:
    db = _db({FIRST_TURN_MANAGER_GRACE_SECONDS_KEY: 900})
    assert (
        await resolve_inbound_batch_defer_seconds(
            db, phone=CHAT_ID, now_utc=WEEKDAY_UTC
        )
        == 900
    )


@pytest.mark.asyncio
async def test_turn_two_never_waits() -> None:
    db = _db({FIRST_TURN_MANAGER_GRACE_SECONDS_KEY: 900}, has_messages=True)
    assert (
        await resolve_inbound_batch_defer_seconds(
            db, phone=CHAT_ID, now_utc=WEEKDAY_UTC
        )
        == 5
    )


@pytest.mark.asyncio
async def test_weekend_with_weekdays_only_answers_instantly() -> None:
    db = _db(
        {
            FIRST_TURN_MANAGER_GRACE_SECONDS_KEY: 900,
            FIRST_TURN_GRACE_WEEKDAYS_ONLY_KEY: "true",
        }
    )
    assert (
        await resolve_inbound_batch_defer_seconds(
            db, phone=CHAT_ID, now_utc=SATURDAY_UTC
        )
        == 5
    )


@pytest.mark.asyncio
async def test_weekend_with_weekdays_only_false_uses_grace() -> None:
    db = _db(
        {
            FIRST_TURN_MANAGER_GRACE_SECONDS_KEY: 900,
            FIRST_TURN_GRACE_WEEKDAYS_ONLY_KEY: False,
        }
    )
    assert (
        await resolve_inbound_batch_defer_seconds(
            db, phone=CHAT_ID, now_utc=SATURDAY_UTC
        )
        == 900
    )


@pytest.mark.asyncio
async def test_grace_is_clamped_to_maximum() -> None:
    db = _db({FIRST_TURN_MANAGER_GRACE_SECONDS_KEY: "5000"})
    assert (
        await resolve_inbound_batch_defer_seconds(
            db, phone=CHAT_ID, now_utc=WEEKDAY_UTC
        )
        == 1800
    )


@pytest.mark.asyncio
async def test_small_grace_never_shortens_standard_defer() -> None:
    db = _db({FIRST_TURN_MANAGER_GRACE_SECONDS_KEY: 2})
    assert (
        await resolve_inbound_batch_defer_seconds(
            db, phone=CHAT_ID, now_utc=WEEKDAY_UTC
        )
        == 5
    )


@pytest.mark.asyncio
async def test_invalid_grace_uses_standard_defer() -> None:
    db = _db({FIRST_TURN_MANAGER_GRACE_SECONDS_KEY: "soon"})
    assert (
        await resolve_inbound_batch_defer_seconds(
            db, phone=CHAT_ID, now_utc=WEEKDAY_UTC
        )
        == 5
    )


@pytest.mark.asyncio
async def test_db_error_falls_back_to_standard_defer() -> None:
    db = _db({FIRST_TURN_MANAGER_GRACE_SECONDS_KEY: 900})
    with patch.object(
        inbound_batch,
        "_phone_has_prior_messages",
        AsyncMock(side_effect=RuntimeError("db down")),
    ):
        assert (
            await resolve_inbound_batch_defer_seconds(
                db, phone=CHAT_ID, now_utc=WEEKDAY_UTC
            )
            == 5
        )


# ---------------------------------------------------------------------------
# Webhook scheduling
# ---------------------------------------------------------------------------


def _message(author_type: str = "client", message_id: str = "grace-1") -> dict:
    return {
        "messageId": message_id,
        "chatId": CHAT_ID,
        "chatType": "whatsapp",
        "text": "Hello",
        "type": "text",
        "channelId": EXPECTED_CHANNEL_ID,
        "timestamp": 1234567890,
        "authorType": author_type,
    }


def _post(messages: list[dict], *, defer: int, pttl: int) -> AsyncMock:
    app.state.redis = AsyncMock()
    app.state.redis.pttl.return_value = pttl
    app.state.redis.set.return_value = True
    app.state.arq_pool = AsyncMock()
    with (
        patch("src.api.v1.webhook._parse_allowed_networks", return_value=[]),
        patch("src.api.v1.webhook.settings.wazzup_channel_id", EXPECTED_CHANNEL_ID),
        patch(
            "src.api.v1.webhook._resolve_client_defer",
            AsyncMock(return_value=defer),
        ) as resolver,
    ):
        response = client.post("/api/v1/webhook/wazzup", json={"messages": messages})
    assert response.status_code == 200
    return resolver


def test_webhook_default_uses_standard_five_second_job() -> None:
    _post([_message()], defer=5, pttl=-2)

    kwargs = app.state.arq_pool.enqueue_job.await_args.kwargs
    assert kwargs["_defer_by"] == 5
    assert "_grace_" not in kwargs["_job_id"]
    app.state.redis.set.assert_not_awaited()


def test_webhook_first_turn_opens_grace_window() -> None:
    batch_ref = inbound_chat_reference(CHAT_ID)
    _post([_message()], defer=900, pttl=-2)

    app.state.redis.rpush.assert_awaited_once()
    assert app.state.redis.rpush.await_args.args[0] == inbound_queue_key(batch_ref)
    kwargs = app.state.arq_pool.enqueue_job.await_args.kwargs
    assert kwargs["_defer_by"] == 900
    assert kwargs["_job_id"].startswith(f"wazzup_batch_{batch_ref}_grace_")
    set_call = app.state.redis.set.await_args
    assert set_call.args[0] == inbound_grace_key(batch_ref)
    assert set_call.kwargs["ex"] == 900 + 120
    assert set_call.kwargs["nx"] is True


def test_webhook_client_message_inside_grace_window_only_queues() -> None:
    resolver = _post([_message()], defer=900, pttl=600_000)

    app.state.redis.rpush.assert_awaited_once()
    app.state.arq_pool.enqueue_job.assert_not_awaited()
    resolver.assert_not_awaited()


def test_webhook_concurrent_window_claim_only_queues() -> None:
    app.state.redis = AsyncMock()
    app.state.redis.pttl.return_value = -2
    app.state.redis.set.return_value = None
    app.state.arq_pool = AsyncMock()
    with (
        patch("src.api.v1.webhook._parse_allowed_networks", return_value=[]),
        patch("src.api.v1.webhook.settings.wazzup_channel_id", EXPECTED_CHANNEL_ID),
        patch(
            "src.api.v1.webhook._resolve_client_defer",
            AsyncMock(return_value=900),
        ),
    ):
        response = client.post(
            "/api/v1/webhook/wazzup", json={"messages": [_message()]}
        )
    assert response.status_code == 200
    app.state.redis.rpush.assert_awaited_once()
    app.state.arq_pool.enqueue_job.assert_not_awaited()


def test_webhook_after_grace_job_is_due_uses_standard_job() -> None:
    _post([_message()], defer=900, pttl=60_000)

    kwargs = app.state.arq_pool.enqueue_job.await_args.kwargs
    assert kwargs["_defer_by"] == 5
    assert "_grace_" not in kwargs["_job_id"]


def test_webhook_manager_message_keeps_standard_job_during_grace() -> None:
    resolver = _post([_message("manager")], defer=900, pttl=600_000)

    kwargs = app.state.arq_pool.enqueue_job.await_args.kwargs
    assert kwargs["_defer_by"] == 5
    assert "_grace_" not in kwargs["_job_id"]
    resolver.assert_not_awaited()
    app.state.redis.pttl.assert_not_awaited()


def test_webhook_enqueue_failure_releases_grace_marker() -> None:
    app.state.redis = AsyncMock()
    app.state.redis.pttl.return_value = -2
    app.state.redis.set.return_value = True
    app.state.arq_pool = AsyncMock()
    app.state.arq_pool.enqueue_job.side_effect = RuntimeError("redis down")
    failing_client = TestClient(app, raise_server_exceptions=False)
    with (
        patch("src.api.v1.webhook._parse_allowed_networks", return_value=[]),
        patch("src.api.v1.webhook.settings.wazzup_channel_id", EXPECTED_CHANNEL_ID),
        patch(
            "src.api.v1.webhook._resolve_client_defer",
            AsyncMock(return_value=900),
        ),
    ):
        response = failing_client.post(
            "/api/v1/webhook/wazzup", json={"messages": [_message()]}
        )
    assert response.status_code == 500
    app.state.redis.delete.assert_awaited_once_with(
        inbound_grace_key(inbound_chat_reference(CHAT_ID))
    )


# ---------------------------------------------------------------------------
# Manager takeover in process_incoming_batch
# ---------------------------------------------------------------------------


def _seed_inbound_redis(redis: AsyncMock, raw_messages: list[str]) -> None:
    redis.set.return_value = True
    redis.get.return_value = None
    redis.lrange.return_value = []
    redis.lmove.side_effect = [*raw_messages, None]
    redis.eval.return_value = 0


@pytest.mark.asyncio
@pytest.mark.usefixtures("authorized_outbound_unit_path")
@patch("src.services.chat.async_session_factory")
@patch("src.services.chat.process_message")
@patch("src.services.chat.WazzupProvider")
@patch("src.services.chat.ZohoCRMClient")
@patch("src.services.chat.ZohoInventoryClient")
@patch("src.services.chat.EmbeddingEngine")
async def test_manager_reply_in_grace_batch_takes_over_and_skips_llm(
    mock_embedding_cls: MagicMock,
    mock_zoho_inv_cls: MagicMock,
    mock_zoho_crm_cls: MagicMock,
    mock_wazzup_cls: MagicMock,
    mock_process_message: AsyncMock,
    mock_session_factory: MagicMock,
) -> None:
    mock_session = AsyncMock()
    mock_session_factory.return_value.__aenter__.return_value = mock_session
    conv = MagicMock()
    conv.id = "conv-grace-1"
    conv.phone = CHAT_ID
    conv.escalation_status = "none"
    conv.metadata_ = {"inbound_channel_id": "ch1"}
    mock_session.execute.side_effect = [
        _Result(None),  # bot_enabled
        MagicMock(scalars=lambda: MagicMock(all=lambda: [conv])),  # conv lookup
        MagicMock(scalars=lambda: MagicMock(all=lambda: [])),  # dedup lookup
    ]
    mock_wazzup = AsyncMock()
    mock_wazzup_cls.return_value.__aenter__ = AsyncMock(return_value=mock_wazzup)
    mock_wazzup_cls.return_value.__aexit__ = AsyncMock(return_value=False)

    client_msg = WazzupIncomingMessage(
        messageId="grace-client-1",
        chatId=CHAT_ID,
        chatType="whatsapp",
        type="text",
        text="Do you have office chairs?",
        channelId="ch1",
        timestamp=1704067200,
        authorType="client",
    )
    manager_msg = WazzupIncomingMessage(
        messageId="grace-manager-1",
        chatId=CHAT_ID,
        chatType="whatsapp",
        type="text",
        text="Hi, this is Israullah, happy to help.",
        channelId="ch1",
        timestamp=1704067260,
        authorType="manager",
        authorName="Israullah",
    )
    mock_redis = AsyncMock()
    _seed_inbound_redis(
        mock_redis, [client_msg.model_dump_json(), manager_msg.model_dump_json()]
    )

    with patch("src.services.chat.settings.wazzup_channel_id", "ch1"):
        await process_incoming_batch({"redis": mock_redis}, CHAT_ID)

    assert conv.escalation_status == "manual_takeover"
    assert "last_manager_message_at" in conv.metadata_
    datetime.fromisoformat(conv.metadata_["last_manager_message_at"])
    assert conv.metadata_["inbound_channel_id"] == "ch1"
    mock_session.commit.assert_awaited()
    mock_process_message.assert_not_awaited()
    mock_wazzup.send_text.assert_not_awaited()
