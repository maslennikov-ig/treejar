from __future__ import annotations

import asyncio
import json
import os
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.schema import CreateSchema

from src.core.config import settings
from src.integrations.messaging.wazzup import WazzupProvider
from src.models.conversation import Conversation
from src.models.conversation_summary import ConversationSummary
from src.models.message import Message
from src.models.outbound_message import OutboundMessageAudit
from src.models.system_config import SystemConfig
from src.services.outbound_audit import (
    send_wazzup_media_with_audit,
    send_wazzup_template_with_audit,
    send_wazzup_text_with_audit,
    update_wazzup_statuses,
)

CHANNEL = "00000000-0000-0000-0000-000000000065"
FOREIGN = "00000000-0000-0000-0000-000000000023"
CONVERSATION = uuid.UUID("00000000-0000-0000-0000-000000000001")
PHONE = "15550000001"


@pytest.fixture
def configured_sender(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "wazzup_channel_id", CHANNEL)
    # Works before the setting is introduced, so RED exercises real behavior.
    monkeypatch.setitem(
        settings.__dict__, "wazzup_outbound_allowed_channel_id", CHANNEL
    )


def safety_db(*, enabled: object = True, inbound: object = CHANNEL) -> AsyncMock:
    db = AsyncMock()
    db.add = MagicMock()
    db.scalar.return_value = enabled
    db.execute.return_value = SimpleNamespace(
        one_or_none=lambda: (PHONE, {"inbound_channel_id": inbound}),
        scalar_one_or_none=lambda: None,
    )
    return db


async def audited_send(db: AsyncMock, provider: WazzupProvider, kind: str) -> object:
    common = dict(
        provider=provider,
        conversation_id=CONVERSATION,
        chat_id=PHONE,
        source="safety_test",
        crm_message_id="safety:message",
    )
    if kind == "text":
        return await send_wazzup_text_with_audit(db, text="Hello", **common)
    if kind == "template":
        return await send_wazzup_template_with_audit(
            db, template_name="approved-template", params={}, **common
        )
    return await send_wazzup_media_with_audit(
        db,
        content=b"private PDF",
        content_type="application/pdf",
        caption="Caption",
        caption_crm_message_id="safety:caption",
        **common,
    )


@pytest.fixture
async def transport() -> tuple[WazzupProvider, list[httpx.Request], list[bytes]]:
    requests: list[httpx.Request] = []
    uploads: list[bytes] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"messageId": f"message-{len(requests)}"})

    async def upload(content: bytes, content_type: str | None = None) -> str:
        uploads.append(content)
        return "https://example.invalid/media.pdf"

    provider = WazzupProvider(channel_id=CHANNEL)
    await provider.client.aclose()
    provider.client = httpx.AsyncClient(
        transport=httpx.MockTransport(handle), base_url="https://example.invalid"
    )
    # Only the external upload is replaced; actual media/audit/transport code runs.
    provider._upload_to_tmpfiles = upload
    try:
        yield provider, requests, uploads
    finally:
        await provider.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["text", "media", "template"])
