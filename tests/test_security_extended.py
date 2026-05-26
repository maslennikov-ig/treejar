"""Extended security tests for Treejar AI Sales Bot.

Covers:
  1. No hardcoded secrets in source code (static analysis)
  2. RAG pipeline uses parameterized queries only (no f-string SQL)
  3. Admin panel requires authentication (302 redirect or login page)

Complements the existing tests/test_security.py which covers webhook
signature verification (verify_wazzup_webhook, compute_signature).
"""

from __future__ import annotations

import re
from collections.abc import Generator
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

# =============================================================================
# 1. No hardcoded secrets in source code
# =============================================================================


def test_no_hardcoded_secrets_in_source() -> None:
    """src/ must contain no hardcoded API keys, passwords, or bearer tokens."""
    src_dir = Path(__file__).parent.parent / "src"

    # Patterns that indicate hardcoded secrets (not env var references)
    secret_patterns = [
        re.compile(r"sk-[a-zA-Z0-9]{20,}"),  # OpenAI-style keys
        re.compile(r'password\s*=\s*"(?!").{8,}"'),  # password = "..."
        re.compile(r'api_key\s*=\s*"(?!").{8,}"'),  # api_key = "..."
        re.compile(r'token\s*=\s*"[a-zA-Z0-9_\-]{20,}"'),  # token = "long-thing"
    ]

    # Safe patterns that should NOT be flagged (env lookups, empty, placeholders)
    safe_indicators = [
        "os.getenv",
        "settings.",
        "environ",
        '""',
        "None",
        "your-",
        "change-me",
        "example",
        "placeholder",
        "test",
        "mock",
    ]

    offending: list[str] = []
    for py_file in src_dir.rglob("*.py"):
        with py_file.open() as f:
            for lineno, line in enumerate(f, 1):
                # Skip comments
                stripped = line.split("#")[0].strip()
                if not stripped:
                    continue
                # Skip lines referencing env vars or safe placeholders
                if any(safe in line for safe in safe_indicators):
                    continue
                for pattern in secret_patterns:
                    if pattern.search(stripped):
                        offending.append(
                            f"{py_file.relative_to(src_dir.parent)}:{lineno}: {line.rstrip()}"
                        )
                        break

    assert not offending, (
        f"Found potential hardcoded secrets in {len(offending)} lines:\n"
        + "\n".join(offending)
    )


# =============================================================================
# 2. RAG pipeline: no raw string interpolation in SQL
# =============================================================================


def test_rag_pipeline_no_raw_string_interpolation() -> None:
    """RAG pipeline must use ORM/parameterized queries, not f-string SQL."""
    pipeline_file = Path(__file__).parent.parent / "src" / "rag" / "pipeline.py"
    content = pipeline_file.read_text()

    # Patterns that indicate unsafe raw SQL construction
    dangerous_patterns = [
        (r'f".*SELECT.*\{', "f-string with SELECT"),
        (r'f".*WHERE.*\{', "f-string with WHERE"),
        (r'"SELECT\s+.*"\s*\+', "String concatenation with SELECT"),
        (r"%\s*\(.*user", "%-formatting with user input"),
    ]

    for pattern, description in dangerous_patterns:
        match = re.search(pattern, content, re.IGNORECASE)
        assert match is None, (
            f"Dangerous SQL pattern found in {pipeline_file.name}: {description}\n"
            f"Match: {match.group() if match else ''}"
        )

    # Verify that text() usage (raw SQL) uses named bind parameters (:param)
    # and not f-strings or string concatenation
    text_usages = re.findall(r'text\("""(.+?)"""', content, re.DOTALL)
    for sql_block in text_usages:
        # Must contain :param_name style bind parameters if it has WHERE clauses
        if "WHERE" in sql_block.upper():
            assert ":" in sql_block, (
                f"text() SQL block with WHERE should use :param binds:\n{sql_block[:200]}"
            )
            # Must NOT contain f-string interpolation inside the text()
            assert "{" not in sql_block, (
                f"text() SQL block should not contain f-string interpolation:\n{sql_block[:200]}"
            )


