from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

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


class EscalationValidity(StrEnum):
    """Whether a pending row agrees with the current conversation state."""

    VALID = "valid"
    STALE = "stale"
    AMBIGUOUS = "ambiguous"


class EscalationAction(StrEnum):
    """Conservative reconciliation action for a pending escalation row."""

    REVIEW = "human_review"
    RESOLVE = "resolve_pending_row"


class EscalationRecordSource(StrEnum):
    """Privacy-safe origin classification derived from repository phone tags."""

    REAL = "real"
    SYNTHETIC = "synthetic"
    REAL_ARCHIVED = "real_archived"
    TAGGED_UNKNOWN = "tagged_unknown"


@dataclass(frozen=True)
class PendingEscalationClassification:
    escalation_id: uuid.UUID
    conversation_id: uuid.UUID
    source: EscalationRecordSource
    validity: EscalationValidity
    action: EscalationAction
    reason: str
    age_days: int
    conversation_status: str
    conversation_escalation_status: str
    escalation_status: str


def classify_record_source(phone: str) -> EscalationRecordSource:
    """Classify repository-owned synthetic tags without exposing the phone."""
    _, separator, suffix = phone.partition("#")
    if not separator:
        return EscalationRecordSource.REAL

    normalized = suffix.casefold()
    if normalized.startswith("archived-"):
        return EscalationRecordSource.REAL_ARCHIVED
    if normalized.startswith(("smoke", "test", "tj-")):
        return EscalationRecordSource.SYNTHETIC
    return EscalationRecordSource.TAGGED_UNKNOWN


def _normalized_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def classify_pending_escalation(
    *,
    escalation_id: uuid.UUID,
    conversation_id: uuid.UUID,
    phone: str,
    conversation_status: str,
    conversation_escalation_status: str,
    escalation_status: str,
    escalation_created_at: datetime,
    now: datetime,
    stale_after_days: int,
) -> PendingEscalationClassification:
    """Classify one row from current persisted state using conservative rules."""
    if stale_after_days < 1:
        raise ValueError("stale_after_days must be positive")

    age_seconds = (
        _normalized_utc(now) - _normalized_utc(escalation_created_at)
    ).total_seconds()
    age_days = max(0, int(age_seconds // 86400))
    is_stale = age_days >= stale_after_days

    validity = EscalationValidity.AMBIGUOUS
    action = EscalationAction.REVIEW
    reason = "state_combination_requires_human_review"

    if escalation_status != EscalationStatus.PENDING.value:
        reason = "row_is_not_pending"
    elif (
        conversation_status == "closed"
        and conversation_escalation_status == EscalationStatus.RESOLVED.value
    ):
        validity = EscalationValidity.STALE
        action = EscalationAction.RESOLVE
        reason = "closed_conversation_is_already_resolved"
    elif (
        conversation_status == "active"
        and conversation_escalation_status == EscalationStatus.NONE.value
    ):
        if is_stale:
            validity = EscalationValidity.STALE
            action = EscalationAction.RESOLVE
            reason = "stale_row_disagrees_with_active_unpaused_conversation"
        else:
            reason = "recent_row_disagrees_with_active_unpaused_conversation"
    elif (
        conversation_status == "active"
        and conversation_escalation_status == EscalationStatus.PENDING.value
    ):
        validity = EscalationValidity.VALID
        reason = "conversation_is_waiting_for_manager"
    elif conversation_status == "active" and conversation_escalation_status in {
        EscalationStatus.IN_PROGRESS.value,
        EscalationStatus.MANUAL_TAKEOVER.value,
    }:
        validity = EscalationValidity.VALID
        reason = "conversation_has_active_human_ownership"

    return PendingEscalationClassification(
        escalation_id=escalation_id,
        conversation_id=conversation_id,
        source=classify_record_source(phone),
        validity=validity,
        action=action,
        reason=reason,
        age_days=age_days,
        conversation_status=conversation_status,
        conversation_escalation_status=conversation_escalation_status,
        escalation_status=escalation_status,
    )


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
