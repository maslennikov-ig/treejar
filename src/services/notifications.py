"""Notification service — orchestrates sending alerts via Telegram.

Provides functions for different notification types:
- Escalation alerts
- Quality alerts (low score)
- Daily summary

All functions are safe to call even when Telegram is not configured.
"""

from __future__ import annotations

import logging
from html import escape
from typing import Any
from uuid import UUID

import logfire

from src.core.config import settings
from src.integrations.notifications.telegram import TelegramClient
from src.quality.schemas import EvaluationResult, RedFlagItem
from src.services.daily_summary import DailySummaryData, calculate_daily_summary

logger = logging.getLogger(__name__)


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
    # CR-4: HTML-escape reason (may contain LLM-generated text with <, >, &)
    safe_reason = reason.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    msg = (
        "🚨 <b>Escalation Alert</b>\n\n"
        f'📞 <b>Phone:</b> <a href="tel:{phone_display}">{phone_display}</a>\n'
        f"<b>Reason:</b> {safe_reason}\n"
        f"<b>Conversation:</b> <code>{conversation_id}</code>\n"
    )

    if context:
        # Truncate and escape HTML chars in context
        safe_context = (
            context[:500]
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        msg += f"\n<b>Контекст:</b>\n<i>{safe_context}</i>\n"

    msg += "\nA human manager has been notified and should review this conversation."
    return msg


def format_quality_alert_message(
    conversation_id: UUID,
    score: float,
    rating: str,
    summary: str,
) -> str:
    """Format a quality alert as HTML for Telegram."""
    emoji = "🔴" if score < 10 else "🟡"
    # R3-4: HTML-escape summary (LLM-generated, may contain < > &)
    safe_summary = (
        summary.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )
    return (
        f"{emoji} <b>Quality Alert</b>\n\n"
        f"<b>Score:</b> {score}/30 ({rating})\n"
        f"<b>Conversation:</b> <code>{conversation_id}</code>\n"
        f"<b>Summary:</b> {safe_summary}\n\n"
        "This dialogue scored below the acceptable threshold."
    )


def format_red_flag_warning_message(
    *,
    conversation_id: UUID,
    phone: str | None,
    sales_stage: str,
    flags: list[RedFlagItem],
    recommended_action: str,
) -> str:
    """Format a compact realtime red-flag warning for Telegram."""
    phone_line = f"<b>Phone:</b> {escape(phone)}\n" if phone and phone.strip() else ""
    red_flag_lines = "\n".join(
        f"• <b>{escape(flag.title)}</b>: {escape(flag.explanation)}" for flag in flags
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
        fallback="No explicit transcript evidence returned by the judge.",
    )

    return (
        "🚨 <b>Red Flag Warning</b>\n\n"
        f"<b>Conversation UUID:</b> <code>{conversation_id}</code>\n"
        f"{phone_line}"
        f"<b>Sales stage:</b> {escape(sales_stage)}\n\n"
        f"<b>Red flags:</b>\n{red_flag_lines}\n\n"
        f"<b>Evidence:</b>\n{evidence_block}\n\n"
        f"<b>Recommended action:</b> {escape(recommended_action)}"
    )


def format_final_quality_review_message(
    *,
    conversation_id: UUID,
    phone: str | None,
    customer_name: str | None,
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
    customer_bits = []
    if phone and phone.strip():
        customer_bits.append(f"<b>Customer phone:</b> {escape(phone)}")
    if customer_name and customer_name.strip():
        customer_bits.append(f"<b>Customer name:</b> {escape(customer_name)}")
    customer_block = "\n".join(customer_bits) + ("\n" if customer_bits else "")
    breakdown_lines = "\n".join(
        f"• {escape(block.block_name)}: {block.points:.1f}/{block.weight:.0f}"
        for block in result.block_scores
    )
    evidence_quotes = _collect_evidence_quotes(result)

    return (
        f"{rating_emoji} <b>Quality Review</b>\n\n"
        f"<b>Score:</b> {result.total_score:.1f}/30 ({escape(result.rating)})\n"
        f"<b>Trigger:</b> {escape(trigger)}\n"
        f"<b>Conversation UUID:</b> <code>{conversation_id}</code>\n"
        f"{customer_block}"
        f"<b>Current stage:</b> {escape(sales_stage)}\n\n"
        f"<b>Weighted breakdown:</b>\n{breakdown_lines}\n\n"
        f"<b>What went well</b>\n{_format_bullets(result.strengths, fallback='No clear strengths noted.')}\n\n"
        f"<b>What hurt the dialogue</b>\n{_format_bullets(result.weaknesses, fallback='No material weaknesses noted.')}\n\n"
        f"<b>Evidence</b>\n{_format_bullets(evidence_quotes, fallback='No transcript evidence captured.')}\n\n"
        f"<b>Recommendations</b>\n{_format_bullets(result.recommendations, fallback='No additional recommendations captured.')}\n\n"
        f"<b>Next best action</b>\n• {escape(result.next_best_action)}"
    )


def _format_optional_quality(score: float | None) -> str:
    return "N/A" if score is None else f"{score:.1f}/30"


def _format_optional_rate(rate: float | None) -> str:
    return "N/A" if rate is None else f"{rate:.1f}%"


def format_daily_summary(metrics: DailySummaryData) -> str:
    """Format daily dashboard metrics as HTML for Telegram."""
    return (
        "📊 <b>Daily Summary</b>\n\n"
        f"<b>Conversations:</b> {metrics.total_conversations}\n"
        f"<b>Unique Customers:</b> {metrics.unique_customers}\n"
        f"<b>Escalations:</b> {metrics.escalation_count}\n"
        f"<b>Avg Quality:</b> {_format_optional_quality(metrics.avg_quality_score)}\n"
        f"<b>Conversion Rate (7d):</b> {_format_optional_rate(metrics.conversion_rate_7d)}\n"
    )


# =============================================================================
# Notification dispatchers (async, calls Telegram)
# =============================================================================


async def notify_escalation(phone: str, conversation_id: UUID, reason: str) -> None:
    """Send escalation notification to Telegram.

    Safe to call even when Telegram is not configured.
    """
    try:
        client = _get_telegram_client()
        message = format_escalation_message(phone, conversation_id, reason)
        await client.send_message(message)
    except Exception:
        logfire.error(
            "telegram.notify_escalation.failed",
            notification_type="escalation",
            phone_masked=_mask_phone(phone),
            conv_id=str(conversation_id),
        )
        logger.exception("Failed to send escalation notification to Telegram")


async def notify_quality_alert(
    conversation_id: UUID,
    score: float,
    rating: str,
    summary: str,
) -> None:
    """Send quality alert notification when score is below threshold.

    Safe to call even when Telegram is not configured.
    """
    try:
        client = _get_telegram_client()
        message = format_quality_alert_message(conversation_id, score, rating, summary)
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


async def send_telegram_message(text: str) -> None:
    """Send a pre-formatted message to Telegram.

    Public wrapper for _get_telegram_client — for use by other modules
    (e.g., weekly reports). Safe to call even when Telegram is not configured.
    """
    try:
        client = _get_telegram_client()
        await client.send_message(text)
    except Exception:
        logfire.error(
            "telegram.send_message.failed",
            notification_type="generic",
        )
        logger.exception("Failed to send message to Telegram")


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
