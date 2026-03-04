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

from src.main import app


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def admin_client() -> AsyncGenerator[AsyncClient, None]:
    """Client with admin session auth (logged in via SQLAdmin)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=False
    ) as ac:
        # Login via SQLAdmin form to get session cookie
        await ac.post(
            "/admin/login",
            data={"username": "admin", "password": "admin"},
            follow_redirects=False,
        )
        # Session cookie is set regardless of redirect status
        yield ac

