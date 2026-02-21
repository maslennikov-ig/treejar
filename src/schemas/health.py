from __future__ import annotations

from pydantic import BaseModel


class DependencyHealth(BaseModel):
    name: str
    status: str  # "ok" | "error" | "degraded"
    latency_ms: float | None = None
    message: str | None = None


class HealthCheckResponse(BaseModel):
    status: str
    version: str
    dependencies: dict[str, DependencyHealth]
