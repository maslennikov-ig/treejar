from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest


class _ScalarResult:
    def __init__(self, value: object | None = None) -> None:
        self.value = value

    def scalar_one_or_none(self) -> object | None:
        return self.value

    def scalars(self) -> _ScalarResult:
        return self

    def all(self) -> list[object]:
        return [] if self.value is None else [self.value]


def _http_status_error(payload: dict[str, object]) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://api.wazzup24.com/v3/message")
    response = httpx.Response(400, json=payload, request=request)
    return httpx.HTTPStatusError(
        "Wazzup rejected message",
        request=request,
        response=response,
    )


@pytest.mark.asyncio
async def test_send_wazzup_text_with_audit_creates_row_and_uses_crm_message_id() -> (
    None
):
    from src.models.outbound_message import OutboundMessageAudit
    from src.services.outbound_audit import send_wazzup_text_with_audit

    db = AsyncMock()
    db.execute.return_value = _ScalarResult(None)
    db.add = MagicMock()
    db.flush = AsyncMock()
    provider = MagicMock()
    provider.outbound_chat_id.return_value = "971501234567"
    provider.send_text = AsyncMock(return_value="wz-msg-1")

    result = await send_wazzup_text_with_audit(
        db,
        provider=provider,
        conversation_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        chat_id="+971501234567#smoke",
        text="Hello",
        source="bot_reply",
        crm_message_id="bot:conv-1:msg-1",
    )

    provider.send_text.assert_awaited_once_with(
        "+971501234567#smoke",
        "Hello",
        crm_message_id="bot:conv-1:msg-1",
    )
    db.add.assert_called_once()
    audit = db.add.call_args.args[0]
    assert isinstance(audit, OutboundMessageAudit)
    assert audit.provider == "wazzup"
    assert audit.conversation_id == uuid.UUID("00000000-0000-0000-0000-000000000001")
    assert audit.chat_id == "+971501234567#smoke"
    assert audit.outbound_chat_id == "971501234567"
    assert audit.message_type == "text"
    assert audit.content == "Hello"
    assert audit.source == "bot_reply"
    assert audit.crm_message_id == "bot:conv-1:msg-1"
    assert audit.provider_message_id == "wz-msg-1"
    assert audit.status == "sent"
    assert result.skipped is False


@pytest.mark.asyncio
async def test_send_wazzup_text_with_audit_does_not_return_unknown_message_id() -> None:
    from src.models.outbound_message import OutboundMessageAudit
    from src.services.outbound_audit import send_wazzup_text_with_audit

    db = AsyncMock()
    db.execute.return_value = _ScalarResult(None)
    db.add = MagicMock()
    db.flush = AsyncMock()
    provider = MagicMock()
    provider.send_text = AsyncMock(return_value="unknown")

    result = await send_wazzup_text_with_audit(
        db,
        provider=provider,
        conversation_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        chat_id="+971501234567#smoke",
        text="Hello",
        source="manager_reply",
        crm_message_id="manager-reply:conv-1:msg-1",
    )

    audit = db.add.call_args.args[0]
    assert isinstance(audit, OutboundMessageAudit)
    assert audit.provider_message_id is None
    assert result.provider_message_id is None


@pytest.mark.asyncio
async def test_send_wazzup_text_with_audit_suppresses_duplicate_active_crm_id() -> None:
    from src.models.outbound_message import OutboundMessageAudit
    from src.services.outbound_audit import send_wazzup_text_with_audit

    existing = OutboundMessageAudit(
        provider="wazzup",
        conversation_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        chat_id="+971501234567",
        outbound_chat_id="971501234567",
        message_type="text",
        content="Hello",
        source="bot_reply",
        crm_message_id="bot:conv-1:msg-1",
        provider_message_id="wz-msg-1",
        status="sent",
    )
    db = AsyncMock()
    db.execute.return_value = _ScalarResult(existing)
    db.add = MagicMock()
    provider = AsyncMock()

    result = await send_wazzup_text_with_audit(
        db,
        provider=provider,
        conversation_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        chat_id="+971501234567",
        text="Hello",
        source="bot_reply",
        crm_message_id="bot:conv-1:msg-1",
    )

    provider.send_text.assert_not_called()
    db.add.assert_not_called()
    assert result.skipped is True
    assert result.provider_message_id == "wz-msg-1"


