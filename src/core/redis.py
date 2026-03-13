from __future__ import annotations

from collections.abc import AsyncGenerator

import redis.asyncio as aioredis

from src.core.config import settings

redis_client: aioredis.Redis = aioredis.from_url(  # type: ignore[no-untyped-call]
    settings.redis_url,
    decode_responses=True,
    # Connection pool settings: prevent exhaustion under load & hang prevention.
    max_connections=20,
    socket_timeout=5.0,
    socket_connect_timeout=5.0,
    retry_on_timeout=True,
)


async def get_redis() -> AsyncGenerator[aioredis.Redis]:
    """FastAPI dependency — use with Depends(get_redis)."""
    yield redis_client


def get_redis_client() -> aioredis.Redis:
    """Direct accessor for non-FastAPI context (ARQ jobs, cron, scripts).

    Use this instead of get_redis() when not inside a FastAPI request lifecycle.
    """
    return redis_client