@pytest.mark.parametrize(
    "enabled,inbound",
    [
        (False, CHANNEL),
        (None, CHANNEL),
        ("false", CHANNEL),
        (True, FOREIGN),
        (True, None),
    ],
)
async def test_denied_audited_send_has_no_http_or_upload(
    configured_sender: None,
    transport: tuple,
    kind: str,
    enabled: object,
    inbound: object,
) -> None:
    provider, requests, uploads = transport
    db = safety_db(enabled=enabled, inbound=inbound)
    with pytest.raises(RuntimeError):
        await audited_send(db, provider, kind)
    assert requests == []
    assert uploads == []
    assert not any(call.args[0].status == "sent" for call in db.add.call_args_list)


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["text", "media", "template"])
async def test_approved_channel_sends_and_scope_cannot_be_reused(
    configured_sender: None, transport: tuple, kind: str
) -> None:
    provider, requests, uploads = transport
    result = await audited_send(safety_db(), provider, kind)
    assert (result.media if kind == "media" else result).audit.status == "sent"
    assert len(requests) == (2 if kind == "media" else 1)
    assert all(json.loads(r.content)["channelId"] == CHANNEL for r in requests)
    assert uploads == ([b"private PDF"] if kind == "media" else [])
    with pytest.raises(RuntimeError):
        await provider.send_text(PHONE, "Unaudited bypass")
    assert len(requests) == (2 if kind == "media" else 1)


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["text", "media", "template", "request"])
async def test_direct_provider_send_cannot_bypass_authorization(
    configured_sender: None, transport: tuple, kind: str
) -> None:
    provider, requests, uploads = transport
    with pytest.raises(RuntimeError):
        if kind == "text":
            await provider.send_text(PHONE, "Direct")
        elif kind == "template":
            await provider.send_template(PHONE, "template")
        elif kind == "media":
            await provider.send_media(PHONE, content=b"private PDF")
        else:
            await provider._request(
                "POST", "/message", json={"channelId": CHANNEL, "chatId": PHONE}
            )
    assert requests == []
    assert uploads == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "missing", ["sender", "allowed", "wrong_sender", "recipient", "conversation"]
)
async def test_incomplete_or_mismatched_authorization_is_denied(
    configured_sender: None,
    transport: tuple,
    monkeypatch: pytest.MonkeyPatch,
    missing: str,
) -> None:
    provider, requests, uploads = transport
    db = safety_db()
    if missing == "sender":
        monkeypatch.setattr(settings, "wazzup_channel_id", "")
    elif missing == "allowed":
        monkeypatch.setitem(settings.__dict__, "wazzup_outbound_allowed_channel_id", "")
    elif missing == "wrong_sender":
        provider.channel_id = FOREIGN
    else:
        db.execute.return_value.one_or_none = lambda: (
            None
            if missing == "conversation"
            else ("15550000999", {"inbound_channel_id": CHANNEL})
        )
    with pytest.raises(RuntimeError):
        await audited_send(db, provider, "media")
    assert requests == []
    assert uploads == []


@pytest.mark.asyncio
async def test_disabled_between_upload_and_send_stops_http(
    configured_sender: None, transport: tuple
) -> None:
    provider, requests, uploads = transport
    db = safety_db()

    async def upload(content: bytes, content_type: str | None = None) -> str:
        uploads.append(content)
        db.scalar.return_value = False
        return "https://example.invalid/media.pdf"

    provider._upload_to_tmpfiles = upload
    with pytest.raises(RuntimeError):
        await audited_send(db, provider, "media")
    assert uploads == [b"private PDF"]
    assert requests == []
    assert all(call.args[0].status == "error" for call in db.add.call_args_list)


@pytest.mark.asyncio
async def test_provider_omitted_channel_uses_configured_sender(
    configured_sender: None,
) -> None:
    async with WazzupProvider() as provider:
        assert provider.channel_id == CHANNEL


@pytest.mark.asyncio
async def test_read_only_channel_lookup_does_not_require_send_scope(
    transport: tuple,
) -> None:
    provider, requests, uploads = transport
    assert await provider.resolve_channel_phone(CHANNEL) is None
    assert len(requests) == 1
    assert requests[0].method == "GET"
    assert uploads == []


@pytest.mark.asyncio
async def test_task_inheriting_context_cannot_send(
    configured_sender: None, transport: tuple
) -> None:
    provider, requests, _ = transport

    async def upload(content: bytes, content_type: str | None = None) -> str:
        with pytest.raises(RuntimeError, match="audited_send_scope_required"):
            await asyncio.create_task(provider.send_text(PHONE, "Inherited bypass"))
        return "https://example.invalid/media.pdf"

    provider._upload_to_tmpfiles = upload
    await audited_send(safety_db(), provider, "media")
    assert len(requests) == 2


