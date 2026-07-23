"""Privacy-safe runtime signal evaluation and notification deduplication."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class RuntimeSnapshot(BaseModel):
    """Aggregate operational counters without customer or request payloads."""

    observed_at: datetime
    failed_jobs_last_hour: int = Field(ge=0)
    oauth_failures_last_hour: int = Field(ge=0)
    queue_depth: int = Field(ge=0)
    oldest_queue_age_seconds: float | None = Field(default=None, ge=0)
    stale_pending_escalations: int = Field(ge=0)
    health_dependency_failures: int = Field(ge=0)
    maintenance_age_seconds: float | None = Field(default=None, ge=0)
    maintenance_last_run_succeeded: bool | None = None


class RuntimeThresholds(BaseModel):
    """Conservative defaults suitable for the existing Noor workload."""

    failed_jobs_last_hour: int = Field(default=1, ge=1)
    oauth_failures_last_hour: int = Field(default=1, ge=1)
    queue_depth: int = Field(default=25, ge=1)
    oldest_queue_age_seconds: float = Field(default=120, gt=0)
    stale_pending_escalations: int = Field(default=1, ge=1)
    health_dependency_failures: int = Field(default=1, ge=1)
    maintenance_age_seconds: float = Field(default=93_600, gt=0)


class RuntimeSignal(BaseModel):
    """Actionable monitoring signal containing operational metadata only."""

    code: str
    severity: Literal["warning", "critical"]
    value: float
    threshold: float
    source: str
    owner: str
    remediation: str


def _signal(
    *,
    code: str,
    severity: Literal["warning", "critical"],
    value: int | float,
    threshold: int | float,
    source: str,
    remediation: str,
) -> RuntimeSignal:
    return RuntimeSignal(
        code=code,
        severity=severity,
        value=float(value),
        threshold=float(threshold),
        source=source,
        owner="Noor operations",
        remediation=remediation,
    )


def evaluate_runtime_snapshot(
    snapshot: RuntimeSnapshot,
    thresholds: RuntimeThresholds,
) -> list[RuntimeSignal]:
    """Return deterministic signals for threshold breaches."""
    signals: list[RuntimeSignal] = []
    if snapshot.failed_jobs_last_hour >= thresholds.failed_jobs_last_hour:
        signals.append(
            _signal(
                code="arq_jobs_failed",
                severity="critical",
                value=snapshot.failed_jobs_last_hour,
                threshold=thresholds.failed_jobs_last_hour,
                source="ARQ result metadata",
                remediation="Inspect failed jobs and retry only after fixing the cause.",
            )
        )
    if snapshot.oauth_failures_last_hour >= thresholds.oauth_failures_last_hour:
        signals.append(
            _signal(
                code="zoho_oauth_failed",
                severity="critical",
                value=snapshot.oauth_failures_last_hour,
                threshold=thresholds.oauth_failures_last_hour,
                source="Zoho OAuth failure counter",
                remediation="Check the sanitized OAuth error class and configured account.",
            )
        )
    if snapshot.queue_depth >= thresholds.queue_depth:
        signals.append(
            _signal(
                code="inbound_queue_backlog",
                severity="warning",
                value=snapshot.queue_depth,
                threshold=thresholds.queue_depth,
                source="ARQ queue metadata",
                remediation="Check worker capacity and the oldest queued job.",
            )
        )
    if (
        snapshot.oldest_queue_age_seconds is not None
        and snapshot.oldest_queue_age_seconds >= thresholds.oldest_queue_age_seconds
    ):
        signals.append(
            _signal(
                code="inbound_queue_stalled",
                severity="critical",
                value=snapshot.oldest_queue_age_seconds,
                threshold=thresholds.oldest_queue_age_seconds,
                source="ARQ queue metadata",
                remediation="Check worker health before replaying queued work.",
            )
        )
    if snapshot.stale_pending_escalations >= thresholds.stale_pending_escalations:
        signals.append(
            _signal(
                code="pending_escalations_stale",
                severity="warning",
                value=snapshot.stale_pending_escalations,
                threshold=thresholds.stale_pending_escalations,
                source="Escalation state audit",
                remediation="Run the read-only escalation audit and review dispositions.",
            )
        )
    if snapshot.health_dependency_failures >= thresholds.health_dependency_failures:
        signals.append(
            _signal(
                code="health_dependency_failed",
                severity="critical",
                value=snapshot.health_dependency_failures,
                threshold=thresholds.health_dependency_failures,
                source="Application health probe",
                remediation="Inspect Redis and database health before restarting services.",
            )
        )
    if snapshot.maintenance_last_run_succeeded is False:
        signals.append(
            _signal(
                code="maintenance_failed",
                severity="warning",
                value=1,
                threshold=1,
                source="Maintenance heartbeat",
                remediation="Inspect the maintenance log and rerun in dry-run mode.",
            )
        )
    if (
        snapshot.maintenance_age_seconds is not None
        and snapshot.maintenance_age_seconds >= thresholds.maintenance_age_seconds
    ):
        signals.append(
            _signal(
                code="maintenance_stale",
                severity="warning",
                value=snapshot.maintenance_age_seconds,
                threshold=thresholds.maintenance_age_seconds,
                source="Maintenance heartbeat",
                remediation="Verify the installed schedule and its last-run record.",
            )
        )
    return signals


async def claim_signal_delivery(
    redis: Any,
    *,
    code: str,
    cooldown_seconds: int,
) -> bool:
    """Claim a cooldown window before sending one external notification."""
    if cooldown_seconds <= 0:
        raise ValueError("cooldown_seconds must be positive")
    claimed = await redis.set(
        f"runtime-alert:{code}",
        "1",
        ex=cooldown_seconds,
        nx=True,
    )
    return bool(claimed)