# =============================================================================
# 3. Admin panel requires authentication
# =============================================================================


@pytest.mark.asyncio
async def test_admin_panel_requires_authentication() -> None:
    """GET /admin/ must not expose data without authentication.

    Expects one of:
    - 302: redirect to login page
    - 401: unauthorized
    - 403: forbidden
    - 200: only if the page contains a login form (username/password fields)
    """
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/admin/", follow_redirects=False)

    allowed_statuses = {200, 302, 303, 307, 401, 403}
    assert response.status_code in allowed_statuses, (
        f"Admin panel returned unexpected status {response.status_code}"
    )

    # If 200 returned, the page must be a login form, not a data table
    if response.status_code == 200:
        body = response.text.lower()
        login_indicators = ["login", "username", "password", "sign in"]
        assert any(indicator in body for indicator in login_indicators), (
            "Admin returned 200 but no login form detected — data may be exposed!"
        )


@pytest.fixture
def restore_auth_settings() -> Generator[None, None, None]:
    from src.core.config import settings

    original_env = settings.app_env
    original_api_key = settings.api_key
    yield
    settings.app_env = original_env
    settings.api_key = original_api_key


@pytest.mark.asyncio
async def test_admin_and_dashboard_reject_internal_api_key_without_session(
    restore_auth_settings: None,
) -> None:
    from src.core.config import settings
    from src.main import app

    settings.app_env = "production"
    settings.api_key = "internal-key"

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        dashboard = await ac.get("/dashboard/", headers={"X-API-Key": "internal-key"})
        admin_api = await ac.get(
            "/api/v1/admin/metrics/", headers={"X-API-Key": "internal-key"}
        )

    assert dashboard.status_code == 401
    assert dashboard.json()["detail"] == "Admin authentication required"
    assert admin_api.status_code == 401
    assert admin_api.json()["detail"] == "Admin authentication required"


@pytest.mark.asyncio
async def test_product_sync_rejects_internal_api_key_without_admin_session(
    restore_auth_settings: None,
) -> None:
    from src.core.config import settings
    from src.main import app

    settings.app_env = "production"
    settings.api_key = "internal-key"
    app.state.arq_pool = AsyncMock()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        direct_sync = await ac.post(
            "/api/v1/products/sync",
            json={"source": "treejar"},
            headers={"X-API-Key": "internal-key"},
        )
        admin_sync = await ac.post(
            "/api/v1/admin/products/sync",
            json={"source": "treejar"},
            headers={"X-API-Key": "internal-key"},
        )

    assert direct_sync.status_code == 401
    assert direct_sync.json()["detail"] == "Admin authentication required"
    assert admin_sync.status_code == 401
    assert admin_sync.json()["detail"] == "Admin authentication required"
    app.state.arq_pool.enqueue_job.assert_not_awaited()


@pytest.mark.asyncio
async def test_conversation_routes_reject_missing_or_wrong_internal_api_key(
    restore_auth_settings: None,
) -> None:
    from src.core.config import settings
    from src.main import app

    settings.app_env = "production"
    settings.api_key = "internal-key"

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        missing = await ac.get("/api/v1/conversations/")
        wrong = await ac.get(
            "/api/v1/conversations/", headers={"X-API-Key": "wrong-key"}
        )

    assert missing.status_code == 403
    assert missing.json()["detail"] == "Invalid or missing API key"
    assert wrong.status_code == 403
    assert wrong.json()["detail"] == "Invalid or missing API key"


@pytest.mark.asyncio
async def test_wazzup_allowlist_blocks_disallowed_origin_without_queueing() -> None:
    import ipaddress

    from src.main import app

    app.state.redis = AsyncMock()
    app.state.arq_pool = AsyncMock()

    with patch(
        "src.api.v1.webhook._parse_allowed_networks",
        return_value=[ipaddress.ip_network("10.0.0.0/8")],
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/webhook/wazzup",
                json={"messages": []},
            )

    assert response.status_code == 403
    assert response.json() == {"error": "forbidden"}
    app.state.redis.rpush.assert_not_awaited()
    app.state.arq_pool.enqueue_job.assert_not_awaited()
