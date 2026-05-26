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
from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.llm.safety import (
    PATH_QUALITY_FINAL,
    PATH_QUALITY_MANAGER,
    PATH_QUALITY_RED_FLAGS,
)
from src.models.conversation import Conversation
from src.models.escalation import Escalation
from src.models.feedback import Feedback
from src.models.llm_attempt import LLMAttempt
from src.models.message import Message
from src.models.quality_review import QualityReview
from src.services.report_localization import translate_report_trigger

logger = logging.getLogger(__name__)


def _normalize_report_boundary(value: datetime) -> datetime:
    """Normalize report filters for timestamp-without-time-zone DB columns."""
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


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
    refusal_count: int = 0
    refusal_rate: float = 0.0
    avg_quality_score: float = 0.0
    escalation_count: int = 0
    escalation_reasons: dict[str, int] = {}
    top_products: list[dict[str, Any]] = []
    # Manager performance
    avg_manager_score: float = 0.0
    avg_manager_response_time_seconds: float = 0.0
    manager_deal_conversion_rate: float = 0.0
    manager_reviews_count: int = 0
    top_managers: list[dict[str, Any]] = []
    # Post-delivery feedback
    feedback_count: int = 0
    avg_feedback_rating: float = 0.0
    avg_delivery_rating: float = 0.0
    feedback_recommend_rate: float = 0.0
    feedback_nps_score: float = 0.0
    # Cost-control visibility
    llm_cost_usd: float = 0.0
    qa_llm_cost_usd: float = 0.0
    qa_llm_attempts_count: int = 0
    qa_budget_blocked_count: int = 0
    qa_prompt_tokens: int = 0
    qa_completion_tokens: int = 0
    qa_reasoning_tokens: int = 0
    qa_cached_tokens: int = 0
    qa_cache_write_tokens: int = 0


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

    start_date = _normalize_report_boundary(start_date)
    end_date = _normalize_report_boundary(end_date)
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
        (total_deals / total_conversations * 100) if total_conversations > 0 else 0.0
    )

    assistant_activity_sq = (
        select(Message.conversation_id)
        .where(Message.role == "assistant")
        .where(Message.created_at >= start_date)
        .where(Message.created_at <= end_date)
        .group_by(Message.conversation_id)
        .subquery()
    )

    # Quality score
    qr_q = select(func.avg(QualityReview.total_score)).where(
        QualityReview.conversation_id.in_(
            select(assistant_activity_sq.c.conversation_id)
        )
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

    # Top products — count SKU mentions in assistant messages.
    # Use CTEs to pre-filter active SKUs and date-range messages,
    # then LIKE-match only on the smaller filtered sets.
    top_products: list[dict[str, Any]] = []
    try:
        top_prod_sql = text("""
            WITH active_skus AS (
                SELECT id, name_en, sku
                FROM products
                WHERE is_active = true AND sku IS NOT NULL
            ),
            filtered_msgs AS (
                SELECT content
                FROM messages
                WHERE role = 'assistant'
                  AND created_at >= :start_date
                  AND created_at <= :end_date
            )
            SELECT s.name_en, s.sku, COUNT(*) as mention_count
            FROM active_skus s
            CROSS JOIN filtered_msgs m
            WHERE m.content LIKE '%' || s.sku || '%'
            GROUP BY s.name_en, s.sku
            HAVING COUNT(*) > 0
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

    # Manager performance metrics
    avg_manager_score = 0.0
    avg_manager_response_time_seconds = 0.0
    manager_deal_conversion_rate = 0.0
    manager_reviews_count = 0
    top_managers: list[dict[str, Any]] = []
    try:
        from src.models.manager_review import ManagerReview

        mgr_q = select(
            func.avg(ManagerReview.total_score),
            func.avg(ManagerReview.first_response_time_seconds),
            func.count(ManagerReview.id),
            func.count().filter(ManagerReview.deal_converted.is_(True)),
        ).where(
            ManagerReview.created_at >= start_date,
            ManagerReview.created_at <= end_date,
        )
        mgr_result = await db.execute(mgr_q)
        mgr_row = mgr_result.one()
        avg_manager_score = round(float(mgr_row[0] or 0.0), 1)
        avg_manager_response_time_seconds = round(float(mgr_row[1] or 0.0), 0)
        manager_reviews_count = mgr_row[2] or 0
        mgr_deals = mgr_row[3] or 0
        manager_deal_conversion_rate = (
            round(mgr_deals / manager_reviews_count * 100, 1)
            if manager_reviews_count > 0
            else 0.0
        )

        # Top managers
        top_mgr_q = (
            select(
                ManagerReview.manager_name,
                func.avg(ManagerReview.total_score),
            )
            .where(
                ManagerReview.created_at >= start_date,
                ManagerReview.created_at <= end_date,
                ManagerReview.manager_name.isnot(None),
            )
            .group_by(ManagerReview.manager_name)
            .order_by(func.avg(ManagerReview.total_score).desc())
            .limit(5)
        )
        top_mgr_result = await db.execute(top_mgr_q)
        top_managers = [
            {"name": row[0], "avg_score": round(float(row[1]), 1)}
            for row in top_mgr_result.all()
        ]
    except Exception:
        logger.exception("Failed to query manager metrics for report")

    # Refusal / lost-dialogue proxy.
    refusal_count = 0
    refusal_rate = 0.0
    try:
        refusal_q = select(func.count(Conversation.id)).where(
            Conversation.created_at >= start_date,
            Conversation.created_at <= end_date,
            or_(
                Conversation.deal_status == "cancelled",
                (
                    (Conversation.status == "closed")
                    & (Conversation.zoho_deal_id.is_(None))
                ),
            ),
        )
        refusal_count = int(await db.scalar(refusal_q) or 0)
        refusal_rate = (
            round(refusal_count / total_conversations * 100, 1)
            if total_conversations > 0
            else 0.0
        )
    except Exception:
        logger.exception("Failed to query refusal metrics for report")

    # Post-delivery feedback metrics
    feedback_count = 0
    avg_feedback_rating = 0.0
    avg_delivery_rating = 0.0
    feedback_recommend_rate = 0.0
    feedback_nps_score = 0.0
    try:
        feedback_q = select(
            func.count(Feedback.id),
            func.avg(Feedback.rating_overall),
            func.avg(Feedback.rating_delivery),
            func.count().filter(Feedback.recommend.is_(True)),
            func.count().filter(Feedback.recommend.is_(False)),
        ).where(
            Feedback.created_at >= start_date,
            Feedback.created_at <= end_date,
        )
        feedback_result = await db.execute(feedback_q)
        feedback_row = feedback_result.one()
        feedback_count = int(feedback_row[0] or 0)
        avg_feedback_rating = round(float(feedback_row[1] or 0.0), 1)
        avg_delivery_rating = round(float(feedback_row[2] or 0.0), 1)
        promoters = int(feedback_row[3] or 0)
        detractors = int(feedback_row[4] or 0)
        if feedback_count > 0:
            feedback_recommend_rate = round(promoters / feedback_count * 100, 1)
            feedback_nps_score = round(
                (promoters - detractors) / feedback_count * 100,
                1,
            )
    except Exception:
        logger.exception("Failed to query feedback metrics for report")

    # Cost controls: customer-chat message cost plus QA attempt usage/cost/cache.
    llm_cost_usd = 0.0
    try:
        llm_cost_q = select(func.sum(Message.cost)).where(
            Message.created_at >= start_date,
            Message.created_at <= end_date,
        )
        llm_cost_usd = round(float(await db.scalar(llm_cost_q) or 0.0), 4)
    except Exception:
        logger.exception("Failed to query message LLM cost for report")

    qa_llm_cost_usd = 0.0
    qa_llm_attempts_count = 0
    qa_budget_blocked_count = 0
    qa_prompt_tokens = 0
    qa_completion_tokens = 0
    qa_reasoning_tokens = 0
    qa_cached_tokens = 0
    qa_cache_write_tokens = 0
    try:
        qa_paths = (
            PATH_QUALITY_FINAL,
            PATH_QUALITY_MANAGER,
            PATH_QUALITY_RED_FLAGS,
        )
        qa_usage_q = select(
            func.count(LLMAttempt.id),
            func.sum(LLMAttempt.cost_usd),
            func.sum(LLMAttempt.prompt_tokens),
            func.sum(LLMAttempt.completion_tokens),
            func.sum(LLMAttempt.reasoning_tokens),
            func.sum(LLMAttempt.cached_tokens),
            func.sum(LLMAttempt.cache_write_tokens),
            func.count().filter(LLMAttempt.status == "budget_blocked"),
        ).where(
            LLMAttempt.created_at >= start_date,
            LLMAttempt.created_at <= end_date,
            LLMAttempt.path.in_(qa_paths),
        )
        qa_result = await db.execute(qa_usage_q)
        qa_row = qa_result.one()
        qa_llm_attempts_count = int(qa_row[0] or 0)
        qa_llm_cost_usd = round(float(qa_row[1] or 0.0), 4)
        qa_prompt_tokens = int(qa_row[2] or 0)
        qa_completion_tokens = int(qa_row[3] or 0)
        qa_reasoning_tokens = int(qa_row[4] or 0)
        qa_cached_tokens = int(qa_row[5] or 0)
        qa_cache_write_tokens = int(qa_row[6] or 0)
        qa_budget_blocked_count = int(qa_row[7] or 0)
    except Exception:
        logger.exception("Failed to query QA LLM usage for report")

    return ReportData(
        period_start=start_date,
        period_end=end_date,
        total_conversations=total_conversations,
        conversations_per_day=round(total_conversations / days_in_period, 1),
        unique_customers=unique_customers,
        total_deals=total_deals,
        conversion_rate=round(conversion_rate, 2),
        avg_deal_value=round(avg_deal_value, 2),
        refusal_count=refusal_count,
        refusal_rate=refusal_rate,
        avg_quality_score=round(avg_quality_score, 1),
        escalation_count=escalation_count,
        escalation_reasons=escalation_reasons,
        top_products=top_products,
        avg_manager_score=avg_manager_score,
        avg_manager_response_time_seconds=avg_manager_response_time_seconds,
        manager_deal_conversion_rate=manager_deal_conversion_rate,
        manager_reviews_count=manager_reviews_count,
        top_managers=top_managers,
        feedback_count=feedback_count,
        avg_feedback_rating=avg_feedback_rating,
        avg_delivery_rating=avg_delivery_rating,
        feedback_recommend_rate=feedback_recommend_rate,
        feedback_nps_score=feedback_nps_score,
        llm_cost_usd=llm_cost_usd,
        qa_llm_cost_usd=qa_llm_cost_usd,
        qa_llm_attempts_count=qa_llm_attempts_count,
        qa_budget_blocked_count=qa_budget_blocked_count,
        qa_prompt_tokens=qa_prompt_tokens,
        qa_completion_tokens=qa_completion_tokens,
        qa_reasoning_tokens=qa_reasoning_tokens,
        qa_cached_tokens=qa_cached_tokens,
        qa_cache_write_tokens=qa_cache_write_tokens,
    )


def format_report_text(data: ReportData) -> str:
    """Format report as HTML text for Telegram."""
    lines = [
        "📈 <b>Недельный отчёт</b>",
        f"<i>{data.period_start.strftime('%Y-%m-%d')} — {data.period_end.strftime('%Y-%m-%d')}</i>",
        "",
        f"<b>Диалоги:</b> {data.total_conversations} ({data.conversations_per_day} в день)",
        f"<b>Уникальные клиенты:</b> {data.unique_customers}",
        f"<b>Сделки:</b> {data.total_deals}",
        f"<b>Конверсия:</b> {data.conversion_rate}%",
        f"<b>Отказы:</b> {data.refusal_count} ({data.refusal_rate}%)",
        f"<b>Средний чек:</b> {data.avg_deal_value} AED",
        f"<b>Средняя оценка качества:</b> {data.avg_quality_score}/30",
        f"<b>Эскалации:</b> {data.escalation_count}",
    ]

    if data.escalation_reasons:
        lines.append("")
        lines.append("<b>Основные причины эскалации:</b>")
        for reason, count in list(data.escalation_reasons.items())[:5]:
            lines.append(
                f"  • {translate_report_trigger(reason, surface='weekly_report', module='reports')}: {count}"
            )

    if data.top_products:
        lines.append("")
        lines.append("<b>Топ товаров:</b>")
        for prod in data.top_products[:5]:
            lines.append(
                f"  • {prod['name']} ({prod['sku']}): {prod['mentions']} упоминаний"
            )

    if data.manager_reviews_count > 0:
        lines.append("")
        lines.append("📊 <b>Показатели менеджеров</b>")
        # Convert seconds to minutes for display
        response_time_min = round(data.avg_manager_response_time_seconds / 60, 1)
        lines.append(f"  Средний балл: {data.avg_manager_score}/20")
        lines.append(f"  Среднее время ответа: {response_time_min} мин")
        lines.append(f"  Конверсия в сделку: {data.manager_deal_conversion_rate}%")
        lines.append(f"  Оценок: {data.manager_reviews_count}")
        if data.top_managers:
            top_names = ", ".join(
                f"{m['name']} ({m['avg_score']})" for m in data.top_managers[:3]
            )
            lines.append(f"  Лучшие: {top_names}")

    lines.append("")
    lines.append("🧾 <b>Обратная связь</b>")
    lines.append(f"  Отзывов: {data.feedback_count}")
    lines.append(f"  Средняя оценка: {data.avg_feedback_rating}/5")
    lines.append(f"  Доставка: {data.avg_delivery_rating}/5")
    lines.append(f"  Готовы рекомендовать: {data.feedback_recommend_rate}%")
    lines.append(f"  NPS-подобный показатель: {data.feedback_nps_score}%")

    lines.append("")
    lines.append("💸 <b>Контроль LLM расходов</b>")
    lines.append(f"  Чат: ${data.llm_cost_usd:.4f}")
    lines.append(
        f"  QA: ${data.qa_llm_cost_usd:.4f} ({data.qa_llm_attempts_count} попыток)"
    )
    lines.append(f"  Бюджетных блокировок QA: {data.qa_budget_blocked_count}")
    lines.append(
        "  QA usage: "
        f"prompt {data.qa_prompt_tokens}, "
        f"completion {data.qa_completion_tokens}, "
        f"reasoning {data.qa_reasoning_tokens}"
    )
    lines.append(
        "  QA cache tokens: "
        f"cached {data.qa_cached_tokens}, "
        f"write {data.qa_cache_write_tokens}"
    )

    return "\n".join(lines)


async def run_weekly_report(ctx: dict[str, Any]) -> None:
    """ARQ job: Generate and send weekly report via Telegram."""
    from src.core.database import async_session_factory
    from src.services.notifications import send_telegram_message

    now = datetime.now(tz=UTC)
    start_date = now - timedelta(days=7)

    async with async_session_factory() as db:
        report = await generate_report(db, start_date=start_date, end_date=now)

    report_text = format_report_text(report)
    await send_telegram_message(report_text)
    logger.info("Weekly report sent to Telegram")