@pytest.mark.asyncio
async def test_send_wazzup_text_with_audit_persists_provider_duplicate_before_reraise() -> (
    None
):
    from src.models.outbound_message import OutboundMessageAudit
    from src.services.outbound_audit import send_wazzup_text_with_audit

    db = AsyncMock()
    db.execute.return_value = _ScalarResult(None)
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    provider = MagicMock()
    provider.send_text = AsyncMock(
        side_effect=_http_status_error({"error": "REPEATED_CRM_MESSAGE_ID"})
    )

    with pytest.raises(httpx.HTTPStatusError):
        await send_wazzup_text_with_audit(
            db,
            provider=provider,
            conversation_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            chat_id="+971501234567",
            text="Hello",
            source="bot_reply",
            crm_message_id="bot:conv-1:msg-1",
        )

    audit = db.add.call_args.args[0]
    assert isinstance(audit, OutboundMessageAudit)
    assert audit.status == "provider_duplicate"
    assert audit.error_details == {
        "status_code": 400,
        "payload": {"error": "REPEATED_CRM_MESSAGE_ID"},
    }
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_wazzup_text_with_audit_suppresses_provider_duplicate_crm_id() -> (
    None
):
    from src.models.outbound_message import OutboundMessageAudit
    from src.services.outbound_audit import send_wazzup_text_with_audit

    existing = OutboundMessageAudit(
        provider="wazzup",
        conversation_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        chat_id="+971501234567",
        outbound_chat_id="971501234567",
        message_type="text",
        content="Hello",
        source="bot_reply",
        crm_message_id="bot:conv-1:msg-1",
        status="provider_duplicate",
    )
    db = AsyncMock()
    db.execute.return_value = _ScalarResult(existing)
    db.add = MagicMock()
    provider = MagicMock()
    provider.send_text = AsyncMock()

    result = await send_wazzup_text_with_audit(
        db,
        provider=provider,
        conversation_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        chat_id="+971501234567",
        text="Hello",
        source="bot_reply",
        crm_message_id="bot:conv-1:msg-1",
    )

    provider.send_text.assert_not_awaited()
    db.add.assert_not_called()
    assert result.skipped is True
    assert result.audit is existing


@pytest.mark.asyncio
async def test_send_wazzup_text_with_audit_persists_provider_error_before_reraise() -> (
    None
):
    from src.models.outbound_message import OutboundMessageAudit
    from src.services.outbound_audit import send_wazzup_text_with_audit

    db = AsyncMock()
    db.execute.return_value = _ScalarResult(None)
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    provider = MagicMock()
    provider.send_text = AsyncMock(side_effect=RuntimeError("network down"))

    with pytest.raises(RuntimeError, match="network down"):
        await send_wazzup_text_with_audit(
            db,
            provider=provider,
            conversation_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            chat_id="+971501234567",
            text="Hello",
            source="bot_reply",
            crm_message_id="bot:conv-1:msg-1",
        )

    audit = db.add.call_args.args[0]
    assert isinstance(audit, OutboundMessageAudit)
    assert audit.status == "error"
    assert audit.error_details == {
        "error": "RuntimeError",
        "description": "network down",
    }
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_wazzup_text_with_audit_reuses_error_row_for_retry() -> None:
    from src.models.outbound_message import OutboundMessageAudit
    from src.services.outbound_audit import send_wazzup_text_with_audit

    existing = OutboundMessageAudit(
        provider="wazzup",
        conversation_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        chat_id="+971501234567",
        outbound_chat_id="971501234567",
        message_type="text",
        content="Hello",
        source="bot_reply",
        crm_message_id="bot:conv-1:msg-1",
        status="error",
        error_details={"error": "RuntimeError"},
    )
    db = AsyncMock()
    db.execute.return_value = _ScalarResult(existing)
    db.add = MagicMock()
    provider = MagicMock()
    provider.send_text = AsyncMock(return_value="wz-msg-2")

    result = await send_wazzup_text_with_audit(
        db,
        provider=provider,
        conversation_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        chat_id="+971501234567",
        text="Retry hello",
        source="bot_reply",
        crm_message_id="bot:conv-1:msg-1",
    )

    db.add.assert_not_called()
    provider.send_text.assert_awaited_once()
    assert result.skipped is False
    assert result.audit is existing
    assert existing.content == "Retry hello"
    assert existing.error_details is None
    assert existing.provider_message_id == "wz-msg-2"
    assert existing.status == "sent"


