"""Notification service — orchestrates sending alerts via Telegram.

Provides functions for different notification types:
- Escalation alerts
- Quality alerts (low score)
- Daily summary

All functions are safe to call even when Telegram is not configured.
"""

from __future__ import annotations

import logging
from datetime import datetime
from html import escape
from typing import Any
from uuid import UUID

import logfire

from src.core.config import settings
from src.integrations.notifications.telegram import TelegramClient
from src.quality.schemas import BlockScore, EvaluationResult, RedFlagItem
from src.services.customer_identity import format_owner_identity_block
from src.services.daily_summary import DailySummaryData, calculate_daily_summary
from src.services.owner_presentation import (
    format_quality_rating,
    format_report_trigger,
    format_sales_stage,
    owner_na,
    owner_unknown,
    red_flag_explanation,
    red_flag_title,
)
from src.services.owner_review_formatters import format_detailed_quality_review

logger = logging.getLogger(__name__)
_ESCALATION_CONTEXT_LIMIT = 500
_ESCALATION_CONTEXT_OMISSION = "… Earlier context hidden …"


def _format_escalation_context_tail(context: str) -> str:
    """Return a bounded context snippet that preserves the latest dialogue lines."""
    if len(context) <= _ESCALATION_CONTEXT_LIMIT:
        return context

    prefix = f"{_ESCALATION_CONTEXT_OMISSION}\n"
    budget = max(_ESCALATION_CONTEXT_LIMIT - len(prefix), 0)
    lines = context.splitlines()
    kept_reversed: list[str] = []
    used = 0

    for line in reversed(lines):
        extra = len(line) + (1 if kept_reversed else 0)
        if kept_reversed and used + extra > budget:
            break
        if not kept_reversed and extra > budget:
            kept_reversed.append(line[-budget:] if budget else "")
            break
        kept_reversed.append(line)
        used += extra

    tail = "\n".join(reversed(kept_reversed)).strip()
    return f"{prefix}{tail}" if tail else prefix.rstrip()


def _get_telegram_client() -> TelegramClient:
    """Create a TelegramClient from current settings."""
    return TelegramClient(
        bot_token=settings.telegram_bot_token,
        chat_id=settings.telegram_chat_id,
    )


def _mask_phone(phone: str) -> str:
    """Mask phone number for external channels: +97150***4567."""
    if len(phone) > 6:
        return phone[:6] + "***" + phone[-4:]
    return "***"


def _format_bullets(items: list[str], *, fallback: str) -> str:
    cleaned = [item.strip() for item in items if item and item.strip()]
    values = cleaned or [fallback]
    return "\n".join(f"• {escape(item)}" for item in values)


def _collect_evidence_quotes(result: EvaluationResult, *, limit: int = 4) -> list[str]:
    quotes: list[str] = []
    sorted_criteria = sorted(
        result.criteria,
        key=lambda criterion: (
            criterion.weight_points or 0.0,
            criterion.score,
            criterion.rule_number,
        ),
        reverse=True,
    )
    for criterion in sorted_criteria:
        for quote in criterion.evidence:
            cleaned = quote.strip()
            if cleaned and cleaned not in quotes:
                quotes.append(cleaned)
            if len(quotes) >= limit:
                return quotes
    return quotes


def _format_quality_block_score(block: BlockScore) -> str:
    if block.applicable_rules == 0 or block.normalized_weight <= 0:
        return owner_na()
    denominator = f"{block.normalized_weight:.2f}".rstrip("0").rstrip(".")
    return f"{block.points:.1f}/{denominator}"


# =============================================================================
# Message formatters (pure functions, no side effects)
# =============================================================================


