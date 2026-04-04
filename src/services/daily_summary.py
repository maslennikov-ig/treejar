"""Daily summary metrics for the Telegram notification."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.conversation import Conversation
from src.models.escalation import Escalation
from src.models.message import Message
from src.models.quality_review import QualityReview
from src.schemas.common import DealStatus


class DailySummaryData(BaseModel):
    """Structured payload for the daily Telegram summary."""

    period_start: datetime
    period_end: datetime
    total_conversations: int = 0
    unique_customers: int = 0
    escalation_count: int = 0
    avg_quality_score: float | None = None
    conversion_rate_7d: float | None = None


def _naive_utc(value: datetime | None) -> datetime:
    """Normalize datetimes to naive UTC to match timestamp-without-time-zone columns."""
    current = value or datetime.now(UTC)
    return current.astimezone(UTC).replace(tzinfo=None)


async def calculate_daily_summary(
    db: AsyncSession,
    now: datetime | None = None,
) -> DailySummaryData:
    """Calculate the daily summary metrics used for Telegram delivery."""
    current = _naive_utc(now)
    period_start = current - timedelta(days=1)
    conversion_start = current - timedelta(days=7)

    conv_q = (
        select(
            func.count(Conversation.id).label("total_conversations"),
            func.count(func.distinct(Conversation.phone)).label("unique_customers"),
        )
        .where(Conversation.created_at >= period_start)
        .where(Conversation.created_at <= current)
    )
    conv_row = (await db.execute(conv_q)).one()

    esc_q = (
        select(func.count(Escalation.id).label("escalation_count"))
        .where(Escalation.created_at >= period_start)
        .where(Escalation.created_at <= current)
    )
    esc_row = (await db.execute(esc_q)).one()

    assistant_activity_24h_sq = (
        select(Message.conversation_id)
        .where(Message.role == "assistant")
        .where(Message.created_at >= period_start)
        .where(Message.created_at <= current)
        .group_by(Message.conversation_id)
        .subquery()
    )

    quality_q = select(
        func.avg(QualityReview.total_score).label("avg_quality_score")
    ).where(
        QualityReview.conversation_id.in_(
            select(assistant_activity_24h_sq.c.conversation_id)
        )
    )
    quality_row = (await db.execute(quality_q)).one()

    delivered_q = (
        select(func.count(Conversation.id).label("delivered_deals"))
        .where(Conversation.deal_status == DealStatus.DELIVERED.value)
        .where(Conversation.deal_delivered_at.is_not(None))
        .where(Conversation.deal_delivered_at >= conversion_start)
        .where(Conversation.deal_delivered_at <= current)
    )
    delivered_row = (await db.execute(delivered_q)).one()

    assistant_activity_7d_sq = (
        select(Message.conversation_id)
        .where(Message.role == "assistant")
        .where(Message.created_at >= conversion_start)
        .where(Message.created_at <= current)
        .group_by(Message.conversation_id)
        .subquery()
    )

    assistant_7d_q = select(func.count().label("assistant_conversations")).select_from(
        assistant_activity_7d_sq
    )
    assistant_row = (await db.execute(assistant_7d_q)).one()

    total_conversations = int(getattr(conv_row, "total_conversations", 0) or 0)
    unique_customers = int(getattr(conv_row, "unique_customers", 0) or 0)
    escalation_count = int(getattr(esc_row, "escalation_count", 0) or 0)

    avg_quality_raw = getattr(quality_row, "avg_quality_score", None)
    avg_quality_score = float(avg_quality_raw) if avg_quality_raw is not None else None

    delivered_deals = int(getattr(delivered_row, "delivered_deals", 0) or 0)
    assistant_conversations = int(
        getattr(assistant_row, "assistant_conversations", 0) or 0
    )
    conversion_rate_7d = (
        round(delivered_deals / assistant_conversations * 100, 2)
        if assistant_conversations > 0
        else None
    )

    return DailySummaryData(
        period_start=period_start,
        period_end=current,
        total_conversations=total_conversations,
        unique_customers=unique_customers,
        escalation_count=escalation_count,
        avg_quality_score=avg_quality_score,
        conversion_rate_7d=conversion_rate_7d,
    )
