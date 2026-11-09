from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.shadow_webhook_event import ShadowWebhookEvent

_SHADOW_STATUS_PRECEDENCE = {
    "inbound": 0,
    "pending": 0,
    "sent": 1,
    "delivered": 2,
    "read": 3,
    "edited": 4,
}


def _clean_str(value: object, *, max_len: int | None = None) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if not stripped:
        return None
    if max_len is not None and len(stripped) > max_len:
        return stripped[:max_len]
    return stripped


def _extract_content_uri(item: dict[str, Any]) -> str | None:
    direct = _clean_str(item.get("contentUri"))
    if direct is not None:
        return direct
    media = item.get("media")
    if isinstance(media, dict):
        return _clean_str(media.get("url") or media.get("contentUri"))
    return None


def _extract_provider_timestamp(item: dict[str, Any]) -> str | None:
    raw_dt = item.get("dateTime")
    if isinstance(raw_dt, str) and raw_dt.strip():
        return raw_dt.strip()[:128]
    raw_ts = item.get("timestamp")
    if isinstance(raw_ts, (int, float)) and not isinstance(raw_ts, bool):
        return str(raw_ts)[:128]
    if isinstance(raw_ts, str) and raw_ts.strip():
        return raw_ts.strip()[:128]
    return None


def _should_advance_shadow_status(current: str | None, candidate: str | None) -> bool:
    if candidate is None or candidate == current:
        return False
    if current is None:
        return True
    if candidate == "error":
        return current != "error"
    if current == "error":
        return False
    return _SHADOW_STATUS_PRECEDENCE.get(candidate, -1) > _SHADOW_STATUS_PRECEDENCE.get(
        current, -1
    )


def _merge_shadow_row(existing: ShadowWebhookEvent, item: dict[str, Any]) -> bool:
    changed = False
    candidate_status = _clean_str(item.get("status"), max_len=64)
    if _should_advance_shadow_status(existing.status, candidate_status):
        existing.status = candidate_status
        changed = True

    if existing.text is None:
        text_val = item.get("text")
        if isinstance(text_val, str) and text_val.strip():
            existing.text = text_val
            changed = True

    if existing.content_uri is None:
        uri = _extract_content_uri(item)
        if uri is not None:
            existing.content_uri = uri
            changed = True

    if existing.author_name is None:
        author_name = _clean_str(item.get("authorName"), max_len=255)
        if author_name is not None:
            existing.author_name = author_name
            changed = True

    if candidate_status == "error" and isinstance(item.get("error"), dict):
        merged_raw = dict(existing.raw_message)
        merged_raw["error"] = item["error"]
        merged_raw["status"] = "error"
        existing.raw_message = merged_raw
        changed = True

    return changed


async def persist_shadow_webhook_payload(
    db: AsyncSession,
    raw_body: dict[str, Any],
    *,
    source_ip: str,
) -> int:
    """Persist passive observe-only Wazzup webhook items without side effects.

    Deduplicates by ``messageId`` while preserving original ``created_at`` so
    exact first-seen response latency can be measured even when Wazzup later
    emits ``delivered``/``read``/``error`` status updates for the same message.
    """
    raw_messages = raw_body.get("messages")
    raw_statuses = raw_body.get("statuses")

    message_items: dict[str, dict[str, Any]] = {}
    if isinstance(raw_messages, list):
        for item in raw_messages:
            if not isinstance(item, dict):
                continue
            message_id = _clean_str(item.get("messageId"), max_len=255)
            chat_id = _clean_str(item.get("chatId"), max_len=255)
            if message_id is None or chat_id is None:
                continue
            prev = message_items.get(message_id)
            if prev is None:
                message_items[message_id] = item
            else:
                # Merge fuller/newer fields within the same batch
                merged = dict(prev)
                merged.update({k: v for k, v in item.items() if v is not None})
                message_items[message_id] = merged

    status_items: dict[str, dict[str, Any]] = {}
    if isinstance(raw_statuses, list):
        for st in raw_statuses:
            if not isinstance(st, dict):
                continue
            message_id = _clean_str(st.get("messageId"), max_len=255)
            status_val = _clean_str(st.get("status"), max_len=64)
            if message_id is None or status_val is None:
                continue
            status_items[message_id] = st

    lookup_ids = set(message_items) | set(status_items)
    if not lookup_ids:
        return 0

    existing_stmt = select(ShadowWebhookEvent).where(
        ShadowWebhookEvent.message_id.in_(lookup_ids)
    )
    existing_result = await db.execute(existing_stmt)
    existing_by_id: dict[str, ShadowWebhookEvent] = {
        row.message_id: row for row in existing_result.scalars().all()
    }

    stored_or_updated = 0
    clean_ip = _clean_str(source_ip, max_len=64) or "unknown"

    for message_id, item in message_items.items():
        existing = existing_by_id.get(message_id)
        if existing is not None:
            if _merge_shadow_row(existing, item):
                stored_or_updated += 1
            continue

        chat_id = _clean_str(item.get("chatId"), max_len=255)
        if chat_id is None:
            continue
        text_raw = item.get("text")
        text_val = text_raw if isinstance(text_raw, str) and text_raw.strip() else None
        row = ShadowWebhookEvent(
            message_id=message_id,
            source_ip=clean_ip,
            channel_id=_clean_str(item.get("channelId"), max_len=255),
            chat_id=chat_id,
            chat_type=_clean_str(item.get("chatType"), max_len=64),
            is_echo=bool(item.get("isEcho") is True),
            status=_clean_str(item.get("status"), max_len=64),
            author_type=_clean_str(item.get("authorType"), max_len=64),
            author_name=_clean_str(item.get("authorName"), max_len=255),
            message_type=_clean_str(item.get("type"), max_len=64),
            text=text_val,
            content_uri=_extract_content_uri(item),
            provider_timestamp=_extract_provider_timestamp(item),
            raw_message=item,
        )
        try:
            async with db.begin_nested():
                db.add(row)
                await db.flush()
            existing_by_id[message_id] = row
            stored_or_updated += 1
        except IntegrityError:
            refreshed = (
                await db.execute(
                    select(ShadowWebhookEvent).where(
                        ShadowWebhookEvent.message_id == message_id
                    )
                )
            ).scalar_one_or_none()
            if refreshed is not None and _merge_shadow_row(refreshed, item):
                stored_or_updated += 1

    for message_id, st in status_items.items():
        existing = existing_by_id.get(message_id)
        if existing is not None and _merge_shadow_row(existing, st):
            stored_or_updated += 1

    return stored_or_updated
