from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.services.runtime_monitoring import (
    ZOHO_OAUTH_FAILURES_KEY,
    RuntimeSnapshot,
    RuntimeThresholds,
    claim_signal_delivery,
    collect_runtime_snapshot,
    evaluate_runtime_snapshot,
    run_runtime_monitoring,
)

NOW = datetime(2026, 7, 23, 12, 0, tzinfo=UTC)


def test_healthy_runtime_snapshot_has_no_alerts() -> None:
    snapshot = RuntimeSnapshot(
        observed_at=NOW,
        failed_jobs_last_hour=0,
        oauth_failures_last_hour=0,
        queue_depth=2,
        oldest_queue_age_seconds=8,
        stale_pending_escalations=0,
        health_dependency_failures=0,
        maintenance_age_seconds=3600,
        maintenance_last_run_succeeded=True,
        maintenance_heartbeat_missing=False,
    )

    assert evaluate_runtime_snapshot(snapshot, RuntimeThresholds()) == []


def test_runtime_snapshot_emits_each_actionable_signal_without_pii() -> None:
    snapshot = RuntimeSnapshot(
        observed_at=NOW,
        failed_jobs_last_hour=2,
        oauth_failures_last_hour=1,
        queue_depth=30,
        oldest_queue_age_seconds=180,
        stale_pending_escalations=3,
        health_dependency_failures=1,
        maintenance_age_seconds=100_000,
        maintenance_last_run_succeeded=False,
        maintenance_heartbeat_missing=False,
    )

    signals = evaluate_runtime_snapshot(snapshot, RuntimeThresholds())

    assert {signal.code for signal in signals} == {
        "arq_jobs_failed",
        "zoho_oauth_failed",
        "inbound_queue_backlog",
        "inbound_queue_stalled",
        "pending_escalations_stale",
        "health_dependency_failed",
        "maintenance_failed",
        "maintenance_stale",
    }
    serialized = " ".join(signal.model_dump_json() for signal in signals)
    assert "phone" not in serialized
    assert "message" not in serialized
    assert "token" not in serialized
    assert "secret" not in serialized


def test_missing_maintenance_heartbeat_is_actionable() -> None:
    snapshot = RuntimeSnapshot(
        observed_at=NOW,
        failed_jobs_last_hour=0,
        oauth_failures_last_hour=0,
        queue_depth=0,
        oldest_queue_age_seconds=None,
        stale_pending_escalations=0,
        health_dependency_failures=0,
        maintenance_age_seconds=None,
        maintenance_last_run_succeeded=None,
        maintenance_heartbeat_missing=True,
    )

    signals = evaluate_runtime_snapshot(snapshot, RuntimeThresholds())

    assert [signal.code for signal in signals] == ["maintenance_heartbeat_missing"]


@pytest.mark.asyncio
async def test_signal_delivery_claim_deduplicates_by_code() -> None:
    redis = AsyncMock()
    redis.set.side_effect = [True, None]

    first = await claim_signal_delivery(
        redis,
        code="inbound_queue_stalled",
        cooldown_seconds=1800,
    )
    second = await claim_signal_delivery(
        redis,
        code="inbound_queue_stalled",
        cooldown_seconds=1800,
    )

    assert first is True
    assert second is False
    redis.set.assert_awaited_with(
        "runtime-alert:inbound_queue_stalled",
        "1",
        ex=1800,
        nx=True,
    )


class _ScalarResult:
    def __init__(self, value: int) -> None:
        self.value = value

    def scalar_one(self) -> int:
        return self.value


