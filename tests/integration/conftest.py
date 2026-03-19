"""Fixtures for integration tests that use real external services.

Credentials are loaded from .env or .env.dev (NOT hardcoded).
All DB-touching tests use a nested transaction with rollback → idempotent.
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

import pytest
from dotenv import dotenv_values

# ---------------------------------------------------------------------------
# Known test contact in Zoho CRM (do NOT delete from CRM!)
# ---------------------------------------------------------------------------

TEST_CONTACT_PHONE = "+971000000001"
TEST_CONTACT_CRM_ID = "559571000034673035"
TEST_CONTACT_NAME = "Integration TestBot"
TEST_CONTACT_EMAIL = "integration-test@treejar.test"
TEST_CONTACT_SEGMENT = ["Wholesale"]  # multi-select list — exact Zoho type

# ---------------------------------------------------------------------------
# Load real credentials from .env / .env.dev (conftest.py sets fake env vars
# at import time, so we must read the file directly)
# ---------------------------------------------------------------------------

_project_root = Path(__file__).resolve().parents[2]
_env_path = _project_root / ".env"
_env_dev_path = _project_root / ".env.dev"

# Prefer .env, fallback to .env.dev
_env = dotenv_values(_env_path) if _env_path.exists() else {}
if not _env:
    _env = dotenv_values(_env_dev_path) if _env_dev_path.exists() else {}


def _get(key: str) -> str:
    """Get env var from dotenv file (not os.environ, which has fake test values)."""
    return _env.get(key, "") or ""


# ---------------------------------------------------------------------------
# Skip conditions
# ---------------------------------------------------------------------------

_has_zoho_crm = bool(
    _get("ZOHO_CRM_CLIENT_ID")
    and _get("ZOHO_CRM_CLIENT_SECRET")
    and _get("ZOHO_CRM_REFRESH_TOKEN")
)

_has_zoho_inventory = bool(
    _get("ZOHO_INVENTORY_CLIENT_ID")
    and _get("ZOHO_INVENTORY_CLIENT_SECRET")
    and _get("ZOHO_INVENTORY_REFRESH_TOKEN")
    and _get("ZOHO_INVENTORY_ORG_ID")
)

_has_openrouter = bool(_get("OPENROUTER_API_KEY"))

_has_db = bool(_get("DATABASE_URL"))

_has_redis = bool(_get("REDIS_URL"))

skip_no_zoho_crm = pytest.mark.skipif(
    not _has_zoho_crm, reason="Zoho CRM credentials not found in .env"
)
skip_no_zoho_inventory = pytest.mark.skipif(
    not _has_zoho_inventory, reason="Zoho Inventory credentials not found in .env"
)
skip_no_openrouter = pytest.mark.skipif(
    not _has_openrouter, reason="OPENROUTER_API_KEY not found in .env"
)
skip_no_db = pytest.mark.skipif(
    not _has_db, reason="DATABASE_URL not found in .env"
)
skip_no_redis = pytest.mark.skipif(
    not _has_redis, reason="REDIS_URL not found in .env"
)

_has_wazzup = bool(_get("WAZZUP_API_KEY") and _get("WAZZUP_API_URL"))

skip_no_wazzup = pytest.mark.skipif(
    not _has_wazzup, reason="Wazzup credentials not found in .env"
)

# Phone number of the user for real WhatsApp delivery tests
USER_WHATSAPP_PHONE = "79262810921"

# Active Wazzup channel ID (Treejar, +971551220665)
WAZZUP_CHANNEL_ID = "b49b1b9d-757f-4104-b56d-8f43d62cc515"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def live_redis() -> AsyncGenerator[Any, None]:
    """Real Redis connection using credentials from .env."""
    import redis.asyncio as aioredis

    url = _get("REDIS_URL") or "redis://localhost:6379/0"
    client = aioredis.from_url(url, decode_responses=True)  # type: ignore
    try:
        await client.ping()
        yield client
    finally:
        await client.aclose()


@pytest.fixture
async def live_db_session() -> AsyncGenerator[Any, None]:
    """Real async DB session wrapped in a nested transaction for rollback.

    Uses begin_nested() so that test data never persists.
    """
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    db_url = _get("DATABASE_URL")
    if not db_url:
        pytest.skip("DATABASE_URL not available")

    engine = create_async_engine(db_url, echo=False)
    async with engine.connect() as conn:
        txn = await conn.begin()
        session = AsyncSession(bind=conn, expire_on_commit=False)
        # Nested txn so that session.commit() inside tests doesn't actually commit
        await conn.begin_nested()

        yield session

        # Rollback everything — test data is never persisted
        await session.close()
        await txn.rollback()
    await engine.dispose()


@pytest.fixture
async def zoho_crm_client(live_redis: Any) -> AsyncGenerator[Any, None]:
    """Real Zoho CRM client with real OAuth token."""
    from src.integrations.crm.zoho_crm import ZohoCRMClient

    # Temporarily set real credentials in os.environ so Settings picks them up
    real_env = {
        "ZOHO_CRM_CLIENT_ID": _get("ZOHO_CRM_CLIENT_ID"),
        "ZOHO_CRM_CLIENT_SECRET": _get("ZOHO_CRM_CLIENT_SECRET"),
        "ZOHO_CRM_REFRESH_TOKEN": _get("ZOHO_CRM_REFRESH_TOKEN"),
        "ZOHO_CRM_API_URL": _get("ZOHO_CRM_API_URL") or "https://www.zohoapis.eu/crm/v7",
        "ZOHO_CRM_ACCOUNTS_URL": _get("ZOHO_CRM_ACCOUNTS_URL") or "https://accounts.zoho.eu",
    }
    saved = {}
    for k, v in real_env.items():
        saved[k] = os.environ.get(k)
        if v is not None:
            os.environ[k] = str(v)

    try:
        client = ZohoCRMClient(redis_client=live_redis)
        yield client
        await client.close()
    finally:
        for saved_k, saved_v in saved.items():
            if saved_v is None:
                os.environ.pop(saved_k, None)
            else:
                os.environ[saved_k] = str(saved_v)


@pytest.fixture
async def zoho_inventory_client(live_redis: Any) -> AsyncGenerator[Any, None]:
    """Real Zoho Inventory client with real OAuth token."""
    from src.integrations.inventory.zoho_inventory import ZohoInventoryClient

    real_env = {
        "ZOHO_INVENTORY_CLIENT_ID": _get("ZOHO_INVENTORY_CLIENT_ID"),
        "ZOHO_INVENTORY_CLIENT_SECRET": _get("ZOHO_INVENTORY_CLIENT_SECRET"),
        "ZOHO_INVENTORY_REFRESH_TOKEN": _get("ZOHO_INVENTORY_REFRESH_TOKEN"),
        "ZOHO_INVENTORY_API_URL": _get("ZOHO_INVENTORY_API_URL") or "https://www.zohoapis.eu/inventory/v1",
        "ZOHO_INVENTORY_ORG_ID": _get("ZOHO_INVENTORY_ORG_ID"),
    }
    saved = {}
    for k, v in real_env.items():
        saved[k] = os.environ.get(k)
        if v is not None:
            os.environ[k] = str(v)

    try:
        client = ZohoInventoryClient(redis_client=live_redis)
        yield client
        await client.close()
    finally:
        for saved_k, saved_v in saved.items():
            if saved_v is None:
                os.environ.pop(saved_k, None)
            else:
                os.environ[saved_k] = str(saved_v)


@pytest.fixture
async def wazzup_client() -> AsyncGenerator[Any, None]:
    """Real Wazzup messaging provider with real credentials.

    Built manually to bypass cached settings singleton that may
    contain docker aliases instead of real hostnames.
    """
    import httpx

    from src.integrations.messaging.wazzup import WazzupProvider

    api_key = _get("WAZZUP_API_KEY")
    api_url = _get("WAZZUP_API_URL") or "https://api.wazzup24.com/v3"

    client = WazzupProvider.__new__(WazzupProvider)
    client.base_url = api_url
    client.api_key = api_key
    client.channel_id = WAZZUP_CHANNEL_ID
    client.client = httpx.AsyncClient(
        base_url=api_url,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=httpx.Timeout(30.0),
    )

    try:
        yield client
    finally:
        await client.close()
