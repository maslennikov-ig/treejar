from __future__ import annotations

import hashlib
import hmac
import logging

from src.core.config import settings
from src.integrations.notifications.telegram import TelegramClient

logger = logging.getLogger(__name__)

_CANONICAL_BASE_URL = "https://noor.starec.ai"
_TELEGRAM_WEBHOOK_ALLOWED_UPDATES = ["message", "callback_query"]
_TELEGRAM_WEBHOOK_PATH = "/api/v1/webhook/telegram"


def expected_telegram_webhook_secret() -> str:
    """Derive the runtime secret expected by Telegram webhook validation."""
    return hmac.new(
        settings.app_secret_key.encode(),
        settings.telegram_bot_token.encode(),
        hashlib.sha256,
    ).hexdigest()[:32]


def telegram_webhook_url() -> str | None:
    """Build the canonical HTTPS Telegram webhook URL for this runtime."""
    domain = settings.domain.strip()
    if domain:
        base_url = domain.rstrip("/")
        if not base_url.startswith(("http://", "https://")):
            base_url = f"https://{base_url}"
        return f"{base_url.rstrip('/')}{_TELEGRAM_WEBHOOK_PATH}"

    if settings.is_production:
        return f"{_CANONICAL_BASE_URL}{_TELEGRAM_WEBHOOK_PATH}"

    return None


async def sync_telegram_webhook() -> bool:
    """Upsert the Telegram webhook so the registered secret never drifts."""
    if not settings.telegram_bot_token:
        logger.info("Telegram webhook sync skipped: bot token is not configured")
        return False

    webhook_url = telegram_webhook_url()
    if webhook_url is None:
        logger.info(
            "Telegram webhook sync skipped: domain is not configured for %s",
            settings.app_env,
        )
        return False

    client = TelegramClient(
        bot_token=settings.telegram_bot_token,
        chat_id=settings.telegram_chat_id,
    )
    secret_token = expected_telegram_webhook_secret()

    try:
        webhook_info = await client.get_webhook_info()
        info = webhook_info.get("result") if isinstance(webhook_info, dict) else None
        if isinstance(info, dict):
            logger.info(
                "Telegram webhook before sync: url=%s pending=%s last_error=%s",
                info.get("url") or "",
                info.get("pending_update_count") or 0,
                info.get("last_error_message") or "",
            )

        result = await client.set_webhook(
            webhook_url=webhook_url,
            secret_token=secret_token,
            allowed_updates=_TELEGRAM_WEBHOOK_ALLOWED_UPDATES,
        )
        synced = bool(result and result.get("ok"))
        if synced:
            logger.info("Telegram webhook synced to %s", webhook_url)
        else:
            logger.warning(
                "Telegram webhook sync returned a non-ok response: %s", result
            )
        return synced
    except Exception:
        logger.exception("Telegram webhook sync failed")
        return False
    finally:
        await client.aclose()
