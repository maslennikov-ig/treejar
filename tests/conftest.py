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

from src.core.config import settings
from src.main import app


def _is_db_available() -> bool:
    """Check if PostgreSQL is reachable with valid credentials."""
    try:
        import asyncio

        import asyncpg

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

_skipif_no_db = pytest.mark.skipif(
    not DB_AVAILABLE, reason="PostgreSQL not available in this environment"
)


def integration(fn: object) -> object:
    """Decorator: marks test as 'integration' AND skips when DB is unavailable.

    Usage:
        @integration
        @pytest.mark.asyncio
        async def test_something(): ...

    Run only integration tests:  pytest -m integration
    Run only unit tests:         pytest -m 'not integration'
    """
    fn = pytest.mark.integration(fn)
    fn = _skipif_no_db(fn)
    return fn


@pytest.fixture(autouse=True)
async def cleanup_db_pool() -> AsyncGenerator[None, None]:
    """Force SQLAlchemy to dispose of the connection pool after each test.
    This prevents 'different event loop' errors when engines are reused across tests.
    """
    yield
    from src.core.database import engine

    await engine.dispose()


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def admin_client() -> AsyncGenerator[AsyncClient, None]:
    """Client authenticated through the real SQLAdmin login flow."""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=False
    ) as ac:
        response = await ac.post(
            "/admin/login",
            data={
                "username": settings.admin_username,
                "password": settings.admin_password,
            },
        )
        assert response.status_code in (200, 302, 303)
        yield ac
