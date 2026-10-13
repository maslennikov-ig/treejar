"""Opt-in reconciliation of the owner-approved shared Wazzup callback."""

from __future__ import annotations

import asyncio
import logging
import secrets
from html import escape
from typing import Any
from urllib.parse import urlsplit

import httpx

from src.core.config import settings
from src.integrations.notifications.telegram import TelegramClient

logger = logging.getLogger(__name__)

WAZZUP_WEBHOOK_URL = "https://noor.starec.ai/api/v1/webhook/wazzup"
_LOCK_KEY = "wazzup:webhook_guard:lock"
_ALERT_KEY = "wazzup:webhook_guard:alerted"
_RELEASE_LOCK = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
end
return 0
"""


def _configuration(response: httpx.Response) -> dict[str, Any]:
    response.raise_for_status()
    data = response.json()
    if (
        not isinstance(data, dict)
        or not isinstance(data.get("webhooksUri"), str)
        or not isinstance(data.get("subscriptions"), dict)
        or not data["subscriptions"]
        or any(type(value) is not bool for value in data["subscriptions"].values())
    ):
        raise ValueError("Invalid Wazzup webhook configuration response")
    return data


def _callback_host(callback: str) -> str:
    """Keep displaced callback query secrets out of logs and notifications."""
    try:
        return urlsplit(callback).hostname or "(empty)"
    except ValueError:
        return "(invalid)"


async def _notify(redis: Any, *, restored: bool, displaced_host: str) -> None:
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        return
    client = TelegramClient(
        bot_token=settings.telegram_bot_token, chat_id=settings.telegram_chat_id
    )
    try:
        async with asyncio.timeout(5):
            outcome = "restored" if restored else "failed"
            if not await redis.set(f"{_ALERT_KEY}:{outcome}", "1", ex=3600, nx=True):
                return
            await client.send_message(
                "⚠️ Wazzup changed Noor's incoming-message address "
                f"(host: {escape(displaced_host)}). "
                + (
                    "The approved bot address has been restored."
                    if restored
                    else "Automatic restoration could not be verified; check routing."
                )
                + " Check the competing integration with access to this Wazzup account."
            )
    except Exception as exc:
        logger.warning(
            "Wazzup webhook guard notification failed: %s", type(exc).__name__
        )
    finally:
        try:
            async with asyncio.timeout(3):
                await client.aclose()
        except Exception as exc:
            logger.warning(
                "Wazzup webhook guard notification close failed: %s", type(exc).__name__
            )


async def reconcile_wazzup_webhook(ctx: dict[str, Any]) -> dict[str, str]:
    """Check once per minute; repair the callback while preserving subscriptions.

    The owner must enable this explicitly because the callback is shared by
    all channels in the provider account. It recovers routing; it does not
    revoke another integration's ability to change the configuration.
    """
    if not settings.wazzup_webhook_guard_enabled:
        return {"status": "disabled"}
    if (
        not settings.wazzup_api_key
        or not settings.wazzup_channel_id
        or settings.wazzup_channel_id != settings.wazzup_outbound_allowed_channel_id
    ):
        return {"status": "unsafe_configuration"}
    redis = ctx.get("redis")
    if redis is None:
        return {"status": "unavailable"}

    token = secrets.token_hex(16)
    locked = False
    displaced_host: str | None = None
    result = {"status": "error"}
    try:
        async with asyncio.timeout(30):
            locked = bool(await redis.set(_LOCK_KEY, token, ex=45, nx=True))
            if not locked:
                return {"status": "busy"}
            async with httpx.AsyncClient(
                base_url=settings.wazzup_api_url,
                headers={"Authorization": f"Bearer {settings.wazzup_api_key}"},
                timeout=8,
                follow_redirects=False,
            ) as client:
                before = _configuration(await client.get("webhooks"))
                if before["webhooksUri"] == WAZZUP_WEBHOOK_URL:
                    return {"status": "ok"}
                displaced_host = _callback_host(before["webhooksUri"])
                # v3 requires subscriptions in PATCH. Refuse a write if another
                # operator changed them (or the callback) between our reads.
                current = _configuration(await client.get("webhooks"))
                if current != before:
                    result = {"status": "changed_during_check"}
                else:
                    response = await client.patch(
                        "webhooks",
                        json={
                            "webhooksUri": WAZZUP_WEBHOOK_URL,
                            "subscriptions": current["subscriptions"],
                        },
                    )
                    response.raise_for_status()
                    after = _configuration(await client.get("webhooks"))
                    result = {
                        "status": "restored"
                        if after["webhooksUri"] == WAZZUP_WEBHOOK_URL
                        and after["subscriptions"] == current["subscriptions"]
                        else "restore_failed"
                    }
                logger.warning(
                    "Wazzup webhook drift: displaced_host=%s status=%s",
                    displaced_host,
                    result["status"],
                )
    except Exception as exc:
        # HTTP response bodies and displaced URIs may contain credentials.
        logger.warning("Wazzup webhook guard failed: %s", type(exc).__name__)
    finally:
        if locked:
            try:
                async with asyncio.timeout(3):
                    await redis.eval(_RELEASE_LOCK, 1, _LOCK_KEY, token)
            except Exception as exc:
                logger.warning(
                    "Wazzup webhook guard lease release failed: %s", type(exc).__name__
                )
    if displaced_host is not None:
        await _notify(
            redis,
            restored=result["status"] == "restored",
            displaced_host=displaced_host,
        )
    return result
