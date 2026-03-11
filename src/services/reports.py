"""Report generation service.

Generates structured weekly reports with key business metrics:
- Conversations per day, conversion rate
- Rejection/escalation reasons
- Average deal value, quality score
- Top requested products

Outputs both text (for Telegram) and JSON (for API).
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.conversation import Conversation
from src.models.escalation import Escalation
from src.models.quality_review import QualityReview

logger = logging.getLogger(__name__)


class ReportData(BaseModel):
    """Structured report data."""

    period_start: datetime
    period_end: datetime
    total_conversations: int = 0
    conversations_per_day: float = 0.0
    unique_customers: int = 0
    total_deals: int = 0
    conversion_rate: float = 0.0
    avg_deal_value: float = 0.0
    avg_quality_score: float = 0.0
    escalation_count: int = 0
    escalation_reasons: dict[str, int] = {}
    top_products: list[dict[str, Any]] = []


async def generate_report(
    db: AsyncSession,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> ReportData:
    """Generate a report for the specified period.

    Defaults to the last 7 days if no dates are provided.
    """
    now = datetime.now(tz=UTC)
    if end_date is None:
        end_date = now
    if start_date is None:
        start_date = now - timedelta(days=7)

    days_in_period = max((end_date - start_date).days, 1)

    # Conversations count and unique customers
    conv_q = select(
        func.count(Conversation.id),
        func.count(func.distinct(Conversation.phone)),
    ).where(
        Conversation.created_at >= start_date,
        Conversation.created_at <= end_date,
    )
    conv_result = await db.execute(conv_q)
    conv_row = conv_result.one()
    total_conversations = conv_row[0] or 0
    unique_customers = conv_row[1] or 0

    # Deals (conversations with zoho_deal_id)
    deals_q = select(
        func.count(Conversation.id),
        func.avg(Conversation.deal_amount),
    ).where(
        Conversation.created_at >= start_date,
        Conversation.created_at <= end_date,
        Conversation.zoho_deal_id.isnot(None),
    )
    deals_result = await db.execute(deals_q)
    deals_row = deals_result.one()
    total_deals = deals_row[0] or 0
    avg_deal_value = float(deals_row[1] or 0.0)

    conversion_rate = (
        (total_deals / total_conversations * 100)
        if total_conversations > 0
        else 0.0
    )

    # Quality score
    qr_q = select(func.avg(QualityReview.total_score)).where(
        QualityReview.created_at >= start_date,
        QualityReview.created_at <= end_date,
    )
    avg_quality_score = float(await db.scalar(qr_q) or 0.0)

    # Escalations
    esc_count_q = select(func.count(Escalation.id)).where(
        Escalation.created_at >= start_date,
        Escalation.created_at <= end_date,
    )
    escalation_count = await db.scalar(esc_count_q) or 0

    esc_reasons_q = (
        select(Escalation.reason, func.count(Escalation.id))
        .where(
            Escalation.created_at >= start_date,
            Escalation.created_at <= end_date,
        )
        .group_by(Escalation.reason)
        .order_by(func.count(Escalation.id).desc())
        .limit(10)
    )
    esc_rows = await db.execute(esc_reasons_q)
    escalation_reasons = {row[0]: row[1] for row in esc_rows.all()}

    # Top products (from assistant messages mentioning SKUs)
    top_products: list[dict[str, Any]] = []
    try:
        top_prod_sql = text("""
            SELECT p.name_en, p.sku, COUNT(*) as mention_count
            FROM messages m
            JOIN products p ON m.content LIKE '%' || p.sku || '%'
            WHERE m.role = 'assistant'
              AND m.created_at >= :start_date
              AND m.created_at <= :end_date
            GROUP BY p.name_en, p.sku
            ORDER BY mention_count DESC
            LIMIT 5
        """)
        prod_result = await db.execute(
            top_prod_sql,
            {"start_date": start_date, "end_date": end_date},
        )
        top_products = [
            {"name": row[0], "sku": row[1], "mentions": row[2]}
            for row in prod_result.all()
        ]
    except Exception:
        logger.exception("Failed to query top products for report")

    return ReportData(
        period_start=start_date,
        period_end=end_date,
        total_conversations=total_conversations,
        conversations_per_day=round(total_conversations / days_in_period, 1),
        unique_customers=unique_customers,
        total_deals=total_deals,
        conversion_rate=round(conversion_rate, 2),
        avg_deal_value=round(avg_deal_value, 2),
        avg_quality_score=round(avg_quality_score, 1),
        escalation_count=escalation_count,
        escalation_reasons=escalation_reasons,
        top_products=top_products,
    )


def format_report_text(data: ReportData) -> str:
    """Format report as HTML text for Telegram."""
    lines = [
        "📈 <b>Weekly Report</b>",
        f"<i>{data.period_start.strftime('%Y-%m-%d')} — {data.period_end.strftime('%Y-%m-%d')}</i>",
        "",
        f"<b>Conversations:</b> {data.total_conversations} ({data.conversations_per_day}/day)",
        f"<b>Unique Customers:</b> {data.unique_customers}",
        f"<b>Deals:</b> {data.total_deals}",
        f"<b>Conversion:</b> {data.conversion_rate}%",
        f"<b>Avg Deal Value:</b> {data.avg_deal_value} AED",
        f"<b>Avg Quality:</b> {data.avg_quality_score}/30",
        f"<b>Escalations:</b> {data.escalation_count}",
    ]

    if data.escalation_reasons:
        lines.append("")
        lines.append("<b>Top Escalation Reasons:</b>")
        for reason, count in list(data.escalation_reasons.items())[:5]:
            lines.append(f"  • {reason}: {count}")

    if data.top_products:
        lines.append("")
        lines.append("<b>Top Products:</b>")
        for prod in data.top_products[:5]:
            lines.append(f"  • {prod['name']} ({prod['sku']}): {prod['mentions']} mentions")

    return "\n".join(lines)


async def run_weekly_report(ctx: dict[str, Any]) -> None:
    """ARQ job: Generate and send weekly report via Telegram."""
    from src.core.database import async_session_factory
    from src.services.notifications import _get_telegram_client

    now = datetime.now(tz=UTC)
    start_date = now - timedelta(days=7)

    async with async_session_factory() as db:
        report = await generate_report(db, start_date=start_date, end_date=now)

    report_text = format_report_text(report)

    client = _get_telegram_client()
    await client.send_message(report_text)
    logger.info("Weekly report sent to Telegram")