@pytest.mark.asyncio
async def test_send_wazzup_media_with_audit_persists_provider_duplicate_before_reraise() -> (
    None
):
    from src.models.outbound_message import OutboundMessageAudit
    from src.services.outbound_audit import send_wazzup_media_with_audit

    db = AsyncMock()
    db.execute.return_value = _ScalarResult(None)
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    provider = MagicMock()
    provider.send_media = AsyncMock(
        side_effect=_http_status_error({"error": "repeatedCrmMessageId"})
    )

    with pytest.raises(httpx.HTTPStatusError):
        await send_wazzup_media_with_audit(
            db,
            provider=provider,
            conversation_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            chat_id="+971501234567",
            source="product_media",
            crm_message_id="product:conv-1:sku-1:media",
            url="https://example.com/image.jpg",
        )

    audit = db.add.call_args.args[0]
    assert isinstance(audit, OutboundMessageAudit)
    assert audit.message_type == "media"
    assert audit.status == "provider_duplicate"
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_wazzup_media_with_audit_suppresses_provider_duplicate_crm_id() -> (
    None
):
    from src.models.outbound_message import OutboundMessageAudit
    from src.services.outbound_audit import send_wazzup_media_with_audit

    existing = OutboundMessageAudit(
        provider="wazzup",
        conversation_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        chat_id="+971501234567",
        outbound_chat_id="971501234567",
        message_type="media",
        content_uri="https://example.com/image.jpg",
        source="product_media",
        crm_message_id="product:conv-1:sku-1:media",
        status="provider_duplicate",
    )
    db = AsyncMock()
    db.execute.return_value = _ScalarResult(existing)
    db.add = MagicMock()
    provider = MagicMock()
    provider.send_media = AsyncMock()

    result = await send_wazzup_media_with_audit(
        db,
        provider=provider,
        conversation_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        chat_id="+971501234567",
        source="product_media",
        crm_message_id="product:conv-1:sku-1:media",
        url="https://example.com/image.jpg",
    )

    provider.send_media.assert_not_awaited()
    db.add.assert_not_called()
    assert result.skipped is True
    assert result.media.audit is existing


@pytest.mark.asyncio
async def test_send_wazzup_media_with_audit_retries_failed_caption_only() -> None:
    from src.models.outbound_message import OutboundMessageAudit
    from src.services.outbound_audit import send_wazzup_media_with_audit

    media = OutboundMessageAudit(
        provider="wazzup",
        conversation_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        chat_id="+971501234567",
        outbound_chat_id="971501234567",
        message_type="media",
        content_uri="https://example.com/image.jpg",
        source="product_media",
        crm_message_id="product:conv-1:sku-1:media",
        provider_message_id="wz-media-1",
        status="sent",
    )
    caption = OutboundMessageAudit(
        provider="wazzup",
        conversation_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        chat_id="+971501234567",
        outbound_chat_id="971501234567",
        message_type="caption",
        content="Caption",
        caption="Caption",
        source="product_media",
        crm_message_id="product:conv-1:sku-1:caption",
        status="error",
        error_details={"error": "caption_send_failed"},
    )
    db = AsyncMock()
    db.execute.side_effect = [_ScalarResult(media), _ScalarResult(caption)]
    db.add = MagicMock()
    db.flush = AsyncMock()
    provider = MagicMock()
    provider.send_media = AsyncMock()
    provider.send_text = AsyncMock(return_value="wz-caption-2")

    result = await send_wazzup_media_with_audit(
        db,
        provider=provider,
        conversation_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        chat_id="+971501234567",
        source="product_media",
        crm_message_id="product:conv-1:sku-1:media",
        caption_crm_message_id="product:conv-1:sku-1:caption",
        url="https://example.com/image.jpg",
        caption="Caption",
    )

    provider.send_media.assert_not_awaited()
    provider.send_text.assert_awaited_once_with(
        "+971501234567",
        "Caption",
        crm_message_id="product:conv-1:sku-1:caption",
    )
    db.add.assert_not_called()
    assert result.media.skipped is True
    assert result.caption is not None
    assert result.caption.skipped is False
    assert result.caption.provider_message_id == "wz-caption-2"
    assert caption.status == "sent"
    assert caption.provider_message_id == "wz-caption-2"
    assert caption.error_details is None


