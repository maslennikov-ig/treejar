from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.conversation import Conversation
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


async def resolve_conversation_pending_escalations(
    db: AsyncSession,
    conversation_id: uuid.UUID,
) -> int:
    """Resolve a conversation and only its still-pending escalation rows."""
    stmt = (
        select(Conversation)
        .options(selectinload(Conversation.escalations))
        .where(Conversation.id == conversation_id)
    )
    result = await db.execute(stmt)
    conversation = result.scalar_one_or_none()
    if conversation is None:
        return 0

    conversation.escalation_status = EscalationStatus.RESOLVED.value

    resolved_rows = 0
    for escalation in conversation.escalations:
        if escalation.status == EscalationStatus.PENDING.value:
            escalation.status = EscalationStatus.RESOLVED.value
            resolved_rows += 1

    return resolved_rows
