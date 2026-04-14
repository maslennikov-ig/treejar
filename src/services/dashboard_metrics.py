"""Dashboard metrics calculation service.

Calculates the current admin dashboard payload from docs/metrics.md directly
from DB with period-based filtering (day/week/month/all_time).

Performance: Uses 3 consolidated SQL queries instead of 12+ sequential ones.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.conversation import Conversation
from src.models.escalation import Escalation
from src.models.feedback import Feedback
from src.models.message import Message
from src.models.quality_review import QualityReview
from src.schemas import (
    DashboardMetricsResponse,
    SalesMetrics,
    TimeseriesPoint,
    TimeseriesResponse,
)


def _get_period_days(period: str) -> int:
    """Return number of days for the given period."""
    match period:
        case "day":
            return 1
        case "week":
            return 7
        case "month":
            return 30
        case _:
            return 90  # all_time defaults to last 90 days for timeseries


def _get_period_start(period: str) -> datetime | None:
    """Return the start datetime for the given period, or None for all_time."""
    now = datetime.now(UTC).replace(tzinfo=None)
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
    """Calculate the admin dashboard payload with optional period filtering.

    Optimized: 3 SQL queries instead of 12+ sequential ones.
      1. Batch conversation-level metrics (volume, classification, escalation, sales)
      2. Batch message-level metrics (quality, cost, manager, feedback)
      3. Avg response time (LATERAL JOIN, requires its own query)
    """
    period_start = _get_period_start(period)
    period_clause = ""
    params: dict[str, Any] = {}

    if period_start:
        period_clause = "AND c.created_at >= :period_start"
        params["period_start"] = period_start

    # ── QUERY 1: All conversation-level metrics in one shot ──
    conv_sql = text(f"""
        SELECT
            -- Volume
            COUNT(*)                                              AS total_conversations,
            COUNT(DISTINCT c.phone)                               AS unique_customers,

            -- Classification
            COUNT(*) FILTER (WHERE c.status IN ('active','completed'))  AS target_count,

            -- Escalation
            COUNT(*) FILTER (WHERE c.escalation_status != 'none')      AS escalation_count,

            -- Sales
            COUNT(*) FILTER (WHERE c.zoho_deal_id IS NOT NULL
                             AND c.escalation_status = 'none')         AS noor_sales_count,
            COUNT(*) FILTER (WHERE c.zoho_deal_id IS NOT NULL
                             AND c.escalation_status != 'none')        AS post_esc_sales_count,

            -- Deal value
            AVG(c.deal_amount) FILTER (WHERE c.deal_amount IS NOT NULL) AS avg_deal_value
        FROM conversations c
        WHERE 1=1 {period_clause}
    """)
    conv_row = (await db.execute(conv_sql, params)).one()

    total_conversations = conv_row.total_conversations or 0
    unique_customers = conv_row.unique_customers or 0
    target_count = conv_row.target_count or 0
    nontarget_count = total_conversations - target_count
    escalation_count = conv_row.escalation_count or 0
    noor_sales_count = conv_row.noor_sales_count or 0
    post_esc_sales_count = conv_row.post_esc_sales_count or 0
    avg_deal_value = float(conv_row.avg_deal_value or 0.0)

    total_deals = noor_sales_count + post_esc_sales_count
    conversion_rate = (
        (total_deals / total_conversations * 100) if total_conversations > 0 else 0.0
    )

    # New vs returning (phone appears once = new, more = returning)
    phone_counts_subq = select(
        Conversation.phone,
        func.count(Conversation.id).label("conv_count"),
    )
    if period_start:
        phone_counts_subq = phone_counts_subq.where(
            Conversation.created_at >= period_start
        )
    phone_counts_sq = phone_counts_subq.group_by(Conversation.phone).subquery()

    new_count = (
        await db.scalar(
            select(func.count())
            .select_from(phone_counts_sq)
            .where(phone_counts_sq.c.conv_count == 1)
        )
        or 0
    )
    returning_count = (
        await db.scalar(
            select(func.count())
            .select_from(phone_counts_sq)
            .where(phone_counts_sq.c.conv_count > 1)
        )
        or 0
    )

    # By language (small aggregation, separate query)
    lang_q = select(Conversation.language, func.count(Conversation.id)).group_by(
        Conversation.language
    )
    if period_start:
        lang_q = lang_q.where(Conversation.created_at >= period_start)
    lang_rows = await db.execute(lang_q)
    by_language = {row[0]: row[1] for row in lang_rows.all()}

    # By segment from metadata JSON
    seg_q = select(
        func.coalesce(Conversation.metadata_["segment"].as_string(), "unknown"),
        func.count(Conversation.id),
    ).group_by(text("1"))
    if period_start:
        seg_q = seg_q.where(Conversation.created_at >= period_start)
    seg_rows = await db.execute(seg_q)
    by_segment = {row[0]: row[1] for row in seg_rows.all()}

    # Escalation reasons
    esc_q = select(Escalation.reason, func.count(Escalation.id)).group_by(
        Escalation.reason
    )
    if period_start:
        esc_q = esc_q.where(Escalation.created_at >= period_start)
    esc_rows = await db.execute(esc_q)
    escalation_reasons = {row[0]: row[1] for row in esc_rows.all()}

    # ── QUERY 2: Message-level metrics ──
    cost_q = select(func.sum(Message.cost))
    if period_start:
        cost_q = cost_q.where(Message.created_at >= period_start)
    llm_cost = await db.scalar(cost_q) or 0.0

    msg_per_conv = select(
        Message.conversation_id,
        func.count(Message.id).label("msg_count"),
    ).group_by(Message.conversation_id)
    if period_start:
        msg_per_conv = msg_per_conv.where(Message.created_at >= period_start)
    msg_sub = msg_per_conv.subquery()
    avg_conv_length = await db.scalar(select(func.avg(msg_sub.c.msg_count))) or 0.0

    # Quality score
    qr_q = select(func.avg(QualityReview.total_score))
    if period_start:
        assistant_activity_sq = (
            select(Message.conversation_id)
            .where(Message.role == "assistant")
            .where(Message.created_at >= period_start)
            .subquery()
        )
        qr_q = qr_q.where(
            QualityReview.conversation_id.in_(
                select(assistant_activity_sq.c.conversation_id)
            )
        )
    avg_quality_score = await db.scalar(qr_q) or 0.0

    # ── QUERY 3: Avg response time (LATERAL JOIN) ──
    rt_sql = """
        SELECT AVG(EXTRACT(EPOCH FROM (bot.created_at - user_msg.created_at)) * 1000)
        FROM messages user_msg
        JOIN LATERAL (
            SELECT created_at FROM messages
            WHERE conversation_id = user_msg.conversation_id
              AND role = 'assistant'
              AND created_at > user_msg.created_at
            ORDER BY created_at LIMIT 1
        ) bot ON true
        WHERE user_msg.role = 'user'
    """
    if period_start:
        rt_sql = rt_sql.rstrip() + " AND user_msg.created_at >= :period_start"
        avg_response_time_ms = (
            await db.scalar(text(rt_sql), {"period_start": period_start})
        ) or 0.0
    else:
        avg_response_time_ms = await db.scalar(text(rt_sql)) or 0.0

    # ── QUERY 4: Manager performance metrics ──
    from src.models.manager_review import ManagerReview
    from src.schemas.manager_review import ManagerLeaderboardEntry

    mgr_q = select(
        func.avg(ManagerReview.total_score),
        func.avg(ManagerReview.first_response_time_seconds),
    )
    mgr_conv_q = select(
        func.count().filter(ManagerReview.deal_converted.is_(True)),
        func.count(),
    ).select_from(ManagerReview)

    if period_start:
        mgr_q = mgr_q.where(ManagerReview.created_at >= period_start)
        mgr_conv_q = mgr_conv_q.where(ManagerReview.created_at >= period_start)

    mgr_result = await db.execute(mgr_q)
    mgr_row = mgr_result.one()
    avg_manager_score = float(mgr_row[0] or 0.0)
    avg_manager_response_time = float(mgr_row[1] or 0.0)

    mgr_conv_result = await db.execute(mgr_conv_q)
    mgr_conv_row = mgr_conv_result.one()
    mgr_deals = mgr_conv_row[0] or 0
    mgr_total = mgr_conv_row[1] or 0
    manager_deal_conversion_rate = (
        round(mgr_deals / mgr_total * 100, 2) if mgr_total > 0 else 0.0
    )

    # Manager leaderboard (top 10)
    lb_q = (
        select(
            ManagerReview.manager_name,
            func.avg(ManagerReview.total_score).label("avg_score"),
            func.count(ManagerReview.id).label("reviews_count"),
        )
        .where(ManagerReview.manager_name.isnot(None))
        .group_by(ManagerReview.manager_name)
        .order_by(func.avg(ManagerReview.total_score).desc())
        .limit(10)
    )
    if period_start:
        lb_q = lb_q.where(ManagerReview.created_at >= period_start)

    lb_result = await db.execute(lb_q)
    manager_leaderboard = [
        ManagerLeaderboardEntry(
            name=row[0],
            avg_score=round(float(row[1]), 1),
            reviews_count=row[2],
        )
        for row in lb_result.all()
    ]

    # ── QUERY 5: Feedback metrics ──
    fb_q = select(
        func.count(Feedback.id),
        func.avg(Feedback.rating_overall),
        func.avg(Feedback.rating_delivery),
        func.count().filter(Feedback.recommend.is_(True)),
        func.count().filter(Feedback.recommend.is_(False)),
    ).select_from(Feedback)

    if period_start:
        fb_q = fb_q.where(Feedback.created_at >= period_start)

    fb_result = await db.execute(fb_q)
    fb_row = fb_result.one()
    feedback_count = fb_row[0] or 0
    avg_rating_overall = float(fb_row[1] or 0.0)
    avg_rating_delivery = float(fb_row[2] or 0.0)
    promoters = fb_row[3] or 0  # recommend=True
    detractors = fb_row[4] or 0  # recommend=False
    nps_score = 0.0
    recommend_rate = 0.0
    if feedback_count > 0:
        nps_score = round((promoters - detractors) / feedback_count * 100, 1)
        recommend_rate = round(promoters / feedback_count * 100, 1)

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
        noor_sales=SalesMetrics(count=noor_sales_count),
        post_escalation_sales=SalesMetrics(count=post_esc_sales_count),
        conversion_rate=round(conversion_rate, 2),
        average_deal_value=round(avg_deal_value, 2),
        avg_conversation_length=round(float(avg_conv_length), 1),
        avg_quality_score=round(float(avg_quality_score), 1),
        avg_response_time_ms=round(float(avg_response_time_ms), 1),
        llm_cost_usd=round(float(llm_cost), 4),
        avg_manager_score=round(avg_manager_score, 1),
        avg_manager_response_time_seconds=round(avg_manager_response_time, 1),
        manager_deal_conversion_rate=manager_deal_conversion_rate,
        manager_leaderboard=manager_leaderboard,
        feedback_count=feedback_count,
        avg_rating_overall=round(avg_rating_overall, 1),
        avg_rating_delivery=round(avg_rating_delivery, 1),
        nps_score=nps_score,
        recommend_rate=recommend_rate,
    )


async def calculate_timeseries(
    db: AsyncSession, period: str = "all_time"
) -> TimeseriesResponse:
    """Calculate daily new vs returning conversation counts for the given period."""
    days = _get_period_days(period)
    period_start = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=days)

    # CTE: first appearance date per phone
    # Then classify each conversation on each day as new (first day) or returning
    sql = text("""
        WITH first_seen AS (
            SELECT phone, MIN(DATE(created_at)) AS first_date
            FROM conversations
            GROUP BY phone
        ),
        daily AS (
            SELECT
                DATE(c.created_at) AS day,
                CASE WHEN DATE(c.created_at) = fs.first_date THEN 'new' ELSE 'returning' END AS ctype
            FROM conversations c
            JOIN first_seen fs ON c.phone = fs.phone
            WHERE c.created_at >= :period_start
        )
        SELECT
            day,
            COUNT(*) FILTER (WHERE ctype = 'new') AS new_count,
            COUNT(*) FILTER (WHERE ctype = 'returning') AS returning_count
        FROM daily
        GROUP BY day
        ORDER BY day
    """)

    result = await db.execute(sql, {"period_start": period_start})
    points = [
        TimeseriesPoint(
            date=row[0].isoformat(),
            new=row[1],
            returning=row[2],
        )
        for row in result.all()
    ]

    return TimeseriesResponse(period=period, points=points)
