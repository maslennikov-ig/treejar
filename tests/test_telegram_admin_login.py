from __future__ import annotations

import json
from collections.abc import Iterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.config import settings


class _MemoryRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.ttls: dict[str, int] = {}

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self.values[key] = value
        self.ttls[key] = ttl

    async def getdel(self, key: str) -> str | None:
        return self.values.pop(key, None)


class _DbContext:
    def __init__(self, db: AsyncMock) -> None:
        self.db = db

    async def __aenter__(self) -> AsyncMock:
        return self.db

    async def __aexit__(self, *_args: object) -> bool:
        return False


@pytest.fixture
def telegram_admin_settings() -> Iterator[None]:
    original = {
        "telegram_chat_id": settings.telegram_chat_id,
        "telegram_admin_user_ids": getattr(settings, "telegram_admin_user_ids", ""),
        "telegram_admin_login_ttl_seconds": getattr(
            settings, "telegram_admin_login_ttl_seconds", 300
        ),
        "domain": settings.domain,
        "app_env": settings.app_env,
    }
    settings.telegram_chat_id = "-100123456789"
    settings.telegram_admin_user_ids = "777, 888"
    settings.telegram_admin_login_ttl_seconds = 300
    settings.domain = "https://crm.example.test"
    settings.app_env = "development"
    yield
    settings.telegram_chat_id = original["telegram_chat_id"]
    settings.telegram_admin_user_ids = original["telegram_admin_user_ids"]
    settings.telegram_admin_login_ttl_seconds = original[
        "telegram_admin_login_ttl_seconds"
    ]
    settings.domain = original["domain"]
    settings.app_env = original["app_env"]


def test_parse_telegram_admin_user_ids() -> None:
    from src.services.telegram_admin_login import parse_telegram_admin_user_ids

    assert parse_telegram_admin_user_ids("777, 888, ,999") == {777, 888, 999}


def test_empty_telegram_admin_user_ids_disables_access(
    telegram_admin_settings: None,
) -> None:
    from src.services.telegram_admin_login import is_authorized_telegram_admin

    settings.telegram_admin_user_ids = ""

    assert is_authorized_telegram_admin(chat_id=-100123456789, user_id=777) is False


@pytest.mark.asyncio
async def test_authorized_admin_link_is_short_lived_and_does_not_store_raw_token(
    telegram_admin_settings: None,
) -> None:
    from src.services.telegram_admin_login import create_telegram_admin_login_link

    redis = _MemoryRedis()

    with patch("src.services.telegram_admin_login.secrets.token_urlsafe") as token:
        token.return_value = "raw-login-token"
        result = await create_telegram_admin_login_link(
            redis,
            chat_id=-100123456789,
            user_id=777,
            username="owner",
            first_name="Noor",
        )

    assert result.authorized is True
    assert result.url == (
        "https://crm.example.test/dashboard/telegram-login?token=raw-login-token"
    )
    assert len(redis.values) == 1
    redis_key, redis_payload = next(iter(redis.values.items()))
    assert "raw-login-token" not in redis_key
    assert "raw-login-token" not in redis_payload
    assert redis.ttls[redis_key] == 300
    payload = json.loads(redis_payload)
    assert payload["chat_id"] == "-100123456789"
    assert payload["user_id"] == 777
    assert payload["username"] == "owner"


@pytest.mark.asyncio
async def test_non_whitelisted_admin_link_request_is_denied(
    telegram_admin_settings: None,
) -> None:
    from src.services.telegram_admin_login import create_telegram_admin_login_link

    redis = _MemoryRedis()

    result = await create_telegram_admin_login_link(
        redis,
        chat_id=-100123456789,
        user_id=999,
        username="intruder",
        first_name=None,
    )

    assert result.authorized is False
    assert result.url is None
    assert redis.values == {}


@pytest.mark.asyncio
async def test_wrong_chat_admin_link_request_is_denied(
    telegram_admin_settings: None,
) -> None:
    from src.services.telegram_admin_login import create_telegram_admin_login_link

    redis = _MemoryRedis()

    result = await create_telegram_admin_login_link(
        redis,
        chat_id=-100999999999,
        user_id=777,
        username="owner",
        first_name=None,
    )

    assert result.authorized is False
    assert result.url is None
    assert redis.values == {}


@pytest.mark.asyncio
async def test_consume_admin_login_token_is_one_time(
    telegram_admin_settings: None,
) -> None:
    from src.services.telegram_admin_login import (
        consume_telegram_admin_login_token,
        create_telegram_admin_login_link,
    )

    redis = _MemoryRedis()

    with patch("src.services.telegram_admin_login.secrets.token_urlsafe") as token:
        token.return_value = "raw-login-token"
        await create_telegram_admin_login_link(
            redis,
            chat_id=-100123456789,
            user_id=777,
            username="owner",
            first_name="Noor",
        )

    identity = await consume_telegram_admin_login_token(redis, "raw-login-token")
    reused = await consume_telegram_admin_login_token(redis, "raw-login-token")

    assert identity is not None
    assert identity.chat_id == "-100123456789"
    assert identity.user_id == 777
    assert identity.username == "owner"
    assert reused is None


