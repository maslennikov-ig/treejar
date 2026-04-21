from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest


class _FakeDb:
    def __init__(self) -> None:
        self.add = MagicMock()
        self.flush = AsyncMock()
        self.commit = AsyncMock()
        self.rollback = AsyncMock()


def _attempt_key_kwargs() -> dict[str, object]:
    return {
        "path": "quality_final",
        "entity_type": "conversation",
        "entity_id": str(uuid4()),
        "entity_updated_at": datetime(2026, 4, 21, 10, 30, tzinfo=UTC),
        "prompt_version": "quality-final:v1",
    }


def _make_redis(*, set_result: bool = True, backoff: str | None = None) -> AsyncMock:
    redis = AsyncMock()
    redis.set = AsyncMock(return_value=set_result)
    redis.get = AsyncMock(return_value=backoff)
    redis.delete = AsyncMock()
    redis.setex = AsyncMock()
    return redis


def test_status_enum_covers_required_statuses() -> None:
    from src.llm.attempts import LLMAttemptStatus, validate_llm_attempt_status

    assert {status.value for status in LLMAttemptStatus} == {
        "pending",
        "success",
        "no_action",
        "failed_retryable",
        "failed_final",
        "budget_blocked",
        "needs_manual_review",
    }
    assert validate_llm_attempt_status("success") is LLMAttemptStatus.SUCCESS
    with pytest.raises(ValueError, match="Unsupported LLM attempt status"):
        validate_llm_attempt_status("unknown")


def test_model_declares_logical_attempt_uniqueness() -> None:
    from sqlalchemy import UniqueConstraint

    from src.models.llm_attempt import LLMAttempt

    unique_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in LLMAttempt.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert (
        "path",
        "entity_type",
        "entity_id",
        "entity_updated_at",
        "prompt_version",
    ) in unique_columns


