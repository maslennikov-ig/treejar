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


def allowed_inbound_channel_phones() -> frozenset[str]:
    """Every inbound line whose conversations may raise a manager alert.

    `tj-zyxz`. This was one phone, and in production it was the hardcoded
    default in `src/core/config.py`: no `telegram_allowed_inbound_phone` in the
    runtime environment and no `telegram_test_mode_enabled` row in the database.
    It worked only because Treejar runs a single WhatsApp line. Adding a second
    would have stopped its manager alerts with nothing to show for it, so the
    setting now accepts a comma-separated list and adding a line is a
    configuration change rather than a code change.
    """
    return frozenset(
        phone
        for phone in (
            normalize_channel_phone(candidate)
            for candidate in str(settings.telegram_allowed_inbound_phone).split(",")
        )
        if phone
    )


def should_send_telegram_alert_for_conversation(conversation: Any) -> bool:
    """Strict gating, for the routine quality and review alerts.

    A conversation the runtime cannot attribute to a configured line does not
    generate one of these, which is a deliberate existing decision: they are
    periodic and their cost of being wrong is noise, not a missed customer.
    """
    allowed = allowed_inbound_channel_phones()
    if not allowed:
        return False

    return get_conversation_inbound_channel_phone(conversation) in allowed


def should_send_manager_alert_for_conversation(conversation: Any) -> bool:
    """Gating for an escalation, which fails open.

    The two alert families are not symmetric, so they no longer share a rule. A
    spurious manager alert costs the internal Telegram group one message. A
    dropped one costs a customer who asked for a human and never got one, and
    it leaves no trace — 11 of the 84 escalations on production at 2026-08-06
    carried no channel metadata and would have been dropped by the strict rule.

    So an unattributable conversation, and an allowlist that is empty and
    therefore matches nothing, both alert.
    """
    allowed = allowed_inbound_channel_phones()
    if not allowed:
        return True

    inbound_phone = get_conversation_inbound_channel_phone(conversation)
    return inbound_phone is None or inbound_phone in allowed


async def _test_mode_restricts(db: Any) -> bool:
    raw_enabled = await get_system_config(db, "telegram_test_mode_enabled", "true")
    return str(raw_enabled).lower() != "false"


async def should_send_telegram_alert_for_conversation_with_db(
    conversation: Any,
    db: Any,
) -> bool:
    """Apply admin-configurable test mode before evaluating inbound gating."""
    if not await _test_mode_restricts(db):
        return True

    return should_send_telegram_alert_for_conversation(conversation)


async def should_send_manager_alert_for_conversation_with_db(
    conversation: Any,
    db: Any,
) -> bool:
    """The escalation variant of the same switch."""
    if not await _test_mode_restricts(db):
        return True

    return should_send_manager_alert_for_conversation(conversation)
