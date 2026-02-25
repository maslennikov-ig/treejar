from __future__ import annotations

from typing import Any

from arq.connections import RedisSettings
from arq.cron import cron

from src.core.config import settings
from src.integrations.inventory.sync import sync_products_from_zoho


async def startup(ctx: dict[str, Any]) -> None:
    """Worker startup — initialize connections."""


async def shutdown(ctx: dict[str, Any]) -> None:
    """Worker shutdown — close connections."""


class WorkerSettings:
    functions: list[Any] = [sync_products_from_zoho]
    cron_jobs = [
        cron(sync_products_from_zoho, hour={0, 6, 12, 18}),
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