@pytest.mark.asyncio
async def test_admin_command_sends_login_url_for_whitelisted_user(
    telegram_admin_settings: None,
) -> None:
    from src.api.telegram_webhook import _handle_admin_login_command_if_present

    telegram = AsyncMock()

    with (
        patch("src.api.telegram_webhook.redis_client", _MemoryRedis()),
        patch("src.api.telegram_webhook._get_telegram_client", return_value=telegram),
        patch("src.services.telegram_admin_login.secrets.token_urlsafe") as token,
    ):
        token.return_value = "raw-login-token"
        handled = await _handle_admin_login_command_if_present(
            {
                "chat": {"id": -100123456789},
                "from": {"id": 777, "username": "owner", "first_name": "Noor"},
                "text": "/admin@NoorBot",
            }
        )

    assert handled is True
    telegram.send_message_with_inline_keyboard.assert_awaited_once()
    text = telegram.send_message_with_inline_keyboard.await_args.args[0]
    buttons = telegram.send_message_with_inline_keyboard.await_args.args[1]
    assert "CRM" in text
    assert buttons[0][0]["text"] == "Открыть Noor CRM"
    assert buttons[0][0]["url"] == (
        "https://crm.example.test/dashboard/telegram-login?token=raw-login-token"
    )


@pytest.mark.asyncio
async def test_admin_command_from_wrong_chat_is_silent(
    telegram_admin_settings: None,
) -> None:
    from src.api.telegram_webhook import _handle_admin_login_command_if_present

    telegram = AsyncMock()

    with patch("src.api.telegram_webhook._get_telegram_client", return_value=telegram):
        handled = await _handle_admin_login_command_if_present(
            {
                "chat": {"id": -100999999999},
                "from": {"id": 777, "username": "owner"},
                "text": "/admin",
            }
        )

    assert handled is True
    telegram.send_message.assert_not_awaited()
    telegram.send_message_with_inline_keyboard.assert_not_awaited()


@pytest.mark.asyncio
async def test_admin_command_from_non_whitelisted_user_has_no_login_url(
    telegram_admin_settings: None,
) -> None:
    from src.api.telegram_webhook import _handle_admin_login_command_if_present

    telegram = AsyncMock()

    with patch("src.api.telegram_webhook._get_telegram_client", return_value=telegram):
        handled = await _handle_admin_login_command_if_present(
            {
                "chat": {"id": -100123456789},
                "from": {"id": 999, "username": "other"},
                "text": "/admin",
            }
        )

    assert handled is True
    telegram.send_message.assert_awaited_once()
    telegram.send_message_with_inline_keyboard.assert_not_awaited()
    assert "999" in telegram.send_message.await_args.args[0]


@pytest.mark.asyncio
async def test_dashboard_telegram_login_sets_admin_session_and_writes_audit(
    client: object,
) -> None:
    from src.services.telegram_admin_login import TelegramAdminLoginIdentity

    db = AsyncMock()
    log_admin_action = AsyncMock()
    consume_token = AsyncMock(
        return_value=TelegramAdminLoginIdentity(
            chat_id="-100123456789",
            user_id=777,
            username="owner",
            first_name="Noor",
        )
    )

    with (
        patch("src.main.consume_telegram_admin_login_token", consume_token),
        patch("src.main.async_session_factory", MagicMock(return_value=_DbContext(db))),
        patch("src.main.log_admin_action", log_admin_action),
    ):
        response = await client.get(
            "/dashboard/telegram-login?token=raw-login-token",
            follow_redirects=False,
        )

    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard/"
    consume_token.assert_awaited_once()
    log_admin_action.assert_awaited_once()
    audit_kwargs = log_admin_action.await_args.kwargs
    assert audit_kwargs["action"] == "admin_login.telegram"
    assert audit_kwargs["entity_type"] == "admin_session"
    assert audit_kwargs["actor"] == "telegram:777"
    assert audit_kwargs["metadata"]["telegram_user_id"] == 777
    assert "token" not in json.dumps(audit_kwargs["metadata"]).lower()
    db.commit.assert_awaited_once()

    dashboard = await client.get("/dashboard/")
    assert dashboard.status_code == 200


@pytest.mark.asyncio
async def test_dashboard_telegram_login_rejects_invalid_token(client: object) -> None:
    consume_token = AsyncMock(return_value=None)

    with patch("src.main.consume_telegram_admin_login_token", consume_token):
        response = await client.get(
            "/dashboard/telegram-login?token=bad-token",
            follow_redirects=False,
        )

    assert response.status_code == 401
    dashboard = await client.get("/dashboard/")
    assert dashboard.status_code == 401
