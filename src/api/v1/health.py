from __future__ import annotations

import re
import time
from contextlib import suppress
from functools import lru_cache
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version
from pathlib import Path

from fastapi import APIRouter, Depends, Response, status
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db, get_redis
from src.schemas import DependencyHealth, HealthCheckResponse
from src.schemas.health import RELEASE_SHA_PATTERN

router = APIRouter()

_PACKAGE_NAME = "treejar-ai-bot"
_FALLBACK_VERSION = "0.0.0+unknown"
_FALLBACK_RELEASE_SHA = "unknown"
_RELEASE_SHA_PATH = Path(__file__).resolve().parents[3] / ".release-sha"
# The same shape the response schema enforces, so the resolver and the model
# can never disagree about what a release SHA is.
_RELEASE_SHA_RE = re.compile(RELEASE_SHA_PATTERN)


def resolve_app_version() -> str:
    """Return the installed application version or a stable source-tree fallback."""
    try:
        return package_version(_PACKAGE_NAME)
    except PackageNotFoundError:
        return _FALLBACK_VERSION


@lru_cache(maxsize=1)
def resolve_release_sha() -> str:
    """Return the deployed release SHA without making health depend on metadata.

    Resolved once per process and reused. `tj-hls5`: this was a blocking file
    read inside an async handler on every poll, and the deploy loop in
    `scripts/vps-deploy.sh` polls up to twenty times every three seconds while
    monitoring polls continuously. The value cannot change without a container
    rebuild, so a second read can only ever return the first answer --
    including the fallback, which is an answer and not a retry.

    `ValueError` is caught beside `OSError` because `read_text` decodes: a
    truncated or non-UTF-8 file raises `UnicodeDecodeError`, which is a
    `ValueError` and not an `OSError`. Uncaught it returned 500, and the deploy
    health loop retries twenty times before failing the release -- a metadata
    file must never be able to do that.

    `tj-izkn`: whatever comes back is a commit SHA or it is "unknown". The
    endpoint is public and unauthenticated, and `.strip()` alone let a
    200,000-byte file through whole and left a second line inside the value.
    Anything the shape does not admit reads "unknown", which is the honest
    answer for a file that does not hold a release SHA.
    """
    try:
        candidate = _RELEASE_SHA_PATH.read_text(encoding="utf-8").strip()
    except (OSError, ValueError):
        return _FALLBACK_RELEASE_SHA
    if not _RELEASE_SHA_RE.fullmatch(candidate):
        return _FALLBACK_RELEASE_SHA
    return candidate


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
        release_sha=resolve_release_sha(),
        dependencies=dependencies,
    )
