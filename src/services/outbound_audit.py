from __future__ import annotations

import hashlib
import inspect
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.outbound_message import OutboundMessageAudit

_ACTIVE_AUDIT_STATUSES = {
    "pending",
    "sent",
    "delivered",
    "read",
    "edited",
    "provider_duplicate",
}
_PROVIDER = "wazzup"


@dataclass
class AuditedSendResult:
    audit: OutboundMessageAudit
    provider_message_id: str | None
    skipped: bool = False


@dataclass
class AuditedMediaSendResult:
    media: AuditedSendResult
    caption: AuditedSendResult | None = None

    @property
    def skipped(self) -> bool:
        return self.media.skipped


def deterministic_crm_message_id(*parts: object) -> str:
    raw = ":".join(str(part).strip().replace(":", "-") for part in parts)
    if len(raw) <= 240:
        return raw
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
    return f"{raw[:215]}:{digest}"


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _parse_status_timestamp(value: object) -> datetime:
    if isinstance(value, str) and value.strip():
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            return parsed.astimezone(UTC).replace(tzinfo=None)
        return parsed
    return _now()


def _provider_message_id(value: str | None) -> str | None:
    if not value or value == "unknown":
        return None
    return value


def _outbound_chat_id(provider: Any, chat_id: str) -> str:
    resolver = getattr(provider, "outbound_chat_id", None)
    if callable(resolver):
        resolved = resolver(chat_id)
        if isinstance(resolved, str):
            return resolved
    return chat_id


def _has_real_media_detailed(provider: Any) -> bool:
    method = inspect.getattr_static(type(provider), "send_media_detailed", None)
    return method is not None


async def _find_by_crm_message_id(
    db: AsyncSession,
    crm_message_id: str | None,
) -> OutboundMessageAudit | None:
    if not crm_message_id:
        return None
    result = await db.execute(
        select(OutboundMessageAudit).where(
            OutboundMessageAudit.provider == _PROVIDER,
            OutboundMessageAudit.crm_message_id == crm_message_id,
        )
    )
    found = result.scalar_one_or_none()
    return found if isinstance(found, OutboundMessageAudit) else None


def _is_active(audit: OutboundMessageAudit | None) -> bool:
    return bool(audit and audit.status in _ACTIVE_AUDIT_STATUSES)


async def _flush_and_commit_failed_attempt(db: AsyncSession) -> None:
    await db.flush()
    await db.commit()


def _http_error_details(exc: httpx.HTTPStatusError) -> dict[str, Any]:
    try:
        payload = exc.response.json()
    except Exception:
        payload = {"text": exc.response.text}
    return {
        "status_code": exc.response.status_code,
        "payload": payload,
    }


def _is_repeated_crm_message_id(exc: httpx.HTTPStatusError) -> bool:
    details = _http_error_details(exc)
    payload = details.get("payload")
    if not isinstance(payload, dict):
        return False
    error = str(payload.get("error", "")).lower()
    return error in {"repeatedcrmmessageid", "repeated_crm_message_id"}


async def send_wazzup_text_with_audit(
    db: AsyncSession,
    *,
    provider: Any,
    conversation_id: uuid.UUID,
    chat_id: str,
    text: str,
    source: str,
    crm_message_id: str | None,
    message_type: str = "text",
) -> AuditedSendResult:
    existing = await _find_by_crm_message_id(db, crm_message_id)
    if existing is not None and _is_active(existing):
        return AuditedSendResult(
            audit=existing,
            provider_message_id=existing.provider_message_id,
            skipped=True,
        )

    if existing is not None:
        audit = existing
        audit.conversation_id = conversation_id
        audit.chat_id = chat_id
        audit.outbound_chat_id = _outbound_chat_id(provider, chat_id)
        audit.message_type = message_type
        audit.content = text
        audit.source = source
        audit.provider_message_id = None
        audit.error_details = None
        audit.details = None
        audit.status = "pending"
        audit.status_updated_at = _now()
    else:
        audit = OutboundMessageAudit(
            provider=_PROVIDER,
            conversation_id=conversation_id,
            chat_id=chat_id,
            outbound_chat_id=_outbound_chat_id(provider, chat_id),
            message_type=message_type,
            content=text,
            source=source,
            crm_message_id=crm_message_id,
            status="pending",
            status_updated_at=_now(),
        )
        db.add(audit)
    await db.flush()

    try:
        message_id = await provider.send_text(
            chat_id,
            text,
            crm_message_id=crm_message_id,
        )
    except httpx.HTTPStatusError as exc:
        audit.status = (
            "provider_duplicate" if _is_repeated_crm_message_id(exc) else "error"
        )
        audit.status_updated_at = _now()
        audit.error_details = _http_error_details(exc)
        await _flush_and_commit_failed_attempt(db)
        raise
    except Exception as exc:
        audit.status = "error"
        audit.status_updated_at = _now()
        audit.error_details = {"error": type(exc).__name__, "description": str(exc)}
        await _flush_and_commit_failed_attempt(db)
        raise

    normalized_message_id = _provider_message_id(message_id)
    audit.provider_message_id = normalized_message_id
    audit.status = "sent"
    audit.status_updated_at = _now()
    await db.flush()
    return AuditedSendResult(audit=audit, provider_message_id=normalized_message_id)