@pytest.mark.asyncio
async def test_begin_attempt_acquires_redis_lock_and_creates_pending(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.llm import attempts
    from src.llm.attempts import LLMAttemptStatus, begin_llm_attempt

    monkeypatch.setattr(attempts, "_get_attempt_by_key", AsyncMock(return_value=None))
    db = _FakeDb()
    redis = _make_redis(set_result=True)

    lease = await begin_llm_attempt(
        db,  # type: ignore[arg-type]
        redis,
        **_attempt_key_kwargs(),
        model="z-ai/glm-5-20260211",
        provider="openrouter",
    )

    assert lease is not None
    assert lease.attempt.status == LLMAttemptStatus.PENDING.value
    assert lease.attempt.attempt_count == 1
    redis.set.assert_awaited_once()
    assert redis.set.await_args.kwargs["nx"] is True
    assert redis.set.await_args.kwargs["ex"] > 0
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_redis_lock_prevents_concurrent_duplicate_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.llm import attempts
    from src.llm.attempts import begin_llm_attempt

    monkeypatch.setattr(attempts, "_get_attempt_by_key", AsyncMock(return_value=None))
    db = _FakeDb()
    redis = _make_redis(set_result=False)

    lease = await begin_llm_attempt(
        db,  # type: ignore[arg-type]
        redis,
        **_attempt_key_kwargs(),
    )

    assert lease is None
    db.add.assert_not_called()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_begin_attempt_releases_redis_lock_when_db_write_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.llm import attempts
    from src.llm.attempts import begin_llm_attempt

    monkeypatch.setattr(attempts, "_get_attempt_by_key", AsyncMock(return_value=None))
    db = _FakeDb()
    db.flush.side_effect = RuntimeError("flush failed")
    redis = _make_redis(set_result=True)
    redis.eval = AsyncMock()

    with pytest.raises(RuntimeError, match="flush failed"):
        await begin_llm_attempt(
            db,  # type: ignore[arg-type]
            redis,
            **_attempt_key_kwargs(),
        )

    db.rollback.assert_awaited_once()
    db.commit.assert_not_awaited()
    redis.eval.assert_awaited_once()
    assert redis.eval.await_args.args[1] == 1
    assert redis.eval.await_args.args[2].startswith("llm_attempt:lock:")


@pytest.mark.asyncio
async def test_terminal_attempt_status_skips_without_redis_lock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.llm import attempts
    from src.llm.attempts import LLMAttemptStatus, begin_llm_attempt
    from src.models.llm_attempt import LLMAttempt

    existing = LLMAttempt(
        **_attempt_key_kwargs(),
        status=LLMAttemptStatus.SUCCESS.value,
        attempt_count=1,
    )
    monkeypatch.setattr(
        attempts, "_get_attempt_by_key", AsyncMock(return_value=existing)
    )
    redis = _make_redis()

    lease = await begin_llm_attempt(
        _FakeDb(),  # type: ignore[arg-type]
        redis,
        **_attempt_key_kwargs(),
    )

    assert lease is None
    redis.set.assert_not_awaited()


@pytest.mark.asyncio
async def test_failed_retryable_writes_backoff_and_skips_until_due(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.llm import attempts
    from src.llm.attempts import (
        LLMAttemptLease,
        LLMAttemptStatus,
        begin_llm_attempt,
        record_llm_attempt_error,
    )
    from src.models.llm_attempt import LLMAttempt

    now = datetime(2026, 4, 21, 12, 0, tzinfo=UTC)
    attempt = LLMAttempt(
        **_attempt_key_kwargs(),
        status=LLMAttemptStatus.PENDING.value,
        attempt_count=1,
    )
    lease = LLMAttemptLease(
        attempt=attempt,
        lock_key="llm_attempt:lock:test",
        lock_token="token",
        backoff_key="llm_attempt:backoff:test",
    )
    db = _FakeDb()
    redis = _make_redis()

    await record_llm_attempt_error(
        db,  # type: ignore[arg-type]
        lease,
        TimeoutError("provider timeout"),
        redis=redis,
        now=now,
        max_attempts=2,
    )

    assert attempt.status == LLMAttemptStatus.FAILED_RETRYABLE.value
    assert attempt.next_retry_at is not None
    assert attempt.next_retry_at > now
    redis.setex.assert_awaited_once()

    monkeypatch.setattr(
        attempts, "_get_attempt_by_key", AsyncMock(return_value=attempt)
    )
    redis_with_backoff = _make_redis(backoff=attempt.next_retry_at.isoformat())

    skipped = await begin_llm_attempt(
        _FakeDb(),  # type: ignore[arg-type]
        redis_with_backoff,
        **_attempt_key_kwargs(),
        now=now + timedelta(minutes=1),
    )

    assert skipped is None
    redis_with_backoff.set.assert_not_awaited()


@pytest.mark.asyncio
async def test_failed_retryable_allows_retry_when_db_due_even_if_redis_read_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.llm import attempts
    from src.llm.attempts import LLMAttemptStatus, begin_llm_attempt
    from src.models.llm_attempt import LLMAttempt

    existing = LLMAttempt(
        **_attempt_key_kwargs(),
        status=LLMAttemptStatus.FAILED_RETRYABLE.value,
        attempt_count=1,
        next_retry_at=datetime(2026, 4, 21, 11, 0, tzinfo=UTC),
    )
    monkeypatch.setattr(
        attempts, "_get_attempt_by_key", AsyncMock(return_value=existing)
    )
    redis = _make_redis()
    redis.get = AsyncMock(side_effect=RuntimeError("redis unavailable"))

    lease = await begin_llm_attempt(
        _FakeDb(),  # type: ignore[arg-type]
        redis,
        **_attempt_key_kwargs(),
        now=datetime(2026, 4, 21, 12, 0, tzinfo=UTC),
    )

    assert lease is not None
    assert existing.status == LLMAttemptStatus.PENDING.value
    assert existing.attempt_count == 2
    redis.get.assert_not_awaited()


@pytest.mark.asyncio
async def test_retryable_failure_becomes_final_after_max_attempts() -> None:
    from src.llm.attempts import (
        LLMAttemptLease,
        LLMAttemptStatus,
        record_llm_attempt_error,
    )
    from src.models.llm_attempt import LLMAttempt

    attempt = LLMAttempt(
        **_attempt_key_kwargs(),
        status=LLMAttemptStatus.PENDING.value,
        attempt_count=2,
    )
    lease = LLMAttemptLease(
        attempt=attempt,
        lock_key="llm_attempt:lock:test",
        lock_token="token",
        backoff_key="llm_attempt:backoff:test",
    )

    await record_llm_attempt_error(
        _FakeDb(),  # type: ignore[arg-type]
        lease,
        TimeoutError("provider timeout"),
        redis=_make_redis(),
        max_attempts=2,
    )

    assert attempt.status == LLMAttemptStatus.FAILED_FINAL.value
    assert attempt.next_retry_at is None


@pytest.mark.asyncio
async def test_budget_blocked_is_persisted_as_terminal() -> None:
    from src.llm.attempts import (
        LLMAttemptLease,
        LLMAttemptStatus,
        record_llm_attempt_error,
    )
    from src.llm.safety import LLMBudgetBlocked
    from src.models.llm_attempt import LLMAttempt

    attempt = LLMAttempt(
        **_attempt_key_kwargs(),
        status=LLMAttemptStatus.PENDING.value,
        attempt_count=1,
    )
    lease = LLMAttemptLease(
        attempt=attempt,
        lock_key="llm_attempt:lock:test",
        lock_token="token",
        backoff_key="llm_attempt:backoff:test",
    )

    await record_llm_attempt_error(
        _FakeDb(),  # type: ignore[arg-type]
        lease,
        LLMBudgetBlocked("blocked"),
        redis=_make_redis(),
    )

    assert attempt.status == LLMAttemptStatus.BUDGET_BLOCKED.value
    assert attempt.next_retry_at is None


@pytest.mark.asyncio
async def test_unreviewable_value_error_is_persisted_as_manual_review() -> None:
    from src.llm.attempts import (
        LLMAttemptLease,
        LLMAttemptStatus,
        record_llm_attempt_error,
    )
    from src.models.llm_attempt import LLMAttempt

    attempt = LLMAttempt(
        **_attempt_key_kwargs(),
        status=LLMAttemptStatus.PENDING.value,
        attempt_count=1,
    )
    lease = LLMAttemptLease(
        attempt=attempt,
        lock_key="llm_attempt:lock:test",
        lock_token="token",
        backoff_key="llm_attempt:backoff:test",
    )

    await record_llm_attempt_error(
        _FakeDb(),  # type: ignore[arg-type]
        lease,
        ValueError("No post-escalation messages found"),
        redis=_make_redis(),
    )

    assert attempt.status == LLMAttemptStatus.NEEDS_MANUAL_REVIEW.value
    assert attempt.next_retry_at is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status",
    ["failed_final", "needs_manual_review", "budget_blocked", "no_action"],
)
async def test_terminal_failure_statuses_prevent_cron_spin(
    monkeypatch: pytest.MonkeyPatch,
    status: str,
) -> None:
    from src.llm import attempts
    from src.llm.attempts import begin_llm_attempt
    from src.models.llm_attempt import LLMAttempt

    existing = LLMAttempt(
        **_attempt_key_kwargs(),
        status=status,
        attempt_count=1,
    )
    monkeypatch.setattr(
        attempts, "_get_attempt_by_key", AsyncMock(return_value=existing)
    )

    assert (
        await begin_llm_attempt(
            _FakeDb(),  # type: ignore[arg-type]
            _make_redis(),
            **_attempt_key_kwargs(),
        )
        is None
    )
