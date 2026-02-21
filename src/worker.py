from __future__ import annotations

from typing import Any

from arq.connections import RedisSettings

from src.core.config import settings


async def startup(ctx: dict[str, Any]) -> None:
    """Worker startup — initialize connections."""


async def shutdown(ctx: dict[str, Any]) -> None:
    """Worker shutdown — close connections."""


class WorkerSettings:
    functions: list[Any] = []  # Will be populated with task functions
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
