from __future__ import annotations

import asyncio
import os

os.environ["OPENROUTER_API_KEY"] = "test-key"
os.environ["WAZZUP_API_KEY"] = "fake-wazzup-key"
os.environ["WAZZUP_API_URL"] = "http://fake-wazzup-url"

# tj-0ikw. Every other outbound credential was already neutralised here and
# Telegram was not, so a test run in a checkout that has a populated `.env`
# sent real alerts to the owner's phone. It happened on 2026-08-06: four
# "LLM final failure" messages naming `mock-model`, from the suite, at 20:53.
#
# `TelegramClient.is_configured` is just `bool(bot_token)`, so emptying the
# token stops the send at the client while leaving every code path above it
# exercised exactly as before.
os.environ["TELEGRAM_BOT_TOKEN"] = ""
os.environ["TELEGRAM_CHAT_ID"] = ""

from collections.abc import AsyncGenerator, Generator

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
def prose_rewrite_unavailable() -> Generator[None, None, None]:
    """No cosmetic rewrite in unit tests unless a test asks for one.

    The verified-prose rewrite runs on its own agent, away from the product
    system prompt, so patching `sales_agent.run` does not reach it. Left
    unpatched it would make a real network call from every route test. The
    default here is that the rewrite is unavailable, which is exactly the
    fallback the routes are built for: the route's own text ships. Tests that
    exercise the rewrite patch `prose_agent.run` themselves.
    """

    from unittest.mock import AsyncMock, patch

    with patch(
        "src.llm.engine.prose_agent.run",
        new_callable=AsyncMock,
        side_effect=TimeoutError,
    ):
        yield


@pytest.fixture(autouse=True)
def repair_judge_is_local() -> Generator[None, None, None]:
    """Keep route tests on a local second-vendor stand-in.

    Route tests patch the primary sales model and assert the rest of the turn.
    A removing guard now invokes a separate model, so leaving that collaborator
    live would turn ordinary unit tests into external calls. Dedicated repair-
    judge tests pass their own runner and cover all three decisions explicitly.
    """

    from unittest.mock import patch

    from src.llm.repair_judge import (
        RepairJudgeDecision,
        RepairJudgeProviderResult,
        RepairJudgeRequest,
    )

    async def correct_with_candidate(
        request: RepairJudgeRequest,
    ) -> RepairJudgeProviderResult:
        corrected_text = next(
            (
                flag.candidate
                for flag in reversed(request.flags)
                if flag.candidate is not None
            ),
            request.reply,
        )
        return RepairJudgeProviderResult(
            decision=RepairJudgeDecision(
                answer="correct",
                corrected_text=corrected_text,
                rationale="Local route-test stand-in accepts the guarded candidate.",
            ),
            model="test/repair-judge",
            prompt_tokens=0,
            completion_tokens=0,
            cost_usd=0.0,
        )

    with patch("src.llm.repair_judge.run_repair_judge", new=correct_with_candidate):
        yield


@pytest.fixture(autouse=True)
def cleanup_db_pool() -> Generator[None, None, None]:
    """Force SQLAlchemy to dispose of the connection pool after each test.
    This prevents 'different event loop' errors when engines are reused across tests.
    """
    yield
    from src.core.database import engine

    asyncio.run(engine.dispose())


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
