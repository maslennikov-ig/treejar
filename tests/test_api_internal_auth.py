from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.core.config import Settings, settings
from src.main import app


@pytest.fixture
def restore_api_auth_settings() -> Generator[None, None, None]:
    original_env = settings.app_env
    original_api_key = settings.api_key
    yield
    settings.app_env = original_env
    settings.api_key = original_api_key


@pytest.mark.asyncio
async def test_internal_routes_fail_closed_when_api_key_missing_in_production(
    restore_api_auth_settings: None,
) -> None:
    settings.app_env = "production"
    settings.api_key = ""

    with patch("src.api.v1.quality.get_reviews", new_callable=AsyncMock) as mock_get:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            response = await ac.get("/api/v1/quality/reviews/")

    assert response.status_code == 503
    assert response.json()["detail"] == "Internal API authentication is not configured"
    mock_get.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("header_value", [None, "wrong-key"])
async def test_internal_routes_reject_missing_or_wrong_api_key_in_production(
    restore_api_auth_settings: None,
    header_value: str | None,
) -> None:
    settings.app_env = "production"
    settings.api_key = "expected-key"
    headers = {} if header_value is None else {"X-API-Key": header_value}

    with patch("src.api.v1.quality.get_reviews", new_callable=AsyncMock) as mock_get:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            response = await ac.get("/api/v1/quality/reviews/", headers=headers)

    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid or missing API key"
    mock_get.assert_not_awaited()


@pytest.mark.asyncio
async def test_internal_routes_allow_matching_api_key_in_production(
    restore_api_auth_settings: None,
) -> None:
    settings.app_env = "production"
    settings.api_key = "expected-key"

    with patch("src.api.v1.quality.get_reviews", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = ([], 0)
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            response = await ac.get(
                "/api/v1/quality/reviews/",
                headers={"X-API-Key": "expected-key"},
            )

    assert response.status_code == 200
    assert response.json()["items"] == []
    mock_get.assert_awaited_once()


def test_settings_require_api_key_in_production() -> None:
    with pytest.raises(ValueError, match="api_key must be set in production"):
        Settings(
            app_env="production",
            app_secret_key="prod-secret",
            admin_password="prod-admin-password",
            api_key="",
        )