@pytest.mark.asyncio
async def test_collect_runtime_snapshot_reads_real_sources_without_payloads(
    tmp_path: Path,
) -> None:
    redis = AsyncMock()
    redis.ping.return_value = True
    redis.all_job_results.return_value = [
        SimpleNamespace(
            success=False,
            finish_time=datetime(2026, 7, 23, 11, 30, tzinfo=UTC),
        ),
        SimpleNamespace(
            success=False,
            finish_time=datetime(2026, 7, 23, 10, 30, tzinfo=UTC),
        ),
    ]
    redis.queued_jobs.return_value = [
        SimpleNamespace(
            function="process_incoming_batch",
            enqueue_time=datetime(2026, 7, 23, 11, 57, tzinfo=UTC),
        ),
        SimpleNamespace(
            function="run_daily_summary",
            enqueue_time=datetime(2026, 7, 23, 11, 0, tzinfo=UTC),
        ),
    ]
    redis.lrange.return_value = [
        json.dumps(
            {
                "batch_id": "safe-id",
                "error_kind": "transport",
                "failed_at": "2026-07-23T11:45:00+00:00",
            }
        ),
        json.dumps(
            {
                "batch_id": "old-id",
                "error_kind": "transport",
                "failed_at": "2026-07-23T09:00:00+00:00",
            }
        ),
    ]
    db = AsyncMock()
    db.execute.side_effect = [SimpleNamespace(), _ScalarResult(4)]
    heartbeat = tmp_path / "maintenance.status"
    heartbeat.write_text(
        '{"status":"success","finished_at_epoch":1784806200}\n',
        encoding="utf-8",
    )

    snapshot = await collect_runtime_snapshot(
        redis,
        db,
        observed_at=NOW,
        maintenance_status_path=heartbeat,
    )

    assert snapshot.failed_jobs_last_hour == 1
    assert snapshot.oauth_failures_last_hour == 1
    assert snapshot.queue_depth == 1
    assert snapshot.oldest_queue_age_seconds == 180
    assert snapshot.stale_pending_escalations == 4
    assert snapshot.health_dependency_failures == 0
    assert snapshot.maintenance_age_seconds == 1800
    assert snapshot.maintenance_last_run_succeeded is True
    assert snapshot.maintenance_heartbeat_missing is False
    redis.lrange.assert_awaited_once_with(ZOHO_OAUTH_FAILURES_KEY, 0, -1)


@pytest.mark.asyncio
async def test_runtime_monitoring_logs_but_does_not_notify_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    collector = AsyncMock(
        return_value=RuntimeSnapshot(
            observed_at=NOW,
            failed_jobs_last_hour=1,
            oauth_failures_last_hour=0,
            queue_depth=0,
            oldest_queue_age_seconds=None,
            stale_pending_escalations=0,
            health_dependency_failures=0,
            maintenance_age_seconds=60,
            maintenance_last_run_succeeded=True,
            maintenance_heartbeat_missing=False,
        )
    )
    sender = AsyncMock()
    monkeypatch.setattr(
        "src.services.runtime_monitoring.collect_runtime_snapshot",
        collector,
    )
    monkeypatch.setattr(
        "src.services.runtime_monitoring.send_telegram_message",
        sender,
    )
    monkeypatch.setattr(
        "src.services.runtime_monitoring.settings.runtime_monitoring_enabled",
        True,
    )
    monkeypatch.setattr(
        "src.services.runtime_monitoring.settings.runtime_monitoring_telegram_enabled",
        False,
    )

    signals = await run_runtime_monitoring({"redis": AsyncMock()})

    assert [signal.code for signal in signals] == ["arq_jobs_failed"]
    sender.assert_not_awaited()


@pytest.mark.asyncio
async def test_runtime_monitoring_notifies_once_after_explicit_enable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    collector = AsyncMock(
        return_value=RuntimeSnapshot(
            observed_at=NOW,
            failed_jobs_last_hour=0,
            oauth_failures_last_hour=1,
            queue_depth=0,
            oldest_queue_age_seconds=None,
            stale_pending_escalations=0,
            health_dependency_failures=0,
            maintenance_age_seconds=60,
            maintenance_last_run_succeeded=True,
            maintenance_heartbeat_missing=False,
        )
    )
    sender = AsyncMock()
    claim = AsyncMock(return_value=True)
    monkeypatch.setattr(
        "src.services.runtime_monitoring.collect_runtime_snapshot",
        collector,
    )
    monkeypatch.setattr(
        "src.services.runtime_monitoring.send_telegram_message",
        sender,
    )
    monkeypatch.setattr(
        "src.services.runtime_monitoring.claim_signal_delivery",
        claim,
    )
    monkeypatch.setattr(
        "src.services.runtime_monitoring.settings.runtime_monitoring_enabled",
        True,
    )
    monkeypatch.setattr(
        "src.services.runtime_monitoring.settings.runtime_monitoring_telegram_enabled",
        True,
    )

    signals = await run_runtime_monitoring({"redis": AsyncMock()})

    assert [signal.code for signal in signals] == ["zoho_oauth_failed"]
    claim.assert_awaited_once()
    message = sender.await_args.args[0]
    assert "zoho_oauth_failed" in message
    assert "token" not in message.lower()
    assert "secret" not in message.lower()