class _DetailedMediaProvider:
    def __init__(self, result: SimpleNamespace) -> None:
        self.result = result

    def outbound_chat_id(self, chat_id: str) -> str:
        return chat_id

    async def send_media_detailed(self, **kwargs: object) -> SimpleNamespace:
        return self.result


@pytest.mark.asyncio
async def test_send_wazzup_media_with_audit_marks_unknown_caption_id_as_error() -> None:
    from src.models.outbound_message import OutboundMessageAudit
    from src.services.outbound_audit import send_wazzup_media_with_audit

    db = AsyncMock()
    db.execute.side_effect = [_ScalarResult(None), _ScalarResult(None)]
    db.add = MagicMock()
    db.flush = AsyncMock()
    provider = _DetailedMediaProvider(
        SimpleNamespace(
            message_id="wz-media-1",
            caption_message_id="unknown",
            content_uri="https://example.com/image.jpg",
            outbound_chat_id="971501234567",
        )
    )

    result = await send_wazzup_media_with_audit(
        db,
        provider=provider,
        conversation_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        chat_id="+971501234567",
        source="product_media",
        crm_message_id="product:conv-1:sku-1:media",
        caption_crm_message_id="product:conv-1:sku-1:caption",
        url="https://example.com/image.jpg",
        caption="Caption",
    )

    assert db.add.call_count == 2
    media_audit = db.add.call_args_list[0].args[0]
    caption_audit = db.add.call_args_list[1].args[0]
    assert isinstance(media_audit, OutboundMessageAudit)
    assert isinstance(caption_audit, OutboundMessageAudit)
    assert media_audit.status == "sent"
    assert media_audit.provider_message_id == "wz-media-1"
    assert caption_audit.status == "error"
    assert caption_audit.provider_message_id is None
    assert caption_audit.error_details == {
        "error": "caption_send_failed",
        "description": "Provider returned no caption message id.",
    }
    assert result.caption is not None
    assert result.caption.provider_message_id is None


@pytest.mark.asyncio
async def test_update_wazzup_statuses_updates_matching_audit_and_ignores_unknown() -> (
    None
):
    from src.models.outbound_message import OutboundMessageAudit
    from src.services.outbound_audit import update_wazzup_statuses

    matching = OutboundMessageAudit(
        provider="wazzup",
        conversation_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        chat_id="+971501234567",
        outbound_chat_id="971501234567",
        message_type="text",
        content="Hello",
        source="bot_reply",
        provider_message_id="known-msg",
        status="sent",
    )
    db = AsyncMock()
    db.execute.side_effect = [_ScalarResult(matching), _ScalarResult(None)]

    updated = await update_wazzup_statuses(
        db,
        [
            {
                "messageId": "known-msg",
                "timestamp": "2026-04-26T12:00:00.000Z",
                "status": "delivered",
            },
            {
                "messageId": "unknown-msg",
                "timestamp": "2026-04-26T12:01:00.000Z",
                "status": "read",
            },
        ],
    )

    assert updated == 1
    assert matching.status == "delivered"
    assert matching.status_updated_at == datetime(
        2026, 4, 26, 12, 0, tzinfo=UTC
    ).replace(tzinfo=None)
    assert matching.error_details is None
