"""Owner-facing customer identity enrichment and formatting helpers."""

from __future__ import annotations

import logging
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
