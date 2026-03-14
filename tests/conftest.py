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


def _is_db_available() -> bool:
    """Check if PostgreSQL is reachable with valid credentials."""
    try:
        import asyncio

        import asyncpg  # type: ignore

        from src.core.config import settings

        url = str(settings.database_url).replace("+asyncpg", "")

        async def _probe() -> bool:
            try:
                conn = await asyncio.wait_for(asyncpg.connect(url), timeout=2.0)
                await conn.close()
                return True
            except Exception:
                return False

        return asyncio.run(_probe())
    except Exception:
        return False


DB_AVAILABLE = _is_db_available()

requires_db = pytest.mark.skipif(
    not DB_AVAILABLE, reason="PostgreSQL not available in this environment"
)


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
