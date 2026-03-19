"""Notification service — orchestrates sending alerts via Telegram.

Provides functions for different notification types:
- Escalation alerts
- Quality alerts (low score)
- Daily summary

All functions are safe to call even when Telegram is not configured.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol
from uuid import UUID

import logfire

from src.core.config import settings
from src.integrations.notifications.telegram import TelegramClient

logger = logging.getLogger(__name__)


class HasMetrics(Protocol):
    """Protocol for objects with dashboard metrics fields."""

    total_conversations: int
    unique_customers: int
    escalation_count: int
    avg_quality_score: float
    conversion_rate: float
    llm_cost_usd: float


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


# =============================================================================
# Message formatters (pure functions, no side effects)
# =============================================================================


def format_escalation_message(phone: str, conversation_id: UUID, reason: str) -> str:
    """Format an escalation alert as HTML for Telegram.

    Phone is masked for PII protection in the manager channel.
    """
    return (
        "🚨 <b>Escalation Alert</b>\n\n"
        f"<b>Phone:</b> <code>{_mask_phone(phone)}</code>\n"
        f"<b>Reason:</b> {reason}\n"
        f"<b>Conversation:</b> <code>{conversation_id}</code>\n\n"
        "A human manager has been notified and should review this conversation."
    )


def format_quality_alert_message(
    conversation_id: UUID,
    score: float,
    rating: str,
    summary: str,
) -> str:
    """Format a quality alert as HTML for Telegram."""
    emoji = "🔴" if score < 10 else "🟡"
    return (
        f"{emoji} <b>Quality Alert</b>\n\n"
        f"<b>Score:</b> {score}/30 ({rating})\n"
        f"<b>Conversation:</b> <code>{conversation_id}</code>\n"
        f"<b>Summary:</b> {summary}\n\n"
        "This dialogue scored below the acceptable threshold."
    )


def format_daily_summary(metrics: HasMetrics) -> str:
    """Format daily dashboard metrics as HTML for Telegram."""
    return (
        "📊 <b>Daily Summary</b>\n\n"
        f"<b>Conversations:</b> {metrics.total_conversations}\n"
        f"<b>Unique Customers:</b> {metrics.unique_customers}\n"
        f"<b>Escalations:</b> {metrics.escalation_count}\n"
        f"<b>Avg Quality:</b> {metrics.avg_quality_score}/30\n"
        f"<b>Conversion Rate:</b> {metrics.conversion_rate}%\n"
        f"<b>LLM Cost:</b> ${metrics.llm_cost_usd}\n"
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


async def notify_daily_summary_telegram(metrics: HasMetrics) -> None:
    """Send daily summary to Telegram.

    Args:
        metrics: DashboardMetricsResponse from calculate_dashboard_metrics.
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

    Calculates dashboard metrics for the last 24 hours
    and sends a formatted summary to the configured Telegram chat.
    """
    from src.core.database import async_session_factory
    from src.services.dashboard_metrics import calculate_dashboard_metrics

    async with async_session_factory() as db:
        metrics = await calculate_dashboard_metrics(db, period="day")

    await notify_daily_summary_telegram(metrics)
    logger.info("Daily summary sent to Telegram")
