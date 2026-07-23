from __future__ import annotations

import time
from contextlib import suppress
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version

from fastapi import APIRouter, Depends, Response, status
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db, get_redis
from src.schemas import DependencyHealth, HealthCheckResponse

router = APIRouter()

_PACKAGE_NAME = "treejar-ai-bot"
_FALLBACK_VERSION = "0.0.0+unknown"


def resolve_app_version() -> str:
    """Return the installed application version or a stable source-tree fallback."""
    try:
        return package_version(_PACKAGE_NAME)
    except PackageNotFoundError:
        return _FALLBACK_VERSION


@router.get("/health", response_model=HealthCheckResponse)
async def health_check(
    response: Response,
    redis: Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_db),
) -> HealthCheckResponse:
    """Check service health and dependency status."""
    dependencies: dict[str, DependencyHealth] = {}

    try:
        start = time.monotonic()
        await redis.ping()
        latency = (time.monotonic() - start) * 1000
        dependencies["redis"] = DependencyHealth(
            name="redis",
            status="ok",
            latency_ms=round(latency, 2),
        )
    except Exception:
        dependencies["redis"] = DependencyHealth(
            name="redis",
            status="error",
            message="unavailable",
        )

    try:
        start = time.monotonic()
        await db.execute(text("SELECT 1"))
        latency = (time.monotonic() - start) * 1000
        dependencies["database"] = DependencyHealth(
            name="database",
            status="ok",
            latency_ms=round(latency, 2),
        )
    except Exception:
        # Clear any failed transaction state so the shared dependency can exit cleanly.
        with suppress(Exception):
            await db.rollback()
        dependencies["database"] = DependencyHealth(
            name="database",
            status="error",
            message="unavailable",
        )

    if all(dependency.status == "ok" for dependency in dependencies.values()):
        overall = "ok"
    else:
        overall = "degraded"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthCheckResponse(
        status=overall,
        version=resolve_app_version(),
        dependencies=dependencies,
    )