@pytest.mark.asyncio
async def test_disabled_during_retry_does_not_repeat_http(
    configured_sender: None, transport: tuple, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider, requests, _ = transport
    db = safety_db()

    def rate_limited(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        db.scalar.return_value = False
        return httpx.Response(429)

    await provider.client.aclose()
    provider.client = httpx.AsyncClient(
        transport=httpx.MockTransport(rate_limited), base_url="https://example.invalid"
    )
    monkeypatch.setattr("src.integrations.messaging.wazzup.asyncio.sleep", AsyncMock())
    with pytest.raises(RuntimeError, match="bot_not_enabled"):
        await audited_send(db, provider, "text")
    assert len(requests) == 1
    assert db.add.call_args.args[0].status == "error"


@pytest.mark.asyncio
@pytest.mark.parametrize("enabled", [False, True])
async def test_real_upload_and_message_http_boundary(
    configured_sender: None, monkeypatch: pytest.MonkeyPatch, enabled: bool
) -> None:
    requests: list[httpx.Request] = []
    client_class = httpx.AsyncClient

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/api/v1/upload":
            return httpx.Response(
                200,
                json={
                    "status": "success",
                    "data": {"url": "https://tmpfiles.org/file.pdf"},
                },
            )
        if request.method == "GET":
            return httpx.Response(200, content=b"private PDF")
        return httpx.Response(200, json={"messageId": f"message-{len(requests)}"})

    def local_client(**kwargs: object) -> httpx.AsyncClient:
        return client_class(**kwargs, transport=httpx.MockTransport(handle))

    monkeypatch.setattr(
        "src.integrations.messaging.wazzup.httpx.AsyncClient", local_client
    )
    async with WazzupProvider() as provider:
        if enabled:
            result = await audited_send(safety_db(), provider, "media")
            assert result.media.audit.status == "sent"
            assert [r.method for r in requests] == ["POST", "GET", "POST", "POST"]
        else:
            with pytest.raises(RuntimeError):
                await audited_send(safety_db(enabled=False), provider, "media")
            assert requests == []


@pytest_asyncio.fixture(loop_scope="function")
async def local_pg_db() -> AsyncIterator[AsyncSession]:
    """Isolated schema, rolled back including any audit helper commits."""
    url = make_url(
        os.getenv(
            "TREEJAR_TEST_POSTGRES_URL",
            "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/postgres",
        )
    )
    if url.host not in {"127.0.0.1", "localhost", "::1"}:
        pytest.fail("Safety integration tests refuse non-local PostgreSQL")
    engine = create_async_engine(url, connect_args={"timeout": 2})
    try:
        try:
            connection = await engine.connect()
        except Exception as exc:
            pytest.skip(f"Local PostgreSQL unavailable: {type(exc).__name__}")
        try:
            transaction = await connection.begin()
            schema = f"safety_{uuid.uuid4().hex}"
            try:
                await connection.execute(CreateSchema(schema))
                await connection.execution_options(schema_translate_map={None: schema})
                for model in (
                    Conversation,
                    SystemConfig,
                    OutboundMessageAudit,
                    Message,
                    ConversationSummary,
                ):
                    await connection.run_sync(model.__table__.create)
                async with AsyncSession(
                    bind=connection,
                    expire_on_commit=False,
                    join_transaction_mode="create_savepoint",
                ) as db:
                    db.add(
                        Conversation(
                            id=CONVERSATION,
                            phone=PHONE,
                            metadata_={"inbound_channel_id": CHANNEL},
                        )
                    )
                    db.add(SystemConfig(key="bot_enabled", value=True))
                    await db.commit()
                    yield db
            finally:
                await transaction.rollback()
                remaining = await connection.scalar(
                    text("SELECT count(*) FROM pg_namespace WHERE nspname=:schema"),
                    {"schema": schema},
                )
                assert remaining == 0
        finally:
            await connection.close()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_local_postgres_send_and_status_roundtrip(
    configured_sender: None, transport: tuple, local_pg_db: AsyncSession
) -> None:
    provider, requests, _ = transport
    db = local_pg_db
    result = await audited_send(db, provider, "text")
    result.audit.status_updated_at = datetime(2026, 8, 28, 12, tzinfo=UTC)
    audit_id = result.audit.id
    await db.commit()
    db.expunge_all()
    row = await db.get(OutboundMessageAudit, audit_id)
    assert row.status_updated_at.tzinfo is not None
    assert (
        await update_wazzup_statuses(
            db,
            [
                {
                    "messageId": "message-1",
                    "status": "delivered",
                    "timestamp": "2026-08-28T12:01:00Z",
                }
            ],
        )
        == 1
    )
    await db.commit()
    db.expunge_all()
    row = await db.get(OutboundMessageAudit, audit_id)
    assert row.status == "delivered"
    assert row.status_updated_at == datetime(2026, 8, 28, 12, 1, tzinfo=UTC)
    assert (
        await update_wazzup_statuses(
            db,
            [
                {
                    "messageId": "message-1",
                    "status": "read",
                    "timestamp": "2026-08-28T12:02:00Z",
                }
            ],
        )
        == 1
    )
    assert (
        await update_wazzup_statuses(
            db,
            [
                {
                    "messageId": "message-1",
                    "status": "sent",
                    "timestamp": "2026-08-28T12:03:00Z",
                },
                {
                    "messageId": "message-1",
                    "status": "delivered",
                    "timestamp": "2026-08-28T12:00:00Z",
                },
            ],
        )
        == 0
    )
    await db.commit()
    db.expunge_all()
    assert (await db.get(OutboundMessageAudit, audit_id)).status == "read"
    assert len(requests) == 1


@pytest.mark.asyncio
async def test_local_postgres_disable_cannot_use_cached_enabled_value(
    configured_sender: None, transport: tuple, local_pg_db: AsyncSession
) -> None:
    provider, requests, uploads = transport
    db = local_pg_db
    cached = await db.get(SystemConfig, "bot_enabled")
    assert cached.value is True
    # A column-level update deliberately leaves the identity-map object stale.
    await db.execute(
        SystemConfig.__table__.update()
        .where(SystemConfig.key == "bot_enabled")
        .values(value=False)
    )
    await db.commit()
    assert cached.value is True
    with pytest.raises(RuntimeError, match="bot_not_enabled"):
        await audited_send(db, provider, "media")
    assert requests == []
    assert uploads == []
    assert (await db.scalars(select(OutboundMessageAudit))).all() == []


@pytest.mark.asyncio
@pytest.mark.parametrize("permission", ["allowed", "disabled", "foreign"])
async def test_feedback_customer_flow_persists_only_after_authorized_send(
    configured_sender: None,
    transport: tuple,
    local_pg_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    permission: str,
) -> None:
    """Real background caller, DB reads/writes and send boundary; no guard mock."""
    from src.services.followup import _send_feedback_request

    provider, requests, uploads = transport
    db = local_pg_db
    conversation = await db.get(Conversation, CONVERSATION)
    conversation.deal_status = "delivered"
    conversation.deal_delivered_at = datetime(2026, 8, 27, 10, tzinfo=UTC)
    conversation.zoho_deal_id = "fixture-order"
    conversation.metadata_ = {
        "inbound_channel_id": FOREIGN if permission == "foreign" else CHANNEL
    }
    if permission == "disabled":
        config = await db.get(SystemConfig, "bot_enabled")
        config.value = False
    await db.commit()

    # Supply the real provider with a local HTTP transport, not a send-method fake.
    monkeypatch.setattr("src.services.followup.WazzupProvider", lambda: provider)
    now = datetime(2026, 8, 28, 12, tzinfo=UTC)
    if permission == "allowed":
        await _send_feedback_request(db, conversation, now=now)
        assert len(requests) == 1
        payload = json.loads(requests[0].content)
        assert payload["channelId"] == CHANNEL
        assert payload["chatId"] == PHONE
    else:
        with pytest.raises(RuntimeError):
            await _send_feedback_request(db, conversation, now=now)
        assert requests == []
    assert uploads == []

    db.expunge_all()
    persisted = await db.get(Conversation, CONVERSATION)
    audits = (await db.scalars(select(OutboundMessageAudit))).all()
    if permission == "allowed":
        assert persisted.sales_stage == "feedback"
        assert persisted.metadata_["feedback_request"]["status"] == "sent"
        assert len(audits) == 1
        assert audits[0].source == "feedback_request"
        assert audits[0].status == "sent"
    else:
        assert persisted.sales_stage == "greeting"
        assert "feedback_request" not in persisted.metadata_
        assert audits == []


@pytest.mark.asyncio
@pytest.mark.parametrize("old_channel", [FOREIGN, None])
async def test_inbound_channel_does_not_rebind_existing_phone_conversation(
    configured_sender: None,
    transport: tuple,
    local_pg_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    old_channel: str | None,
) -> None:
    """New channel gets a new history; retained IDs stay forbidden to later sends."""
    from src.llm.response_runtime import LLMResponse
    from src.services.chat import _process_batch_inner
    from src.services.followup import _send_feedback_request

    provider, requests, _ = transport
    db = local_pg_db
    old = await db.get(Conversation, CONVERSATION)
    old_metadata = {"zoho_sale_order_id": "old-order"}
    if old_channel is not None:
        old_metadata["inbound_channel_id"] = old_channel
    old.metadata_ = old_metadata
    old.deal_status = "delivered"
    old.deal_delivered_at = datetime(2026, 8, 27, 10, tzinfo=UTC)
    db.add(Message(conversation_id=old.id, role="user", content="Old private order"))
    await db.commit()
    seen_histories: list[list[str]] = []

    @asynccontextmanager
    async def database_session():
        yield db

    @asynccontextmanager
    async def inert_zoho(**kwargs: object):
        yield None

    async def local_model(**kwargs: object) -> LLMResponse:
        rows = await db.scalars(
            select(Message.content).where(
                Message.conversation_id == kwargs["conversation_id"]
            )
        )
        seen_histories.append(list(rows))
        return LLMResponse(
            text="Hello", tokens_in=0, tokens_out=0, cost=0, model="local-fixture"
        )

    monkeypatch.setattr("src.services.chat.async_session_factory", database_session)
    monkeypatch.setattr("src.services.chat.WazzupProvider", lambda **kwargs: provider)
    monkeypatch.setattr("src.services.followup.WazzupProvider", lambda: provider)
    monkeypatch.setattr("src.services.chat.ZohoInventoryClient", inert_zoho)
    monkeypatch.setattr("src.services.chat.ZohoCRMClient", inert_zoho)
    monkeypatch.setattr("src.services.chat.EmbeddingEngine", lambda: None)
    monkeypatch.setattr("src.services.chat.process_message", local_model)
    redis = AsyncMock()
    redis.set.return_value = True
    redis.get.return_value = None
    await _process_batch_inner(
        redis,
        PHONE,
        [
            json.dumps(
                {
                    "messageId": "fresh-test-inbound",
                    "chatId": PHONE,
                    "channelId": CHANNEL,
                    "text": "Fresh hello",
                    "type": "text",
                    "timestamp": 1787918400,
                }
            )
        ],
    )

    db.expunge_all()
    conversations = (
        await db.scalars(select(Conversation).where(Conversation.phone == PHONE))
    ).all()
    assert len(conversations) == 2
    new = next(c for c in conversations if c.id != CONVERSATION)
    retained = next(c for c in conversations if c.id == CONVERSATION)
    assert retained.metadata_ == old_metadata
    assert retained.deal_status == "delivered"
    assert new.metadata_["inbound_channel_id"] == CHANNEL
    assert new.zoho_deal_id is None
    assert "zoho_sale_order_id" not in new.metadata_
    assert seen_histories == [["Fresh hello"]]
    audit = (await db.scalars(select(OutboundMessageAudit))).one()
    assert audit.conversation_id == new.id
    assert audit.status == "sent"
    before_denied_sends = len(requests)
    with pytest.raises(RuntimeError, match="inbound_channel_not_allowed"):
        await send_wazzup_text_with_audit(
            db,
            provider=provider,
            conversation_id=retained.id,
            chat_id=PHONE,
            text="Old manager reply",
            source="manager_reply",
            crm_message_id="old-manager",
        )
    with pytest.raises(RuntimeError, match="inbound_channel_not_allowed"):
        await _send_feedback_request(
            db, retained, now=datetime(2026, 8, 28, 12, tzinfo=UTC)
        )
    assert len(requests) == before_denied_sends
    assert (await db.scalars(select(OutboundMessageAudit))).all() == [audit]


@pytest.mark.asyncio
@pytest.mark.parametrize("aware", [True, False])
@pytest.mark.parametrize(
    "timestamp",
    ["2026-08-28T12:01:00Z", "2026-08-28T15:01:00+03:00", "2026-08-28T12:01:00"],
)
async def test_status_update_accepts_db_and_legacy_timestamps(
    aware: bool, timestamp: str
) -> None:
    row = OutboundMessageAudit(
        status="sent",
        status_updated_at=datetime(2026, 8, 28, 12, tzinfo=UTC if aware else None),
    )
    db = AsyncMock()
    db.execute.return_value = SimpleNamespace(scalar_one_or_none=lambda: row)
    assert (
        await update_wazzup_statuses(
            db, [{"messageId": "known", "status": "delivered", "timestamp": timestamp}]
        )
        == 1
    )
    assert row.status == "delivered"
    assert row.status_updated_at == datetime(2026, 8, 28, 12, 1, tzinfo=UTC)
    assert (
        await update_wazzup_statuses(
            db,
            [
                {
                    "messageId": "known",
                    "status": "read",
                    "timestamp": "2026-08-28T12:02:00Z",
                }
            ],
        )
        == 1
    )
    assert (
        await update_wazzup_statuses(
            db,
            [
                {
                    "messageId": "known",
                    "status": "sent",
                    "timestamp": "2026-08-28T12:03:00Z",
                },
                {
                    "messageId": "known",
                    "status": "delivered",
                    "timestamp": "2026-08-28T12:00:00Z",
                },
            ],
        )
        == 0
    )
    assert row.status == "read"
    assert row.status_updated_at == datetime(2026, 8, 28, 12, 2, tzinfo=UTC)
