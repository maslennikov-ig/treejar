"""API endpoints for notification management.

Provides test send and configuration viewing endpoints.
"""
from __future__ import annotations

from fastapi import APIRouter

from src.core.config import settings
from src.integrations.notifications.telegram import TelegramClient

router = APIRouter()


@router.post("/test")
async def send_test_notification() -> dict[str, str]:
    """Send a test notification to verify Telegram integration."""
    client = TelegramClient(
        bot_token=settings.telegram_bot_token,
        chat_id=settings.telegram_chat_id,
    )

    if not client.is_configured:
        return {"status": "skipped", "reason": "Telegram not configured"}

    await client.send_message(
        "✅ <b>Test Notification</b>\n\n"
        "Telegram integration is working correctly.\n"
        f"<i>Bot: {settings.app_name}</i>"
    )
    return {"status": "sent"}


@router.get("/config")
async def get_notification_config() -> dict[str, object]:
    """Return current notification configuration (sensitive values masked)."""
    token = settings.telegram_bot_token
    chat_id = settings.telegram_chat_id

    return {
        "telegram_configured": bool(token),
        "telegram_bot_token": f"***{token[-4:]}" if len(token) > 4 else "not set",
        "telegram_chat_id": f"***{chat_id[-4:]}" if len(chat_id) > 4 else "not set",
    }
