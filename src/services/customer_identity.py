"""Owner-facing customer identity enrichment and formatting helpers."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from html import escape
from typing import Any
from zoneinfo import ZoneInfo

from src.core.cache import get_cached_crm_profile, set_cached_crm_profile
from src.services.inbound_channels import normalize_channel_phone

_DUBAI_TZ = ZoneInfo("Asia/Dubai")
_UNKNOWN_TEXT = "не указано"
_UNKNOWN_PHONE = "не указан"
_GENERIC_CUSTOMER_PLACEHOLDERS = frozenset(
    {
        "valued customer",
        "unknown client",
    }
)
_ATTRIBUTION_METADATA_KEY = "source_attribution"
_UTM_KEYS = frozenset(
    {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "utm_id",
    }
)
_SOURCE_KEYS = ("source", "lead_source", "referrer", "referral_source")
_CHANNEL_KEYS = ("channel", "chatType", "chat_type")
_RECENT_STATUS_KEYS = (
    "Recent_Status",
    "Last_Deal_Status",
    "Last_Order_Status",
    "Deal_Status",
    "Latest_Status",
    "Stage",
)
_MAX_CONTEXT_VALUE_CHARS = 96
_MAX_LLM_CONTEXT_LINES = 4

logger = logging.getLogger(__name__)


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _is_generic_customer_placeholder(value: str | None) -> bool:
    cleaned = _clean_text(value)
    if not cleaned:
        return False
    return cleaned.casefold() in _GENERIC_CUSTOMER_PLACEHOLDERS


def _extract_name_from_profile(profile: dict[str, Any] | None) -> str | None:
    if not profile:
        return None

    for key in ("Name", "Full_Name", "Full Name", "full_name"):
        raw = profile.get(key)
        cleaned = _clean_text(raw) if isinstance(raw, str) else None
        if cleaned:
            return cleaned

    first_name = (
        _clean_text(profile.get("First_Name"))
        if isinstance(profile.get("First_Name"), str)
        else None
    )
    last_name = (
        _clean_text(profile.get("Last_Name"))
        if isinstance(profile.get("Last_Name"), str)
        else None
    )
    full_name = " ".join(part for part in (first_name, last_name) if part)
    return full_name or None


def _coerce_compact_text(
    value: Any, *, max_chars: int = _MAX_CONTEXT_VALUE_CHARS
) -> str:
    if isinstance(value, (list, tuple, set)):
        text = ", ".join(str(item).strip() for item in value if str(item).strip())
    elif isinstance(value, Mapping):
        name = value.get("name")
        text = str(name).strip() if name is not None else ""
    else:
        text = str(value).strip() if value is not None else ""

    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def _first_text_value(payload: Mapping[str, Any], keys: Sequence[str]) -> str | None:
    for key in keys:
        value = payload.get(key)
        text = _clean_text(value) if isinstance(value, str) else None
        if text:
            return text
    return None


def _build_cached_profile(contact: dict[str, Any]) -> dict[str, Any]:
    name = " ".join(
        part
        for part in (
            _clean_text(contact.get("First_Name"))
            if isinstance(contact.get("First_Name"), str)
            else None,
            _clean_text(contact.get("Last_Name"))
            if isinstance(contact.get("Last_Name"), str)
            else None,
        )
        if part
    )
    if not name:
        name = _extract_name_from_profile(contact) or ""

    return {
        "Name": name,
        "Segment": contact.get("Segment", "Unknown"),
    }


def _payload_from_message(message: Any) -> dict[str, Any]:
    if isinstance(message, Mapping):
        return dict(message)
    if hasattr(message, "model_dump"):
        payload = dict(message.model_dump())
        extra = getattr(message, "model_extra", None)
        if isinstance(extra, Mapping):
            payload.update(extra)
        return payload
    return {}


def extract_inbound_source_attribution(
    messages: Sequence[Any],
) -> dict[str, Any] | None:
    """Extract safe source/UTM attribution from inbound message payloads."""
    source: str | None = None
    channel: str | None = None
    utm: dict[str, str] = {}

    for message in messages:
        payload = _payload_from_message(message)
        if not payload:
            continue

        source = source or _first_text_value(payload, _SOURCE_KEYS)
        channel = channel or _first_text_value(payload, _CHANNEL_KEYS)

        nested_utm = payload.get("utm")
        if isinstance(nested_utm, Mapping):
            for key, value in nested_utm.items():
                if key in _UTM_KEYS and isinstance(value, str) and value.strip():
                    utm[key] = value.strip()

        for key in _UTM_KEYS:
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                utm[key] = value.strip()

    if not source and not channel and not utm:
        return None

    attribution: dict[str, Any] = {}
    if source:
        attribution["source"] = source
    if channel:
        attribution["channel"] = channel
    if utm:
        attribution["utm"] = utm
    return attribution


def apply_source_attribution_metadata(
    conversation: Any,
    attribution: Mapping[str, Any] | None,
) -> None:
    """Persist original/latest inbound attribution in conversation metadata."""
    if not attribution:
        return

    cleaned: dict[str, Any] = {}
    source = attribution.get("source")
    channel = attribution.get("channel")
    if isinstance(source, str) and source.strip():
        cleaned["source"] = source.strip()
    if isinstance(channel, str) and channel.strip():
        cleaned["channel"] = channel.strip()

    raw_utm = attribution.get("utm")
    if isinstance(raw_utm, Mapping):
        utm = {
            str(key): str(value).strip()
            for key, value in raw_utm.items()
            if key in _UTM_KEYS and value is not None and str(value).strip()
        }
        if utm:
            cleaned["utm"] = utm

    if not cleaned:
        return

    metadata = dict(getattr(conversation, "metadata_", None) or {})
    existing = metadata.get(_ATTRIBUTION_METADATA_KEY)
    attribution_meta = dict(existing) if isinstance(existing, Mapping) else {}

    if not isinstance(attribution_meta.get("original"), Mapping):
        attribution_meta["original"] = cleaned
    attribution_meta["latest"] = cleaned
    attribution_meta["policy"] = {
        "original_preserved": True,
        "latest_updates_on_repeat_contact": True,
        "zoho_outbound_mapping": "client_decision_required",
    }

    metadata[_ATTRIBUTION_METADATA_KEY] = attribution_meta
    conversation.metadata_ = metadata


def build_bounded_returning_customer_context(
    contact: Mapping[str, Any] | None,
) -> dict[str, str]:
    """Build compact CRM context safe for owner/admin/LLM prompts."""
    if not contact:
        return {"Segment": "Unknown", "Returning_Customer": "no"}

    context: dict[str, str] = {"Returning_Customer": "yes"}
    name = _extract_name_from_profile(dict(contact))
    if name:
        context["Name"] = _coerce_compact_text(name)

    segment = _coerce_compact_text(contact.get("Segment", "Unknown"))
    context["Segment"] = segment or "Unknown"

    for key in _RECENT_STATUS_KEYS:
        status = _coerce_compact_text(contact.get(key))
        if status:
            context["Recent_Status"] = status
            break

    return context


def format_llm_crm_context(context: Mapping[str, Any]) -> str:
    """Format only allow-listed, bounded CRM context lines for the LLM prompt."""
    allowed_keys = ("Name", "Segment", "Recent_Status", "Returning_Customer")
    lines: list[str] = []
    for key in allowed_keys:
        value = context.get(key)
        text = _coerce_compact_text(value)
        if text:
            lines.append(f"{key}: {text}")
        if len(lines) >= _MAX_LLM_CONTEXT_LINES:
            break
    return "\n".join(lines)


async def resolve_owner_customer_name(
    *,
    phone: str | None,
    conversation_customer_name: str | None,
    redis: Any,
    crm_client: Any | None,
) -> str:
    """Resolve a display-ready customer name for owner-facing notifications."""
    direct_name = _clean_text(conversation_customer_name)
    if direct_name and not _is_generic_customer_placeholder(direct_name):
        return direct_name

    if redis is not None and phone:
        try:
            cached_profile = await get_cached_crm_profile(redis, phone)
        except Exception:
            logger.warning(
                "Failed to read CRM profile cache for owner-facing identity phone=%s",
                phone,
                exc_info=True,
            )
        else:
            cached_name = _extract_name_from_profile(cached_profile)
            if cached_name:
                return cached_name

    if crm_client is not None and phone:
        try:
            contact = await crm_client.find_contact_by_phone(phone)
        except Exception:
            logger.warning(
                "Failed to enrich owner-facing identity from CRM phone=%s",
                phone,
                exc_info=True,
            )
        else:
            if contact:
                cached_profile = _build_cached_profile(contact)
                if redis is not None:
                    try:
                        await set_cached_crm_profile(redis, phone, cached_profile)
                    except Exception:
                        logger.warning(
                            "Failed to update CRM profile cache for owner-facing identity phone=%s",
                            phone,
                            exc_info=True,
                        )
                cached_name = _extract_name_from_profile(cached_profile)
                if cached_name:
                    return cached_name

    return _UNKNOWN_TEXT


def _format_datetime_uae(value: datetime | None) -> str:
    if value is None:
        return _UNKNOWN_TEXT

    value = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)

    return value.astimezone(_DUBAI_TZ).strftime("%d.%m.%Y %H:%M")


def format_owner_identity_block(
    *,
    phone: str | None,
    customer_name: str | None,
    inbound_channel_phone: str | None,
    conversation_created_at: datetime | None,
    last_activity_at: datetime | None,
) -> str:
    """Render a stable owner-facing identity block for quality notifications."""
    phone_display = _clean_text(phone) or _UNKNOWN_PHONE
    customer_name_display = _clean_text(customer_name) or _UNKNOWN_TEXT
    inbound_display = normalize_channel_phone(inbound_channel_phone) or _UNKNOWN_PHONE

    return "\n".join(
        [
            f"<b>Телефон клиента:</b> {escape(phone_display)}",
            f"<b>Имя клиента:</b> {escape(customer_name_display)}",
            f"<b>Входящий номер:</b> {escape(inbound_display)}",
            f"<b>Начат (UAE):</b> {escape(_format_datetime_uae(conversation_created_at))}",
            f"<b>Последняя активность (UAE):</b> {escape(_format_datetime_uae(last_activity_at))}",
        ]
    )
