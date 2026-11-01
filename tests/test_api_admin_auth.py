from src.api.admin.auth import authentication_backend
from src.core.config import settings


async def test_admin_auth_login_success() -> None:
    class MockRequest:
        def __init__(self, form_data: dict[str, str]) -> None:
            self.session: dict[str, str] = {}
            self._form_data = form_data

        async def form(self) -> dict[str, str]:
            return self._form_data

    request = MockRequest(
        {"username": settings.admin_username, "password": settings.admin_password}
    )
    # Ignore typing here because it's a mock
    success = await authentication_backend.login(request)  # type: ignore

    assert success is True
    assert request.session.get("token") == "admin_session"


async def test_admin_auth_login_failure() -> None:
    class MockRequest:
        def __init__(self, form_data: dict[str, str]) -> None:
            self.session: dict[str, str] = {}
            self._form_data = form_data

        async def form(self) -> dict[str, str]:
            return self._form_data

    request = MockRequest({"username": "wrong", "password": "wrong"})
    success = await authentication_backend.login(request)  # type: ignore

    assert success is False
    assert request.session.get("token") is None


async def test_admin_auth_logout() -> None:
    class MockRequest:
        def __init__(self) -> None:
            self.session = {"token": "admin_session", "other": "data"}

    request = MockRequest()
    success = await authentication_backend.logout(request)  # type: ignore

    assert success is True
    assert not request.session


async def test_admin_auth_authenticate() -> None:
    class MockRequest:
        def __init__(self, session_data: dict[str, str]) -> None:
            self.session = session_data

    request_valid = MockRequest({"token": "admin_session"})
    assert await authentication_backend.authenticate(request_valid) is True  # type: ignore

    request_invalid = MockRequest({"token": "wrong"})
    assert await authentication_backend.authenticate(request_invalid) is False  # type: ignore

    request_empty = MockRequest({})
    assert await authentication_backend.authenticate(request_empty) is False  # type: ignore


async def test_admin_auth_password_login_records_audit_entry() -> None:
    """Password login writes an admin_login.password audit row via async_session_factory (AD-14)."""
    from types import SimpleNamespace
    from unittest.mock import patch

    from src.models.admin_action_audit import AdminActionAudit

    added: list[object] = []

    class FakeSession:
        def add(self, obj: object) -> None:
            added.append(obj)

        async def flush(self) -> None:
            return None

        async def commit(self) -> None:
            return None

        async def __aenter__(self) -> "FakeSession":
            return self

        async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
            return None

    class MockRequest:
        def __init__(self) -> None:
            self.session: dict[str, str] = {}
            self.url = SimpleNamespace(path="/admin/login")

        async def form(self) -> dict[str, str]:
            return {
                "username": settings.admin_username,
                "password": settings.admin_password,
            }

    request = MockRequest()
    with patch(
        "src.core.database.async_session_factory",
        return_value=FakeSession(),
    ):
        success = await authentication_backend.login(request)  # type: ignore[arg-type]

    assert success is True
    assert len(added) == 1
    audit = added[0]
    assert isinstance(audit, AdminActionAudit)
    assert audit.action == "admin_login.password"
    assert audit.entity_type == "admin_session"
    assert audit.actor == settings.admin_username


async def test_notification_config_requires_both_token_and_chat_id(
    monkeypatch: object,
) -> None:
    """telegram_configured must be False unless both bot token and chat_id are set (AD-36)."""
    from src.api.v1.notifications import get_notification_config

    mp = monkeypatch  # type: ignore[assignment]
    mp.setattr(settings, "telegram_bot_token", "bot-token")
    mp.setattr(settings, "telegram_chat_id", "")
    missing_chat = await get_notification_config()
    assert missing_chat["telegram_configured"] is False

    mp.setattr(settings, "telegram_bot_token", "")
    mp.setattr(settings, "telegram_chat_id", "123456")
    missing_token = await get_notification_config()
    assert missing_token["telegram_configured"] is False

    mp.setattr(settings, "telegram_bot_token", "bot-token")
    mp.setattr(settings, "telegram_chat_id", "123456")
    both_present = await get_notification_config()
    assert both_present["telegram_configured"] is True
