from __future__ import annotations

import hashlib
import hmac
import logging
from html import escape
from typing import Any

from src.core.config import settings
from src.integrations.notifications.telegram import TelegramClient

logger = logging.getLogger(__name__)

_CANONICAL_BASE_URL = "https://noor.starec.ai"
_TELEGRAM_WEBHOOK_ALLOWED_UPDATES = ["message", "callback_query"]
_TELEGRAM_BOT_COMMANDS = [
    {"command": "admin", "description": "Open Noor CRM"},
    {"command": "status", "description": "Check operational status"},
    {"command": "help", "description": "Notification help"},
]
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


async def sync_telegram_webhook(*, sync_commands: bool = True) -> bool:
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
            if sync_commands:
                commands_result = await client.set_my_commands(_TELEGRAM_BOT_COMMANDS)
                if not commands_result or not commands_result.get("ok"):
                    logger.warning(
                        "Telegram command menu sync returned a non-ok response: %s",
                        commands_result,
                    )
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


_DRIFT_ALERT_KEY = "telegram:webhook_drift_alerted"
_DRIFT_ALERT_TTL_SECONDS = 3600


def _webhook_drift(info: dict[str, Any], webhook_url: str) -> str | None:
    """Describe why the registered webhook no longer reaches this runtime."""
    registered = str(info.get("url") or "")
    if registered != webhook_url:
        return f"url={registered or '(empty)'}"
    # Same URL registered with another secret: Telegram gets our 403 back.
    last_error = str(info.get("last_error_message") or "")
    if "403" in last_error:
        return f"last_error={last_error}"
    return None


async def reconcile_telegram_webhook(ctx: dict[str, Any]) -> dict[str, str]:
    """ARQ cron: restore the webhook when anyone else holding the token moves it.

    The bot token is also known outside this runtime (a legacy relay and an
    earlier server). A startup-only sync left `/reset` undelivered until the
    next deploy each time one of them changed or deleted the webhook, so the
    registration is checked every minute and repaired on drift.
    """
    webhook_url = telegram_webhook_url()
    if not settings.telegram_bot_token or webhook_url is None:
        return {"status": "skipped"}

    client = TelegramClient(
        bot_token=settings.telegram_bot_token,
        chat_id=settings.telegram_chat_id,
    )
    try:
        webhook_info = await client.get_webhook_info()
        info = webhook_info.get("result") if isinstance(webhook_info, dict) else None
        if not isinstance(info, dict):
            logger.warning("Telegram webhook check returned %s", webhook_info)
            return {"status": "unknown"}
        drift = _webhook_drift(info, webhook_url)
        if drift is None:
            return {"status": "ok"}

        result = await client.set_webhook(
            webhook_url=webhook_url,
            secret_token=expected_telegram_webhook_secret(),
            allowed_updates=_TELEGRAM_WEBHOOK_ALLOWED_UPDATES,
        )
        restored = bool(result and result.get("ok"))
        logger.warning(
            "Telegram webhook drift (%s); restore %s",
            drift,
            "succeeded" if restored else f"failed: {result}",
        )
        redis = ctx.get("redis")
        first_alert = redis is None or await redis.set(
            _DRIFT_ALERT_KEY, "1", ex=_DRIFT_ALERT_TTL_SECONDS, nx=True
        )
        if first_alert:
            await client.send_message(
                "⚠️ The Telegram bot webhook was changed outside Noor "
                f"({escape(drift)}). "
                + (
                    "It has been restored; queued commands will now arrive."
                    if restored
                    else "Restoring it failed; /reset will not work until fixed."
                )
                + " Someone else holds this bot token: revoke it in @BotFather "
                "and update TELEGRAM_BOT_TOKEN to stop this for good."
            )
        return {"status": "restored" if restored else "restore_failed"}
    except Exception:
        logger.exception("Telegram webhook reconcile failed")
        return {"status": "error"}
    finally:
        await client.aclose()