async def send_wazzup_template_with_audit(
    db: AsyncSession,
    *,
    provider: Any,
    conversation_id: uuid.UUID,
    chat_id: str,
    template_name: str,
    params: dict[str, str] | None,
    source: str,
    crm_message_id: str,
) -> AuditedSendResult:
    existing = await _find_by_crm_message_id(db, crm_message_id)
    if existing is not None and _is_active(existing):
        return AuditedSendResult(
            audit=existing,
            provider_message_id=existing.provider_message_id,
            skipped=True,
        )

    if existing is not None:
        audit = existing
        audit.conversation_id = conversation_id
        audit.chat_id = chat_id
        audit.outbound_chat_id = _outbound_chat_id(provider, chat_id)
        audit.message_type = "template"
        audit.content = template_name
        audit.source = source
        audit.provider_message_id = None
        audit.error_details = None
        audit.details = {"params": params or {}}
        audit.status = "pending"
        audit.status_updated_at = _now()
    else:
        audit = OutboundMessageAudit(
            provider=_PROVIDER,
            conversation_id=conversation_id,
            chat_id=chat_id,
            outbound_chat_id=_outbound_chat_id(provider, chat_id),
            message_type="template",
            content=template_name,
            source=source,
            crm_message_id=crm_message_id,
            details={"params": params or {}},
            status="pending",
            status_updated_at=_now(),
        )
        db.add(audit)
    await db.flush()

    try:
        message_id = await provider.send_template(
            chat_id,
            template_name,
            params or {},
            crm_message_id=crm_message_id,
        )
    except httpx.HTTPStatusError as exc:
        audit.status = (
            "provider_duplicate" if _is_repeated_crm_message_id(exc) else "error"
        )
        audit.status_updated_at = _now()
        audit.error_details = _http_error_details(exc)
        await _flush_and_commit_failed_attempt(db)
        raise
    except Exception as exc:
        audit.status = "error"
        audit.status_updated_at = _now()
        audit.error_details = {"error": type(exc).__name__, "description": str(exc)}
        await _flush_and_commit_failed_attempt(db)
        raise

    normalized_message_id = _provider_message_id(message_id)
    audit.provider_message_id = normalized_message_id
    audit.status = "sent"
    audit.status_updated_at = _now()
    await db.flush()
    return AuditedSendResult(audit=audit, provider_message_id=normalized_message_id)


