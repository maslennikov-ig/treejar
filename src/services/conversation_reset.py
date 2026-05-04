from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.conversation import Conversation
from src.models.escalation import Escalation
from src.models.message import Message
from src.schemas.common import EscalationStatus, SalesStage


@dataclass(frozen=True)
class ResetPreview:
    phone: str
    phone_variants: tuple[str, ...]
    conversation_count: int
    latest_conversation_id: uuid.UUID | None
    message_count: int
    pending_escalation_count: int


@dataclass(frozen=True)
class ResetResult:
    phone: str
    archived_count: int
    new_conversation: Conversation | None


def normalize_reset_phone(value: str | None) -> str | None:
    """Normalize Telegram-entered phone values to +<digits> for reset matching."""
    if not value:
        return None

    digits = "".join(ch for ch in value if ch.isdigit())
    if len(digits) < 7:
        return None

    return f"+{digits}"


def phone_reset_variants(value: str | None) -> tuple[str, ...]:
    normalized = normalize_reset_phone(value)
    if normalized is None:
        return ()

    digits = normalized[1:]
    return (normalized, digits)


async def _fetch_reset_conversations(
    db: AsyncSession,
    phone: str,
) -> list[Conversation]:
    variants = phone_reset_variants(phone)
    if not variants:
        return []

    result = await db.execute(
        select(Conversation)
        .where(Conversation.phone.in_(variants))
        .order_by(Conversation.updated_at.desc(), Conversation.created_at.desc())
    )
    return list(result.scalars().all())


async def build_reset_preview(db: AsyncSession, phone: str) -> ResetPreview:
    normalized = normalize_reset_phone(phone)
    variants = phone_reset_variants(phone)
    if normalized is None or not variants:
        return ResetPreview(
            phone="",
            phone_variants=(),
            conversation_count=0,
            latest_conversation_id=None,
            message_count=0,
            pending_escalation_count=0,
        )

    conversations = await _fetch_reset_conversations(db, normalized)
    if not conversations:
        return ResetPreview(
            phone=normalized,
            phone_variants=variants,
            conversation_count=0,
            latest_conversation_id=None,
            message_count=0,
            pending_escalation_count=0,
        )

    conversation_ids = [conversation.id for conversation in conversations]
    message_count_result = await db.execute(
        select(func.count(Message.id)).where(
            Message.conversation_id.in_(conversation_ids)
        )
    )
    pending_count_result = await db.execute(
        select(func.count(Escalation.id)).where(
            Escalation.conversation_id.in_(conversation_ids),
            Escalation.status.in_(
                (
                    EscalationStatus.PENDING.value,
                    EscalationStatus.IN_PROGRESS.value,
                )
            ),
        )
    )

    return ResetPreview(
        phone=normalized,
        phone_variants=variants,
        conversation_count=len(conversations),
        latest_conversation_id=conversations[0].id,
        message_count=int(message_count_result.scalar_one()),
        pending_escalation_count=int(pending_count_result.scalar_one()),
    )


async def execute_conversation_reset(
    db: AsyncSession,
    phone: str,
    *,
    requested_by_telegram_user_id: int,
) -> ResetResult:
    normalized = normalize_reset_phone(phone)
    if normalized is None:
        return ResetResult(phone="", archived_count=0, new_conversation=None)

    conversations = await _fetch_reset_conversations(db, normalized)
    if not conversations:
        return ResetResult(phone=normalized, archived_count=0, new_conversation=None)

    reset_at = datetime.now(UTC)
    reset_at_text = reset_at.isoformat()
    archive_suffix = reset_at.strftime("%Y%m%d%H%M%S")
    replacement_phone = conversations[0].phone
    archived_ids = [str(conversation.id) for conversation in conversations]

    for conversation in conversations:
        original_phone = conversation.phone
        short_id = str(conversation.id).split("-", 1)[0]
        conversation.phone = f"{original_phone}#archived-{archive_suffix}-{short_id}"
        conversation.status = "closed"
        conversation.escalation_status = EscalationStatus.RESOLVED.value
        metadata = dict(conversation.metadata_ or {})
        metadata.update(
            {
                "reset_source": "telegram",
                "reset_at": reset_at_text,
                "reset_by_telegram_user_id": requested_by_telegram_user_id,
                "original_phone": original_phone,
                "reset_replacement_phone": replacement_phone,
            }
        )
        conversation.metadata_ = metadata

    escalation_result = await db.execute(
        select(Escalation).where(
            Escalation.conversation_id.in_(
                [conversation.id for conversation in conversations]
            ),
            Escalation.status.in_(
                (
                    EscalationStatus.PENDING.value,
                    EscalationStatus.IN_PROGRESS.value,
                )
            ),
        )
    )
    for escalation in escalation_result.scalars().all():
        escalation.status = EscalationStatus.RESOLVED.value

    new_conversation = Conversation(
        id=uuid.uuid4(),
        phone=replacement_phone,
        language="en",
        sales_stage=SalesStage.GREETING.value,
        status="active",
        escalation_status=EscalationStatus.NONE.value,
        customer_name=None,
        zoho_contact_id=None,
        zoho_deal_id=None,
        metadata_={
            "reset_source": "telegram",
            "reset_at": reset_at_text,
            "reset_by_telegram_user_id": requested_by_telegram_user_id,
            "reset_from_conversation_ids": archived_ids,
            "archived_conversation_count": len(conversations),
        },
    )
    db.add(new_conversation)

    return ResetResult(
        phone=normalized,
        archived_count=len(conversations),
        new_conversation=new_conversation,
    )
