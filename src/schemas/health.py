from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class DependencyHealth(BaseModel):
    name: str
    status: Literal["ok", "error", "degraded"]
    latency_ms: float | None = None
    message: str | None = None


class HealthCheckResponse(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    dependencies: dict[str, DependencyHealth]
