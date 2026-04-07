from __future__ import annotations

from src.schemas.common import EscalationStatus

_ACTIVE_HUMAN_HANDOFF_STATUSES = {
    EscalationStatus.PENDING.value,
    EscalationStatus.IN_PROGRESS.value,
}

_BOT_PAUSED_STATUSES = {
    *_ACTIVE_HUMAN_HANDOFF_STATUSES,
    EscalationStatus.MANUAL_TAKEOVER.value,
}

_FOLLOWUP_ALLOWED_STATUSES = {
    EscalationStatus.NONE.value,
    EscalationStatus.RESOLVED.value,
    None,
}


def is_active_human_handoff(status: str | None) -> bool:
    """Return True when a conversation is actively waiting on a human."""
    return status in _ACTIVE_HUMAN_HANDOFF_STATUSES


def should_pause_bot_for_escalation(status: str | None) -> bool:
    """Return True when the bot must stay silent for the current conversation."""
    return status in _BOT_PAUSED_STATUSES


def should_send_escalation_fallback(status: str | None) -> bool:
    """Return True when the client should receive the escalation fallback reply."""
    return status in _ACTIVE_HUMAN_HANDOFF_STATUSES


def allows_automatic_followup(status: str | None) -> bool:
    """Return True when automatic follow-ups are allowed for the conversation."""
    return status in _FOLLOWUP_ALLOWED_STATUSES
