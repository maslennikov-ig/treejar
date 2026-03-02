from src.api.admin.auth import authentication_backend
from src.core.config import settings


async def test_admin_auth_login_success() -> None:
    class MockRequest:
        def __init__(self, form_data: dict[str, str]) -> None:
            self.session: dict[str, str] = {}
            self._form_data = form_data

        async def form(self) -> dict[str, str]:
            return self._form_data

    request = MockRequest({"username": settings.admin_username, "password": settings.admin_password})
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
