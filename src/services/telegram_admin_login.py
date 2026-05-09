from __future__ import annotations

import hashlib
import json
import logging
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from src.core.config import settings

logger = logging.getLogger(__name__)

_CANONICAL_BASE_URL = "https://noor.starec.ai"
_TOKEN_KEY_PREFIX = "telegram_admin_login:"
_LOGIN_PATH = "/dashboard/telegram-login"


@dataclass(frozen=True)
class TelegramAdminLoginIdentity:
    chat_id: str
    user_id: int
    username: str | None = None
    first_name: str | None = None


@dataclass(frozen=True)
class TelegramAdminLoginLinkResult:
    authorized: bool
    url: str | None = None
    reason: str | None = None


def parse_telegram_admin_user_ids(raw: str) -> set[int]:
    user_ids: set[int] = set()
    for item in raw.split(","):
        value = item.strip()
        if not value:
            continue
        try:
            user_ids.add(int(value))
        except ValueError:
            logger.warning("Ignoring invalid Telegram admin user id: %s", value)
    return user_ids


def is_authorized_telegram_admin(*, chat_id: int | str | None, user_id: int) -> bool:
    configured_chat_id = settings.telegram_chat_id.strip()
    if not configured_chat_id or str(chat_id) != configured_chat_id:
        return False
    return user_id in parse_telegram_admin_user_ids(settings.telegram_admin_user_ids)


def telegram_admin_login_base_url() -> str | None:
    domain = settings.domain.strip()
    if domain:
        base_url = domain.rstrip("/")
        if not base_url.startswith(("http://", "https://")):
            base_url = f"https://{base_url}"
        return base_url.rstrip("/")
    if settings.is_production:
        return _CANONICAL_BASE_URL
    return None


def _token_key(raw_token: str) -> str:
    digest = hashlib.sha256(raw_token.encode()).hexdigest()
    return f"{_TOKEN_KEY_PREFIX}{digest}"


async def create_telegram_admin_login_link(
    redis: Any,
    *,
    chat_id: int | str | None,
    user_id: int,
    username: str | None,
    first_name: str | None,
) -> TelegramAdminLoginLinkResult:
    if not is_authorized_telegram_admin(chat_id=chat_id, user_id=user_id):
        return TelegramAdminLoginLinkResult(authorized=False, reason="unauthorized")

    base_url = telegram_admin_login_base_url()
    if base_url is None:
        return TelegramAdminLoginLinkResult(
            authorized=False,
            reason="domain_not_configured",
        )

    raw_token = secrets.token_urlsafe(32)
    payload = {
        "chat_id": str(chat_id),
        "user_id": user_id,
        "username": username,
        "first_name": first_name,
        "created_at": datetime.now(UTC).isoformat(),
    }
    await redis.setex(
        _token_key(raw_token),
        settings.telegram_admin_login_ttl_seconds,
        json.dumps(payload),
    )
    return TelegramAdminLoginLinkResult(
        authorized=True,
        url=f"{base_url}{_LOGIN_PATH}?token={raw_token}",
    )


async def consume_telegram_admin_login_token(
    redis: Any,
    raw_token: str,
) -> TelegramAdminLoginIdentity | None:
    token = raw_token.strip()
    if not token:
        return None

    redis_key = _token_key(token)
    getdel = getattr(redis, "getdel", None)
    if callable(getdel):
        raw_payload = await getdel(redis_key)
    else:
        raw_payload = await redis.get(redis_key)
        if raw_payload:
            await redis.delete(redis_key)

    if not raw_payload:
        return None

    if isinstance(raw_payload, bytes):
        raw_payload = raw_payload.decode()

    try:
        payload = json.loads(raw_payload)
        user_id = int(payload["user_id"])
        chat_id = str(payload["chat_id"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None

    return TelegramAdminLoginIdentity(
        chat_id=chat_id,
        user_id=user_id,
        username=payload.get("username"),
        first_name=payload.get("first_name"),
    )
