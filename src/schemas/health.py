from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# `tj-izkn`. `/api/v1/health` is public and unauthenticated, and the value
# comes from a file inside the container. A commit SHA or the literal
# "unknown", nothing else and nothing longer: the response has no reason to be
# unbounded, whatever a future caller hands the model.
RELEASE_SHA_PATTERN = r"^(?:unknown|[0-9a-f]{7,40})$"


class DependencyHealth(BaseModel):
    name: str
    status: Literal["ok", "error", "degraded"]
    latency_ms: float | None = None
    message: str | None = None


class HealthCheckResponse(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    release_sha: str = Field(pattern=RELEASE_SHA_PATTERN, max_length=40)
    dependencies: dict[str, DependencyHealth]
