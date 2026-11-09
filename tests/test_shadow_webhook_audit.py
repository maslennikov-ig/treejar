from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.core.config import Settings
from src.main import app
from src.models.shadow_webhook_event import ShadowWebhookEvent
from src.services.shadow_webhook_audit import persist_shadow_webhook_payload

STRONG_WEBHOOK_SECRET = "expected-secret-value-with-32-bytes"
WRONG_WEBHOOK_SECRET = "wrong-secret-value-with-at-least-32-bytes"
SHADOW_IP = "46.225.136.202"
RANDOM_IP = "203.0.113.42"


class _FakeScalarResult:
    def __init__(self, rows: list[ShadowWebhookEvent]) -> None:
        self._rows = rows

    def scalars(self) -> _FakeScalarResult:
        return self

    def all(self) -> list[ShadowWebhookEvent]:
        return list(self._rows)

    def scalar_one_or_none(self) -> ShadowWebhookEvent | None:
        return self._rows[0] if self._rows else None


class _FakeNestedTx:
    async def __aenter__(self) -> _FakeNestedTx:
        return self

    async def __aexit__(self, *_: object) -> bool:
        return False


class _InMemoryShadowSession:
    def __init__(self, initial: list[ShadowWebhookEvent] | None = None) -> None:
        self.rows: dict[str, ShadowWebhookEvent] = {
            row.message_id: row for row in (initial or [])
        }
        self._pending: list[ShadowWebhookEvent] = []
        self.commits = 0

    def begin_nested(self) -> _FakeNestedTx:
        return _FakeNestedTx()

    def add(self, obj: ShadowWebhookEvent) -> None:
        self._pending.append(obj)

    async def flush(self) -> None:
        for obj in self._pending:
            self.rows[obj.message_id] = obj
        self._pending.clear()

    async def execute(self, _stmt: Any) -> _FakeScalarResult:
        return _FakeScalarResult(list(self.rows.values()))

    async def commit(self) -> None:
        await self.flush()
        self.commits += 1


def _session_cm(session: _InMemoryShadowSession) -> Any:
    cm = AsyncMock()
    cm.__aenter__.return_value = session
    cm.__aexit__.return_value = False
    return cm


@pytest.mark.asyncio
async def test_persist_shadow_webhook_payload_stores_customer_and_nikita_echo_and_merges_status() -> (
    None
):
    session = _InMemoryShadowSession()

    stored_1 = await persist_shadow_webhook_payload(
        session,  # type: ignore[arg-type]
        {
            "messages": [
                {
                    "messageId": "msg-cust-1",
                    "channelId": "13c71a7f-cf9d-4df2-8b27-11ea67e6b0d9",
                    "chatType": "whatsapp",
                    "chatId": "971501112233",
                    "dateTime": "2026-11-10T08:15:12.000Z",
                    "type": "text",
                    "status": "inbound",
                    "isEcho": False,
                    "authorType": "client",
                    "text": "Hi, I need 6 office chairs in Dubai",
                },
                {
                    "messageId": "msg-nikita-1",
                    "channelId": "13c71a7f-cf9d-4df2-8b27-11ea67e6b0d9",
                    "chatType": "whatsapp",
                    "chatId": "971501112233",
                    "dateTime": "2026-11-10T08:22:00.001Z",
                    "type": "text",
                    "status": "sent",
                    "isEcho": True,
                    "authorName": "Admin",
                    "text": "Hi! I'm Nikita, Treejar's virtual sales assistant.",
                },
            ]
        },
        source_ip=SHADOW_IP,
    )
    assert stored_1 == 2
    assert set(session.rows) == {"msg-cust-1", "msg-nikita-1"}
    assert session.rows["msg-cust-1"].is_echo is False
    assert session.rows["msg-nikita-1"].is_echo is True
    assert session.rows["msg-nikita-1"].author_name == "Admin"
    assert session.rows["msg-nikita-1"].status == "sent"

    # Duplicate delivery with same status does not count as new mutation
    stored_dup = await persist_shadow_webhook_payload(
        session,  # type: ignore[arg-type]
        {
            "messages": [
                {
                    "messageId": "msg-nikita-1",
                    "chatId": "971501112233",
                    "status": "sent",
                    "isEcho": True,
                    "text": "Hi! I'm Nikita, Treejar's virtual sales assistant.",
                }
            ]
        },
        source_ip=SHADOW_IP,
    )
    assert stored_dup == 0

    # Advancing status via statuses array updates status without duplicating row
    stored_read = await persist_shadow_webhook_payload(
        session,  # type: ignore[arg-type]
        {
            "statuses": [
                {
                    "messageId": "msg-nikita-1",
                    "status": "read",
                }
            ]
        },
        source_ip=SHADOW_IP,
    )
    assert stored_read == 1
    assert len(session.rows) == 2
    assert session.rows["msg-nikita-1"].status == "read"


