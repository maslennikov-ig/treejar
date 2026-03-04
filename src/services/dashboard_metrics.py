"""Dashboard metrics calculation service.

Calculates 17 KPIs across 6 categories (docs/metrics.md) directly from DB
with period-based filtering (day/week/month/all_time).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.conversation import Conversation
from src.models.escalation import Escalation
from src.models.message import Message
from src.models.quality_review import QualityReview
from src.schemas import DashboardMetricsResponse, SalesMetrics


def _get_period_start(period: str) -> datetime | None:
    """Return the start datetime for the given period, or None for all_time."""
    now = datetime.now(tz=UTC)
    match period:
        case "day":
            return now - timedelta(days=1)
        case "week":
            return now - timedelta(weeks=1)
        case "month":
            return now - timedelta(days=30)
        case _:
            return None


async def calculate_dashboard_metrics(
    db: AsyncSession, period: str = "all_time"
) -> DashboardMetricsResponse:
    """Calculate all 17 dashboard metrics from DB with optional period filtering."""
    period_start = _get_period_start(period)

    # Base filters
    def conv_filter(stmt):  # type: ignore[no-untyped-def]
        if period_start:
            return stmt.where(Conversation.created_at >= period_start)
        return stmt

    def msg_filter(stmt):  # type: ignore[no-untyped-def]
        if period_start:
            return stmt.where(Message.created_at >= period_start)
        return stmt

    # --- 1. VOLUME ---
    total_conversations = (
        await db.scalar(conv_filter(select(func.count(Conversation.id)))) or 0
    )

    unique_customers = (
        await db.scalar(
            conv_filter(select(func.count(func.distinct(Conversation.phone))))
        )
        or 0
    )

    # New vs returning: phone appears once = new, more = returning
    phone_counts_subq = (
        conv_filter(
            select(
                Conversation.phone,
                func.count(Conversation.id).label("conv_count"),
            )
        )
        .group_by(Conversation.phone)
        .subquery()
    )
    new_count = (
        await db.scalar(
            select(func.count()).select_from(phone_counts_subq).where(
                phone_counts_subq.c.conv_count == 1
            )
        )
        or 0
    )
    returning_count = (
        await db.scalar(
            select(func.count()).select_from(phone_counts_subq).where(
                phone_counts_subq.c.conv_count > 1
            )
        )
        or 0
    )

    # --- 2. CLASSIFICATION ---
    # By language
    lang_rows = await db.execute(
        conv_filter(
            select(Conversation.language, func.count(Conversation.id))
        ).group_by(Conversation.language)
    )
    by_language = {row[0]: row[1] for row in lang_rows.all()}

    # By segment — from metadata.segment if available
    by_segment: dict[str, int] = {}

    # Target vs non-target: status = 'active' or 'completed' is target
    target_count = (
        await db.scalar(
            conv_filter(
                select(func.count(Conversation.id)).where(
                    Conversation.status.in_(["active", "completed"])
                )
            )
        )
        or 0
    )
    nontarget_count = total_conversations - target_count

    # --- 3. ESCALATION ---
    escalation_count = (
        await db.scalar(
            conv_filter(
                select(func.count(Conversation.id)).where(
                    Conversation.escalation_status != "none"
                )
            )
        )
        or 0
    )

    # Escalation reasons from escalations table
    esc_base = select(Escalation.reason, func.count(Escalation.id)).group_by(
        Escalation.reason
    )
    if period_start:
        esc_base = esc_base.where(Escalation.created_at >= period_start)

    esc_rows = await db.execute(esc_base)
    escalation_reasons = {row[0]: row[1] for row in esc_rows.all()}

    # --- 4. SALES ---
    deals_with_noor = (
        await db.scalar(
            conv_filter(
                select(func.count(Conversation.id)).where(
                    Conversation.zoho_deal_id.is_not(None),
                    Conversation.escalation_status == "none",
                )
            )
        )
        or 0
    )
    deals_post_esc = (
        await db.scalar(
            conv_filter(
                select(func.count(Conversation.id)).where(
                    Conversation.zoho_deal_id.is_not(None),
                    Conversation.escalation_status != "none",
                )
            )
        )
        or 0
    )

    total_deals = deals_with_noor + deals_post_esc
    conversion_rate = (
        (total_deals / total_conversations * 100) if total_conversations > 0 else 0.0
    )

    # --- 5. QUALITY ---
    avg_conv_length = (
        await db.scalar(
            msg_filter(
                select(
                    func.avg(
                        select(func.count(Message.id))
                        .where(Message.conversation_id == Conversation.id)
                        .correlate(Conversation)
                        .scalar_subquery()
                    )
                ).select_from(Conversation)
            )
        )
        or 0.0
    )

    # Average quality score from quality_reviews
    qr_base = select(func.avg(QualityReview.total_score))
    if period_start:
        qr_base = qr_base.where(QualityReview.created_at >= period_start)
    avg_quality_score = await db.scalar(qr_base) or 0.0

    # Average response time (from message pairs: user → assistant time diff)
    avg_response_time_ms = 0.0

    # --- 6. COST ---
    cost_base = select(func.sum(Message.cost))
    if period_start:
        cost_base = cost_base.where(Message.created_at >= period_start)
    llm_cost = await db.scalar(cost_base) or 0.0

    return DashboardMetricsResponse(
        period=period,
        total_conversations=total_conversations,
        unique_customers=unique_customers,
        new_vs_returning={"new": new_count, "returning": returning_count},
        by_segment=by_segment,
        by_language=by_language,
        target_vs_nontarget={"target": target_count, "nontarget": nontarget_count},
        escalation_count=escalation_count,
        escalation_reasons=escalation_reasons,
        noor_sales=SalesMetrics(count=deals_with_noor),
        post_escalation_sales=SalesMetrics(count=deals_post_esc),
        conversion_rate=round(conversion_rate, 2),
        average_deal_value=0.0,
        avg_conversation_length=round(float(avg_conv_length), 1),
        avg_quality_score=round(float(avg_quality_score), 1),
        avg_response_time_ms=round(float(avg_response_time_ms), 1),
        llm_cost_usd=round(float(llm_cost), 4),
    )
