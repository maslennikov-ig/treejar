from __future__ import annotations

from typing import Any

from src.core.config import get_system_config, settings


def normalize_channel_phone(value: str | None) -> str | None:
    """Normalize inbound channel phone into +<digits> form."""
    if not value or not isinstance(value, str):
        return None

    digits = "".join(ch for ch in value if ch.isdigit())
    if not digits:
        return None

    return f"+{digits}"


def update_conversation_inbound_channel(
    conversation: Any,
    *,
    channel_id: str | None,
    channel_phone: str | None,
) -> None:
    """Persist inbound channel metadata on a conversation JSON column."""
    if not channel_id:
        return

    metadata = dict(getattr(conversation, "metadata_", None) or {})
    metadata["inbound_channel_id"] = channel_id

    normalized_phone = normalize_channel_phone(channel_phone)
    if normalized_phone:
        metadata["inbound_channel_phone"] = normalized_phone

    conversation.metadata_ = metadata


def get_conversation_inbound_channel_phone(conversation: Any) -> str | None:
    """Return normalized inbound channel phone stored on a conversation."""
    metadata = getattr(conversation, "metadata_", None) or {}
    if not isinstance(metadata, dict):
        return None

    value = metadata.get("inbound_channel_phone")
    return normalize_channel_phone(value) if isinstance(value, str) else None


def should_send_telegram_alert_for_conversation(conversation: Any) -> bool:
    """Allow Telegram alerts only for the configured inbound channel phone."""
    allowed_phone = normalize_channel_phone(settings.telegram_allowed_inbound_phone)
    if not allowed_phone:
        return False

    inbound_phone = get_conversation_inbound_channel_phone(conversation)
    return inbound_phone == allowed_phone


async def should_send_telegram_alert_for_conversation_with_db(
    conversation: Any,
    db: Any,
) -> bool:
    """Apply admin-configurable test mode before evaluating inbound gating."""
    raw_enabled = await get_system_config(db, "telegram_test_mode_enabled", "true")
    if str(raw_enabled).lower() == "false":
        return True

    return should_send_telegram_alert_for_conversation(conversation)