@pytest.mark.asyncio
async def test_unauthenticated_shadow_ip_persists_observe_only_and_never_touches_queue() -> (
    None
):
    session = _InMemoryShadowSession()
    app.state.redis = MagicMock()
    app.state.redis.rpush = AsyncMock()
    app.state.arq_pool = MagicMock()
    app.state.arq_pool.enqueue_job = AsyncMock()

    auth_settings = Settings(
        _env_file=None,
        wazzup_webhook_auth_mode="enforce",
        wazzup_webhook_secret=STRONG_WEBHOOK_SECRET,
        wazzup_shadow_audit_ips=SHADOW_IP,
    )

    transport = ASGITransport(app=app, client=(SHADOW_IP, 54321))
    with (
        patch("src.api.v1.webhook.settings", auth_settings),
        patch(
            "src.api.v1.webhook.async_session_factory",
            return_value=_session_cm(session),
        ),
    ):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/api/v1/webhook/wazzup",
                json={
                    "messages": [
                        {
                            "messageId": "shadow-even-day-1",
                            "channelId": "13c71a7f-cf9d-4df2-8b27-11ea67e6b0d9",
                            "chatId": "971509998877",
                            "type": "image",
                            "status": "inbound",
                            "isEcho": False,
                            "contentUri": "https://store.wazzup24.com/sample.jpg",
                        }
                    ]
                },
            )

    assert resp.status_code == 401
    assert session.commits == 1
    assert "shadow-even-day-1" in session.rows
    assert (
        session.rows["shadow-even-day-1"].content_uri
        == "https://store.wazzup24.com/sample.jpg"
    )
    app.state.redis.rpush.assert_not_called()
    app.state.arq_pool.enqueue_job.assert_not_called()


@pytest.mark.asyncio
async def test_unauthenticated_non_shadow_ip_is_rejected_without_reading_db() -> None:
    auth_settings = Settings(
        _env_file=None,
        wazzup_webhook_auth_mode="enforce",
        wazzup_webhook_secret=STRONG_WEBHOOK_SECRET,
        wazzup_shadow_audit_ips=SHADOW_IP,
    )

    transport = ASGITransport(app=app, client=(RANDOM_IP, 54321))
    with (
        patch("src.api.v1.webhook.settings", auth_settings),
        patch("src.api.v1.webhook.async_session_factory") as session_factory,
    ):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/api/v1/webhook/wazzup",
                json={
                    "messages": [
                        {
                            "messageId": "attacker-msg-1",
                            "chatId": "971500000000",
                            "text": "spoof",
                        }
                    ]
                },
            )

    assert resp.status_code == 401
    session_factory.assert_not_called()


@pytest.mark.asyncio
async def test_wrong_bearer_from_shadow_ip_is_not_captured_as_unauthenticated_mirror() -> (
    None
):
    auth_settings = Settings(
        _env_file=None,
        wazzup_webhook_auth_mode="enforce",
        wazzup_webhook_secret=STRONG_WEBHOOK_SECRET,
        wazzup_shadow_audit_ips=SHADOW_IP,
    )

    transport = ASGITransport(app=app, client=(SHADOW_IP, 54321))
    with (
        patch("src.api.v1.webhook.settings", auth_settings),
        patch("src.api.v1.webhook.async_session_factory") as session_factory,
    ):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/api/v1/webhook/wazzup",
                headers={"Authorization": f"Bearer {WRONG_WEBHOOK_SECRET}"},
                json={"messages": [{"messageId": "m1", "chatId": "971500000000"}]},
            )

    assert resp.status_code == 401
    session_factory.assert_not_called()


@pytest.mark.asyncio
async def test_explicit_observe_endpoint_accepts_bearer_or_shadow_ip_and_rejects_random() -> (
    None
):
    session = _InMemoryShadowSession()
    app.state.redis = MagicMock()
    app.state.redis.rpush = AsyncMock()
    app.state.arq_pool = MagicMock()
    app.state.arq_pool.enqueue_job = AsyncMock()

    auth_settings = Settings(
        _env_file=None,
        wazzup_webhook_auth_mode="enforce",
        wazzup_webhook_secret=STRONG_WEBHOOK_SECRET,
        wazzup_shadow_audit_ips=SHADOW_IP,
    )

    random_transport = ASGITransport(app=app, client=(RANDOM_IP, 54321))
    with (
        patch("src.api.v1.webhook.settings", auth_settings),
        patch(
            "src.api.v1.webhook.async_session_factory",
            return_value=_session_cm(session),
        ),
    ):
        async with AsyncClient(
            transport=random_transport, base_url="http://test"
        ) as ac:
            denied = await ac.post(
                "/api/v1/webhook/wazzup/observe",
                json={
                    "messages": [{"messageId": "obs-denied", "chatId": "971500000001"}]
                },
            )
            allowed = await ac.post(
                "/api/v1/webhook/wazzup/observe",
                headers={"Authorization": f"Bearer {STRONG_WEBHOOK_SECRET}"},
                json={
                    "messages": [
                        {
                            "messageId": "obs-allowed",
                            "chatId": "971500000002",
                            "text": "Observed Nikita chat",
                        }
                    ]
                },
            )

    assert denied.status_code == 401
    assert allowed.status_code == 200
    assert allowed.json() == {"ok": True, "observed": True, "stored": 1}
    assert "obs-allowed" in session.rows
    assert "obs-denied" not in session.rows
    app.state.redis.rpush.assert_not_called()
    app.state.arq_pool.enqueue_job.assert_not_called()
