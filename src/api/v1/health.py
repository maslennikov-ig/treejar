from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends, Request
from redis.asyncio import Redis

from src.api.deps import get_redis
from src.schemas import DependencyHealth, HealthCheckResponse

router = APIRouter()


@router.get("/debug/redis")
async def debug_redis(request: Request) -> dict[str, Any]:
    redis = request.app.state.redis
    queue_len = await redis.llen("wazzup:incoming:+971500000004")
    raw_msgs = await redis.lrange("wazzup:incoming:+971500000004", 0, -1)
    return {"len": queue_len, "msgs": [m.decode("utf-8") for m in raw_msgs]}


@router.get("/health", response_model=HealthCheckResponse)
async def health_check(
    redis: Redis = Depends(get_redis),
) -> HealthCheckResponse:
    """Check service health and dependency status."""
    dependencies: dict[str, DependencyHealth] = {}

    # Check Redis
    try:
        start = time.monotonic()
        await redis.ping()
        latency = (time.monotonic() - start) * 1000
        dependencies["redis"] = DependencyHealth(
            name="redis",
            status="ok",
            latency_ms=round(latency, 2),
        )
    except Exception as exc:
        dependencies["redis"] = DependencyHealth(
            name="redis",
            status="error",
            message=str(exc),
        )

    # Determine overall status
    statuses = [dep.status for dep in dependencies.values()]
    if all(s == "ok" for s in statuses):
        overall = "ok"
    elif any(s == "error" for s in statuses):
        overall = "degraded"
    else:
        overall = "degraded"

    return HealthCheckResponse(
        status=overall,
        version="0.1.0",
        dependencies=dependencies,
    )
