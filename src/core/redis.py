from __future__ import annotations

from collections.abc import AsyncGenerator

import redis.asyncio as aioredis

from src.core.config import settings

redis_client: aioredis.Redis = aioredis.from_url(  # type: ignore[no-untyped-call]
    settings.redis_url,
    decode_responses=True,
)


async def get_redis() -> AsyncGenerator[aioredis.Redis]:
    yield redis_client