def format_escalation_message(
    phone: str,
    conversation_id: UUID,
    reason: str,
    *,
    context: str | None = None,
) -> str:
    """Format an escalation alert as HTML for Telegram.

    Phone is shown in full so managers can call back or find in CRM.
    Context (if provided) shows recent messages so manager knows what's happening.
    """
    # Format phone with + prefix for tel: link if not already prefixed
    phone_display = phone if phone.startswith("+") else f"+{phone}"
    translated_reason = format_report_trigger(
        reason,
        surface="escalation_alert",
        module="notifications",
    )
    safe_reason = (
        translated_reason.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    msg = (
        "🚨 <b>Escalation</b>\n\n"
        f'📞 <b>Customer phone:</b> <a href="tel:{phone_display}">{phone_display}</a>\n'
        f"<b>Reason:</b> {safe_reason}\n"
        f"<b>Conversation UUID:</b> <code>{conversation_id}</code>\n"
    )

    if context:
        # Preserve the latest actionable lines before escaping for Telegram HTML.
        safe_context = escape(_format_escalation_context_tail(context))
        msg += f"\n<b>Context:</b>\n<i>{safe_context}</i>\n"

    msg += "\nThe manager has been notified and should review this conversation."
    return msg


def format_catalog_mismatch_message(
    *,
    sku: str | None,
    treejar_slug: str,
    product_name: str | None,
    issue: str | None = None,
    detail: str | None = None,
) -> str:
    """Format an operational alert for Treejar-vs-Zoho catalog mismatches."""
    safe_name = (
        escape(product_name.strip())
        if product_name and product_name.strip()
        else "Unknown product"
    )
    safe_sku = escape(sku.strip()) if sku and sku.strip() else "missing"
    safe_slug = escape(treejar_slug.strip())
    detail_block = ""
    if detail and detail.strip():
        detail_block = f"\n<b>Details:</b> {escape(detail.strip())}\n"
    issue_text = (
        escape(issue.strip())
        if issue and issue.strip()
        else (
            "Product exists in Treejar Catalog API but is missing in Zoho. "
            "Do not promise exact price or availability until the mismatch is resolved."
        )
    )

    return (
        "⚠️ <b>Catalog mismatch</b>\n\n"
        f"<b>Product:</b> {safe_name}\n"
        f"<b>SKU:</b> <code>{safe_sku}</code>\n"
        f"<b>Treejar slug:</b> <code>{safe_slug}</code>\n"
        f"<b>Issue:</b> {issue_text}"
        f"{detail_block}"
        "\nThe site/customer team needs to check this."
    )


def format_quality_alert_message(
    conversation_id: UUID,
    score: float,
    rating: str,
    summary: str,
    *,
    criteria: list[Any] | None = None,
    current_stage: str | None = None,
    trigger: str | None = "low_score",
    phone: str | None = None,
    customer_name: str | None = None,
    inbound_channel_phone: str | None = None,
    conversation_created_at: datetime | None = None,
    last_activity_at: datetime | None = None,
) -> str:
    """Format a long quality review for Telegram."""
    return format_detailed_quality_review(
        conversation_id=conversation_id,
        score=score,
        rating=rating,
        criteria=criteria or [],
        current_stage=current_stage,
        trigger=trigger,
        summary=summary,
        phone=phone,
        customer_name=customer_name,
        inbound_channel_phone=inbound_channel_phone,
        conversation_created_at=conversation_created_at,
        last_activity_at=last_activity_at,
    )


def format_red_flag_warning_message(
    *,
    conversation_id: UUID,
    phone: str | None,
    customer_name: str | None,
    inbound_channel_phone: str | None,
    conversation_created_at: datetime | None,
    last_activity_at: datetime | None,
    sales_stage: str,
    flags: list[RedFlagItem],
    recommended_action: str,
) -> str:
    """Format a compact realtime red-flag warning for Telegram."""
    identity_block = format_owner_identity_block(
        phone=phone,
        customer_name=customer_name,
        inbound_channel_phone=inbound_channel_phone,
        conversation_created_at=conversation_created_at,
        last_activity_at=last_activity_at,
    )
    stage_label = format_sales_stage(sales_stage)
    red_flag_lines = "\n".join(
        "• "
        f"<b>{escape(red_flag_title(flag.code, flag.title))}</b>: "
        f"{escape(red_flag_explanation(flag.code, flag.explanation))}"
        for flag in flags
    )
    evidence_quotes: list[str] = []
    for flag in flags:
        for quote in flag.evidence:
            cleaned = quote.strip()
            if cleaned and cleaned not in evidence_quotes:
                evidence_quotes.append(cleaned)
            if len(evidence_quotes) >= 2:
                break
        if len(evidence_quotes) >= 2:
            break
    evidence_block = _format_bullets(
        evidence_quotes,
        fallback="No direct quotes from the conversation were recorded.",
    )
    action_text = escape(
        recommended_action.strip()
        or "Review the conversation urgently and send a corrective message."
    )

    return (
        "🚨 <b>Critical signal</b>\n\n"
        f"<b>Conversation UUID:</b> <code>{conversation_id}</code>\n"
        f"{identity_block}\n"
        f"<b>Current stage:</b> {escape(stage_label)}\n\n"
        f"<b>Critical signals:</b>\n{red_flag_lines}\n\n"
        f"<b>Evidence:</b>\n{evidence_block}\n\n"
        f"<b>Recommended action:</b> {action_text}"
    )


def format_final_quality_review_message(
    *,
    conversation_id: UUID,
    phone: str | None,
    customer_name: str | None,
    inbound_channel_phone: str | None,
    conversation_created_at: datetime | None,
    last_activity_at: datetime | None,
    sales_stage: str,
    trigger: str,
    result: EvaluationResult,
) -> str:
    """Format the owner-facing final quality review for Telegram."""
    rating_emoji = (
        "🔴"
        if result.rating == "poor"
        else "🟡"
        if result.rating == "satisfactory"
        else "🟢"
    )
    rating_label = format_quality_rating(result.rating)
    trigger_label = format_report_trigger(
        trigger,
        surface="quality_final_review",
        module="notifications",
    )
    stage_label = format_sales_stage(sales_stage)
    identity_block = format_owner_identity_block(
        phone=phone,
        customer_name=customer_name,
        inbound_channel_phone=inbound_channel_phone,
        conversation_created_at=conversation_created_at,
        last_activity_at=last_activity_at,
    )
    breakdown_lines = "\n".join(
        f"• {escape(block.block_name)}: {escape(_format_quality_block_score(block))}"
        for block in result.block_scores
    )
    diagnostics = result.diagnostics
    coverage_line = (
        f"<b>Coverage:</b> {diagnostics.applicable_rules}/15 rules, "
        f"{diagnostics.applicable_blocks}/4 blocks"
    )
    score_line = (
        "<b>Score:</b> not published — evaluator coverage error"
        if diagnostics.low_coverage
        else f"<b>Score:</b> {result.total_score:.1f}/30 ({escape(rating_label)})"
    )
    evidence_quotes = _collect_evidence_quotes(result)
    strengths_block = _format_bullets(
        result.strengths,
        fallback="No clearly stated strengths were recorded.",
    )
    weaknesses_block = _format_bullets(
        result.weaknesses,
        fallback="No material problems with the conversation were recorded.",
    )
    evidence_block = _format_bullets(
        evidence_quotes,
        fallback="No quotes from the conversation were recorded.",
    )
    recommendations_block = _format_bullets(
        result.recommendations,
        fallback="No additional recommendations were recorded.",
    )
    next_best_action = escape(
        result.next_best_action.strip()
        or "Review the conversation manually and decide the next step with the customer."
    )

    return (
        f"{rating_emoji} <b>Quality review</b>\n\n"
        f"{score_line}\n"
        f"{coverage_line}\n"
        f"<b>Reason:</b> {escape(trigger_label)}\n"
        f"<b>Conversation UUID:</b> <code>{conversation_id}</code>\n"
        f"{identity_block}\n"
        f"<b>Current stage:</b> {escape(stage_label)}\n\n"
        f"<b>Weighted breakdown</b>\n{breakdown_lines}\n\n"
        f"<b>What went well</b>\n{strengths_block}\n\n"
        f"<b>What weakened the conversation</b>\n{weaknesses_block}\n\n"
        f"<b>Evidence</b>\n{evidence_block}\n\n"
        f"<b>Recommendations</b>\n{recommendations_block}\n\n"
        f"<b>Next action</b>\n• {next_best_action}"
    )


def _format_optional_quality(score: float | None) -> str:
    return owner_na() if score is None else f"{score:.1f}/30"


def _format_optional_rate(rate: float | None) -> str:
    return owner_na() if rate is None else f"{rate:.1f}%"


def format_low_manager_score_alert_message(
    escalation_id: str,
    manager_name: str | None,
    score: float,
    rating: str,
    summary: str | None,
) -> str:
    """Format a low manager score alert as HTML for Telegram."""
    safe_summary = (
        (summary or owner_na())
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    manager_label = (
        (manager_name or owner_unknown(kind="person"))
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    rating_label = format_quality_rating(rating)
    return (
        "⚠️ <b>Low manager score</b>\n"
        f"<b>Escalation:</b> {escalation_id}\n"
        f"<b>Manager:</b> {manager_label}\n"
        f"<b>Score:</b> {score}/20 ({rating_label})\n"
        f"<b>In brief:</b> {safe_summary}"
    )


def format_daily_summary(metrics: DailySummaryData) -> str:
    """Format daily dashboard metrics as HTML for Telegram."""
    return (
        "📊 <b>Daily summary</b>\n\n"
        f"<b>Conversations:</b> {metrics.total_conversations}\n"
        f"<b>Unique customers:</b> {metrics.unique_customers}\n"
        f"<b>Escalations:</b> {metrics.escalation_count}\n"
        f"<b>Average quality score:</b> {_format_optional_quality(metrics.avg_quality_score)}\n"
        f"<b>Conversion (7d):</b> {_format_optional_rate(metrics.conversion_rate_7d)}\n"
    )


# =============================================================================
# Notification dispatchers (async, calls Telegram)
# =============================================================================


async def notify_catalog_mismatch(
    *,
    sku: str | None,
    treejar_slug: str,
    product_name: str | None,
    issue: str | None = None,
    detail: str | None = None,
) -> None:
    """Send an operational Treejar-vs-Zoho mismatch alert to Telegram."""
    try:
        client = _get_telegram_client()
        await client.send_message(
            format_catalog_mismatch_message(
                sku=sku,
                treejar_slug=treejar_slug,
                product_name=product_name,
                issue=issue,
                detail=detail,
            )
        )
    except Exception:
        logfire.error(
            "telegram.notify_catalog_mismatch.failed",
            notification_type="catalog_mismatch",
            treejar_slug=treejar_slug,
            sku=sku or "",
        )
        logger.exception("Failed to send catalog mismatch notification to Telegram")


async def notify_quality_alert(
    conversation_id: UUID,
    score: float,
    rating: str,
    summary: str,
    *,
    criteria: list[Any] | None = None,
    current_stage: str | None = None,
    trigger: str | None = "low_score",
    phone: str | None = None,
    customer_name: str | None = None,
    inbound_channel_phone: str | None = None,
    conversation_created_at: datetime | None = None,
    last_activity_at: datetime | None = None,
) -> None:
    """Send quality alert notification when score is below threshold.

    Safe to call even when Telegram is not configured.
    """
    try:
        client = _get_telegram_client()
        message = format_quality_alert_message(
            conversation_id,
            score,
            rating,
            summary,
            criteria=criteria,
            current_stage=current_stage,
            trigger=trigger,
            phone=phone,
            customer_name=customer_name,
            inbound_channel_phone=inbound_channel_phone,
            conversation_created_at=conversation_created_at,
            last_activity_at=last_activity_at,
        )
        await client.send_message(message)
    except Exception:
        logfire.error(
            "telegram.notify_quality_alert.failed",
            notification_type="quality_alert",
            conv_id=str(conversation_id),
            score=score,
        )
        logger.exception("Failed to send quality alert notification to Telegram")


async def notify_red_flag_warning(
    *,
    conversation_id: UUID,
    phone: str | None,
    customer_name: str | None,
    inbound_channel_phone: str | None,
    conversation_created_at: datetime | None,
    last_activity_at: datetime | None,
    sales_stage: str,
    flags: list[RedFlagItem],
    recommended_action: str,
) -> None:
    """Send a realtime red-flag warning to Telegram."""
    try:
        client = _get_telegram_client()
        message = format_red_flag_warning_message(
            conversation_id=conversation_id,
            phone=phone,
            customer_name=customer_name,
            inbound_channel_phone=inbound_channel_phone,
            conversation_created_at=conversation_created_at,
            last_activity_at=last_activity_at,
            sales_stage=sales_stage,
            flags=flags,
            recommended_action=recommended_action,
        )
        await client.send_message(message)
    except Exception:
        logfire.error(
            "telegram.notify_red_flag_warning.failed",
            notification_type="quality_red_flag",
            conv_id=str(conversation_id),
        )
        logger.exception("Failed to send red-flag warning to Telegram")


async def notify_final_quality_review(
    *,
    conversation_id: UUID,
    phone: str | None,
    customer_name: str | None,
    inbound_channel_phone: str | None,
    conversation_created_at: datetime | None,
    last_activity_at: datetime | None,
    sales_stage: str,
    trigger: str,
    result: EvaluationResult,
) -> None:
    """Send the owner-facing final quality review to Telegram."""
    try:
        client = _get_telegram_client()
        message = format_final_quality_review_message(
            conversation_id=conversation_id,
            phone=phone,
            customer_name=customer_name,
            inbound_channel_phone=inbound_channel_phone,
            conversation_created_at=conversation_created_at,
            last_activity_at=last_activity_at,
            sales_stage=sales_stage,
            trigger=trigger,
            result=result,
        )
        await client.send_message(message)
    except Exception:
        logfire.error(
            "telegram.notify_final_quality_review.failed",
            notification_type="quality_final_review",
            conv_id=str(conversation_id),
            score=result.total_score,
        )
        logger.exception("Failed to send final quality review to Telegram")


async def notify_daily_summary_telegram(metrics: DailySummaryData) -> None:
    """Send daily summary to Telegram.

    Args:
        metrics: DailySummaryData from calculate_daily_summary.
    """
    try:
        client = _get_telegram_client()
        message = format_daily_summary(metrics)
        await client.send_message(message)
    except Exception:
        logfire.error(
            "telegram.notify_daily_summary.failed",
            notification_type="daily_summary",
        )
        logger.exception("Failed to send daily summary to Telegram")


async def send_telegram_message(text: str) -> bool:
    """Send a pre-formatted message to Telegram.

    Public wrapper for _get_telegram_client — for use by other modules
    (e.g., weekly reports). Return whether Telegram confirmed delivery.
    Safe to call even when Telegram is not configured.
    """
    try:
        client = _get_telegram_client()
        result = await client.send_message(text)
        return bool(result and result.get("ok") is True)
    except Exception:
        logfire.error(
            "telegram.send_message.failed",
            notification_type="generic",
        )
        logger.exception("Failed to send message to Telegram")
        return False


async def run_daily_summary(ctx: dict[str, Any]) -> None:
    """ARQ job: Send daily summary via Telegram.

    Calculates dedicated daily summary metrics
    and sends a formatted summary to the configured Telegram chat.
    """
    from src.core.database import async_session_factory

    async with async_session_factory() as db:
        metrics = await calculate_daily_summary(db)

    await notify_daily_summary_telegram(metrics)
    logger.info("Daily summary sent to Telegram")
