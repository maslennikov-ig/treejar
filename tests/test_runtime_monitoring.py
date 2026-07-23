from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from src.services.runtime_monitoring import (
    RuntimeSnapshot,
    RuntimeThresholds,
    claim_signal_delivery,
    evaluate_runtime_snapshot,
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
