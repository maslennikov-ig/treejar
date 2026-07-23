"""Privacy-safe runtime collection, signal evaluation, and notification."""

from __future__ import annotations

import json
import logging
import secrets
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field
from sqlalchemy import func, select, text

from src.core.config import settings
from src.core.database import async_session_factory
from src.models.escalation import Escalation
from src.schemas.common import EscalationStatus
from src.services.notifications import send_telegram_message

logger = logging.getLogger(__name__)

INBOUND_BATCH_FAILURES_KEY = "wazzup:inbound:failures"
ZOHO_OAUTH_FAILURES_KEY = "zoho:oauth:failures"
_INBOUND_JOB_FUNCTION = "process_incoming_batch"
_LOOKBACK = timedelta(hours=1)
_STALE_ESCALATION_AGE = timedelta(days=30)
_RELEASE_CLAIM_SCRIPT = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
end
return 0
"""


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
    maintenance_heartbeat_missing: bool = False


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
    if snapshot.maintenance_heartbeat_missing:
        signals.append(
            _signal(
                code="maintenance_heartbeat_missing",
                severity="warning",
                value=1,
                threshold=1,
                source="Maintenance heartbeat",
                remediation="Verify the maintenance schedule and status-file path.",
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
    owner_token: str | None = None,
) -> str | None:
    """Claim a cooldown window before sending one external notification."""
    if cooldown_seconds <= 0:
        raise ValueError("cooldown_seconds must be positive")
    token = owner_token or secrets.token_hex(16)
    claimed = await redis.set(
        f"runtime-alert:{code}",
        token,
        ex=cooldown_seconds,
        nx=True,
    )
    return token if claimed else None


async def release_signal_delivery(
    redis: Any,
    *,
    code: str,
    owner_token: str,
) -> bool:
    """Release a failed delivery claim only while this caller still owns it."""
    released = await redis.eval(
        _RELEASE_CLAIM_SCRIPT,
        1,
        f"runtime-alert:{code}",
        owner_token,
    )
    return bool(released)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _decode_json_record(raw: Any) -> dict[str, Any] | None:
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="replace")
    if not isinstance(raw, str):
        return None
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _count_recent_oauth_failures(
    records: list[Any],
    *,
    cutoff: datetime,
) -> int:
    failures = 0
    for raw in records:
        payload = _decode_json_record(raw)
        if payload is None:
            continue
        failed_at_raw = payload.get("failed_at")
        if not isinstance(failed_at_raw, str):
            continue
        try:
            failed_at = _as_utc(datetime.fromisoformat(failed_at_raw))
        except ValueError:
            continue
        if failed_at >= cutoff:
            failures += 1
    return failures


def _maintenance_heartbeat(
    path: Path,
    *,
    observed_at: datetime,
) -> tuple[float | None, bool | None, bool]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        status = payload["status"]
        finished_at_epoch = payload["finished_at_epoch"]
        if status not in {"success", "failure"}:
            raise ValueError("unsupported status")
        if isinstance(finished_at_epoch, bool):
            raise ValueError("invalid timestamp")
        finished_at = datetime.fromtimestamp(int(finished_at_epoch), tz=UTC)
    except FileNotFoundError:
        return None, None, True
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
        return None, False, False

    age_seconds = max(0.0, (observed_at - finished_at).total_seconds())
    return age_seconds, status == "success", False


async def collect_runtime_snapshot(
    redis: Any,
    db: Any,
    *,
    observed_at: datetime | None = None,
    maintenance_status_path: Path | None = None,
) -> RuntimeSnapshot:
    """Collect bounded counters from Redis, ARQ, PostgreSQL, and maintenance."""
    current = _as_utc(observed_at or datetime.now(UTC))
    cutoff = current - _LOOKBACK
    dependency_failures = 0

    try:
        await redis.ping()
    except Exception:
        dependency_failures += 1
        logger.exception("Runtime monitoring Redis health probe failed")

    try:
        job_results = await redis.all_job_results()
    except Exception:
        job_results = []
        logger.exception("Runtime monitoring could not read ARQ results")
    failed_jobs = sum(
        1
        for result in job_results
        if not result.success and _as_utc(result.finish_time) >= cutoff
    )

    try:
        failure_records = await redis.lrange(ZOHO_OAUTH_FAILURES_KEY, 0, -1)
    except Exception:
        failure_records = []
        logger.exception("Runtime monitoring could not read OAuth failure counters")
    oauth_failures = _count_recent_oauth_failures(
        list(failure_records),
        cutoff=cutoff,
    )

    try:
        queued_jobs = await redis.queued_jobs()
    except Exception:
        queued_jobs = []
        logger.exception("Runtime monitoring could not read ARQ queue metadata")
    inbound_jobs = [
        job
        for job in queued_jobs
        if job.function.rsplit(".", maxsplit=1)[-1] == _INBOUND_JOB_FUNCTION
    ]
    queue_depth = len(inbound_jobs)
    oldest_queue_age = (
        max(
            0.0,
            (
                current - min(_as_utc(job.enqueue_time) for job in inbound_jobs)
            ).total_seconds(),
        )
        if inbound_jobs
        else None
    )

    database_healthy = True
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        database_healthy = False
        dependency_failures += 1
        with suppress(Exception):
            await db.rollback()
        logger.exception("Runtime monitoring database health probe failed")

    stale_pending = 0
    if database_healthy:
        try:
            result = await db.execute(
                select(func.count(Escalation.id)).where(
                    Escalation.status == EscalationStatus.PENDING.value,
                    Escalation.created_at <= current - _STALE_ESCALATION_AGE,
                )
            )
            stale_pending = int(result.scalar_one())
        except Exception:
            dependency_failures += 1
            with suppress(Exception):
                await db.rollback()
            logger.exception("Runtime monitoring escalation query failed")

    heartbeat_path = maintenance_status_path or Path(
        settings.runtime_monitoring_maintenance_status_path
    )
    maintenance_age, maintenance_succeeded, heartbeat_missing = _maintenance_heartbeat(
        heartbeat_path, observed_at=current
    )

    return RuntimeSnapshot(
        observed_at=current,
        failed_jobs_last_hour=failed_jobs,
        oauth_failures_last_hour=oauth_failures,
        queue_depth=queue_depth,
        oldest_queue_age_seconds=oldest_queue_age,
        stale_pending_escalations=stale_pending,
        health_dependency_failures=dependency_failures,
        maintenance_age_seconds=maintenance_age,
        maintenance_last_run_succeeded=maintenance_succeeded,
        maintenance_heartbeat_missing=heartbeat_missing,
    )


def _format_runtime_signal(signal: RuntimeSignal) -> str:
    return (
        "⚠️ <b>Noor runtime signal</b>\n\n"
        f"<b>Code:</b> <code>{signal.code}</code>\n"
        f"<b>Severity:</b> {signal.severity}\n"
        f"<b>Value:</b> {signal.value:g}\n"
        f"<b>Threshold:</b> {signal.threshold:g}\n"
        f"<b>Source:</b> {signal.source}\n"
        f"<b>Owner:</b> {signal.owner}\n"
        f"<b>Action:</b> {signal.remediation}"
    )


async def run_runtime_monitoring(ctx: dict[str, Any]) -> list[RuntimeSignal]:
    """ARQ job that logs all signals and optionally sends deduplicated Telegram."""
    if not settings.runtime_monitoring_enabled:
        return []

    redis = ctx["redis"]
    async with async_session_factory() as db:
        snapshot = await collect_runtime_snapshot(redis, db)
    signals = evaluate_runtime_snapshot(snapshot, RuntimeThresholds())

    for signal in signals:
        log_method = logger.error if signal.severity == "critical" else logger.warning
        log_method(
            "Runtime signal code=%s severity=%s value=%s threshold=%s source=%s",
            signal.code,
            signal.severity,
            signal.value,
            signal.threshold,
            signal.source,
        )
        if not settings.runtime_monitoring_telegram_enabled:
            continue
        if (
            not settings.telegram_bot_token.strip()
            or not str(settings.telegram_chat_id).strip()
        ):
            continue
        owner_token = await claim_signal_delivery(
            redis,
            code=signal.code,
            cooldown_seconds=settings.runtime_monitoring_alert_cooldown_seconds,
        )
        if owner_token is None:
            continue
        delivered = await send_telegram_message(_format_runtime_signal(signal))
        if not delivered:
            await release_signal_delivery(
                redis,
                code=signal.code,
                owner_token=owner_token,
            )

    return signals