async def send_wazzup_media_with_audit(
    db: AsyncSession,
    *,
    provider: Any,
    conversation_id: uuid.UUID,
    chat_id: str,
    source: str,
    crm_message_id: str,
    url: str | None = None,
    caption: str | None = None,
    content: bytes | None = None,
    content_type: str | None = None,
    caption_crm_message_id: str | None = None,
    file_name: str | None = None,
) -> AuditedMediaSendResult:
    existing = await _find_by_crm_message_id(db, crm_message_id)
    if existing is not None and _is_active(existing):
        media_result = AuditedSendResult(
            audit=existing,
            provider_message_id=existing.provider_message_id,
            skipped=True,
        )
        retry_caption_result: AuditedSendResult | None = None
        if caption:
            existing_caption = await _find_by_crm_message_id(db, caption_crm_message_id)
            if existing_caption is not None and _is_active(existing_caption):
                retry_caption_result = AuditedSendResult(
                    audit=existing_caption,
                    provider_message_id=existing_caption.provider_message_id,
                    skipped=True,
                )
            else:
                if existing_caption is not None:
                    retry_caption_audit = existing_caption
                    retry_caption_audit.conversation_id = conversation_id
                    retry_caption_audit.chat_id = chat_id
                    retry_caption_audit.outbound_chat_id = _outbound_chat_id(
                        provider, chat_id
                    )
                    retry_caption_audit.message_type = "caption"
                    retry_caption_audit.content = caption
                    retry_caption_audit.caption = caption
                    retry_caption_audit.source = source
                    retry_caption_audit.provider_message_id = None
                    retry_caption_audit.error_details = None
                    retry_caption_audit.details = None
                    retry_caption_audit.status = "pending"
                    retry_caption_audit.status_updated_at = _now()
                else:
                    retry_caption_audit = OutboundMessageAudit(
                        provider=_PROVIDER,
                        conversation_id=conversation_id,
                        chat_id=chat_id,
                        outbound_chat_id=_outbound_chat_id(provider, chat_id),
                        message_type="caption",
                        content=caption,
                        caption=caption,
                        source=source,
                        crm_message_id=caption_crm_message_id,
                        status="pending",
                        status_updated_at=_now(),
                    )
                    db.add(retry_caption_audit)

                await db.flush()
                try:
                    caption_message_id = await provider.send_text(
                        chat_id,
                        caption,
                        crm_message_id=caption_crm_message_id,
                    )
                except httpx.HTTPStatusError as exc:
                    retry_caption_audit.status = (
                        "provider_duplicate"
                        if _is_repeated_crm_message_id(exc)
                        else "error"
                    )
                    retry_caption_audit.status_updated_at = _now()
                    retry_caption_audit.error_details = _http_error_details(exc)
                    await _flush_and_commit_failed_attempt(db)
                    raise
                except Exception as exc:
                    retry_caption_audit.status = "error"
                    retry_caption_audit.status_updated_at = _now()
                    retry_caption_audit.error_details = {
                        "error": type(exc).__name__,
                        "description": str(exc),
                    }
                    await _flush_and_commit_failed_attempt(db)
                    raise

                normalized_caption_message_id = _provider_message_id(caption_message_id)
                retry_caption_audit.provider_message_id = normalized_caption_message_id
                retry_caption_audit.status = (
                    "sent" if normalized_caption_message_id else "error"
                )
                retry_caption_audit.status_updated_at = _now()
                if not normalized_caption_message_id:
                    retry_caption_audit.error_details = {
                        "error": "caption_send_failed",
                        "description": "Provider returned no caption message id.",
                    }
                retry_caption_result = AuditedSendResult(
                    audit=retry_caption_audit,
                    provider_message_id=normalized_caption_message_id,
                )
                await db.flush()

        return AuditedMediaSendResult(
            media=media_result,
            caption=retry_caption_result,
        )

    if existing is not None:
        media_audit = existing
        media_audit.conversation_id = conversation_id
        media_audit.chat_id = chat_id
        media_audit.outbound_chat_id = _outbound_chat_id(provider, chat_id)
        media_audit.message_type = "media"
        media_audit.content_uri = url
        media_audit.file_name = file_name
        media_audit.content_type = content_type
        media_audit.file_size = len(content) if content is not None else None
        media_audit.source = source
        media_audit.provider_message_id = None
        media_audit.error_details = None
        media_audit.details = None
        media_audit.status = "pending"
        media_audit.status_updated_at = _now()
    else:
        media_audit = OutboundMessageAudit(
            provider=_PROVIDER,
            conversation_id=conversation_id,
            chat_id=chat_id,
            outbound_chat_id=_outbound_chat_id(provider, chat_id),
            message_type="media",
            content_uri=url,
            file_name=file_name,
            content_type=content_type,
            file_size=len(content) if content is not None else None,
            source=source,
            crm_message_id=crm_message_id,
            status="pending",
            status_updated_at=_now(),
        )
        db.add(media_audit)

    caption_audit: OutboundMessageAudit | None = None
    if caption:
        existing_caption = await _find_by_crm_message_id(db, caption_crm_message_id)
        if existing_caption is not None:
            caption_audit = existing_caption
            caption_audit.conversation_id = conversation_id
            caption_audit.chat_id = chat_id
            caption_audit.outbound_chat_id = _outbound_chat_id(provider, chat_id)
            caption_audit.message_type = "caption"
            caption_audit.content = caption
            caption_audit.caption = caption
            caption_audit.source = source
            caption_audit.provider_message_id = None
            caption_audit.error_details = None
            caption_audit.details = None
            caption_audit.status = "pending"
            caption_audit.status_updated_at = _now()
        else:
            caption_audit = OutboundMessageAudit(
                provider=_PROVIDER,
                conversation_id=conversation_id,
                chat_id=chat_id,
                outbound_chat_id=_outbound_chat_id(provider, chat_id),
                message_type="caption",
                content=caption,
                caption=caption,
                source=source,
                crm_message_id=caption_crm_message_id,
                status="pending",
                status_updated_at=_now(),
            )
            db.add(caption_audit)

    await db.flush()

    try:
        if _has_real_media_detailed(provider):
            provider_result = await provider.send_media_detailed(
                chat_id=chat_id,
                url=url,
                caption=caption,
                content=content,
                content_type=content_type,
                crm_message_id=crm_message_id,
                caption_crm_message_id=caption_crm_message_id,
            )
            media_message_id = provider_result.message_id
            caption_message_id = provider_result.caption_message_id
            content_uri = provider_result.content_uri
            outbound_chat_id = provider_result.outbound_chat_id
        else:
            media_message_id = await provider.send_media(
                chat_id=chat_id,
                url=url,
                caption=caption,
                content=content,
                content_type=content_type,
                crm_message_id=crm_message_id,
                caption_crm_message_id=caption_crm_message_id,
            )
            caption_message_id = None
            content_uri = url
            outbound_chat_id = media_audit.outbound_chat_id
    except httpx.HTTPStatusError as exc:
        media_audit.status = (
            "provider_duplicate" if _is_repeated_crm_message_id(exc) else "error"
        )
        media_audit.status_updated_at = _now()
        media_audit.error_details = _http_error_details(exc)
        if caption_audit:
            caption_audit.status = "error"
            caption_audit.status_updated_at = media_audit.status_updated_at
            caption_audit.error_details = {
                "error": "media_send_failed",
                "description": "Caption was not attempted because media send failed.",
            }
        await _flush_and_commit_failed_attempt(db)
        raise
    except Exception as exc:
        media_audit.status = "error"
        media_audit.status_updated_at = _now()
        media_audit.error_details = {
            "error": type(exc).__name__,
            "description": str(exc),
        }
        if caption_audit:
            caption_audit.status = "error"
            caption_audit.status_updated_at = media_audit.status_updated_at
            caption_audit.error_details = {
                "error": "media_send_failed",
                "description": "Caption was not attempted because media send failed.",
            }
        await _flush_and_commit_failed_attempt(db)
        raise

    normalized_media_message_id = _provider_message_id(media_message_id)
    media_audit.provider_message_id = normalized_media_message_id
    media_audit.content_uri = content_uri
    media_audit.outbound_chat_id = outbound_chat_id
    media_audit.status = "sent"
    media_audit.status_updated_at = _now()
    media_result = AuditedSendResult(
        audit=media_audit,
        provider_message_id=normalized_media_message_id,
    )

    caption_result: AuditedSendResult | None = None
    if caption_audit:
        normalized_caption_message_id = _provider_message_id(caption_message_id)
        caption_audit.provider_message_id = normalized_caption_message_id
        caption_audit.status = "sent" if normalized_caption_message_id else "error"
        caption_audit.status_updated_at = _now()
        if not normalized_caption_message_id:
            caption_audit.error_details = {
                "error": "caption_send_failed",
                "description": "Provider returned no caption message id.",
            }
        caption_result = AuditedSendResult(
            audit=caption_audit,
            provider_message_id=normalized_caption_message_id,
        )

    await db.flush()
    return AuditedMediaSendResult(media=media_result, caption=caption_result)


async def update_wazzup_statuses(
    db: AsyncSession,
    statuses: list[dict[str, Any]],
) -> int:
    updated = 0
    for status_payload in statuses:
        provider_message_id = status_payload.get("messageId")
        if not isinstance(provider_message_id, str) or not provider_message_id:
            continue

        result = await db.execute(
            select(OutboundMessageAudit).where(
                OutboundMessageAudit.provider == _PROVIDER,
                OutboundMessageAudit.provider_message_id == provider_message_id,
            )
        )
        audit = result.scalar_one_or_none()
        if not isinstance(audit, OutboundMessageAudit):
            continue

        status = status_payload.get("status")
        if isinstance(status, str) and status:
            audit.status = status
        audit.status_updated_at = _parse_status_timestamp(
            status_payload.get("timestamp")
        )
        error = status_payload.get("error")
        audit.error_details = error if isinstance(error, dict) else None
        audit.details = dict(status_payload)
        updated += 1

    if updated:
        await db.flush()
    return updated
