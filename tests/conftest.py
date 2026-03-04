from __future__ import annotations

import os

os.environ["OPENROUTER_API_KEY"] = "test-key"
os.environ["WAZZUP_API_KEY"] = "fake-wazzup-key"
os.environ["WAZZUP_API_URL"] = "http://fake-wazzup-url"

import os
from collections.abc import AsyncGenerator

os.environ["LOGFIRE_IGNORE_NO_CONFIG"] = "1"

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.v1.admin import require_admin_session
from src.main import app


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def _noop_admin_auth() -> None:
    """No-op dependency override for admin auth in tests."""


@pytest.fixture
async def admin_client() -> AsyncGenerator[AsyncClient, None]:
    """Client with admin auth bypassed via dependency override."""
    app.dependency_overrides[require_admin_session] = _noop_admin_auth
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=False
    ) as ac:
        yield ac
    app.dependency_overrides.pop(require_admin_session, None)
