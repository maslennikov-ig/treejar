"""Durable LLM attempt/cache state with Redis coordination."""

from __future__ import annotations

import hashlib
import inspect
import json
import logging
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, cast

import httpx
from pydantic_ai.exceptions import (
    ModelAPIError,
    ModelHTTPError,
    UnexpectedModelBehavior,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.llm.safety import LLMBudgetBlocked
from src.models.llm_attempt import LLMAttempt

logger = logging.getLogger(__name__)

DEFAULT_LOCK_TTL_SECONDS = 10 * 60
DEFAULT_BACKOFF_SECONDS = 30 * 60
MAX_BACKOFF_SECONDS = 6 * 60 * 60
DEFAULT_MAX_CRON_ATTEMPTS = 2
_RELEASE_LOCK_SCRIPT = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
end
return 0
"""


class LLMAttemptStatus(StrEnum):
    PENDING = "pending"
    SUCCESS = "success"
    NO_ACTION = "no_action"
    FAILED_RETRYABLE = "failed_retryable"
    FAILED_FINAL = "failed_final"
    BUDGET_BLOCKED = "budget_blocked"
    NEEDS_MANUAL_REVIEW = "needs_manual_review"


TERMINAL_STATUSES = frozenset(
    {
        LLMAttemptStatus.SUCCESS,
        LLMAttemptStatus.NO_ACTION,
        LLMAttemptStatus.FAILED_FINAL,
        LLMAttemptStatus.BUDGET_BLOCKED,
        LLMAttemptStatus.NEEDS_MANUAL_REVIEW,
    }
)

_RETRYABLE_ERRORS = (
    TimeoutError,
    httpx.HTTPError,
    ModelAPIError,
    ModelHTTPError,
    UnexpectedModelBehavior,
)


@dataclass(frozen=True, slots=True)
class LLMAttemptLease:
    attempt: LLMAttempt
    lock_key: str
    lock_token: str
    backoff_key: str
    attempt_count: int | None = None


def validate_llm_attempt_status(value: str | LLMAttemptStatus) -> LLMAttemptStatus:
    try:
        return value if isinstance(value, LLMAttemptStatus) else LLMAttemptStatus(value)
    except ValueError as exc:
        raise ValueError(f"Unsupported LLM attempt status: {value}") from exc


def _normalise_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _attempt_key_payload(
    *,
    path: str,
    entity_type: str,
    entity_id: Any,
    entity_updated_at: datetime,
    prompt_version: str,
) -> dict[str, str]:
    return {
        "path": path,
        "entity_type": entity_type,
        "entity_id": str(entity_id),
        "entity_updated_at": _normalise_utc(entity_updated_at).isoformat(),
        "prompt_version": prompt_version,
    }


def _attempt_key_digest(payload: dict[str, str]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _lock_key(payload: dict[str, str]) -> str:
    return f"llm_attempt:lock:{_attempt_key_digest(payload)}"


def _backoff_key(payload: dict[str, str]) -> str:
    return f"llm_attempt:backoff:{_attempt_key_digest(payload)}"


async def _release_redis_lock(redis: Any, lock_key: str, lock_token: str) -> None:
    await redis.eval(_RELEASE_LOCK_SCRIPT, 1, lock_key, lock_token)


async def _get_attempt_by_key(
    db: AsyncSession,
    *,
    path: str,
    entity_type: str,
    entity_id: Any,
    entity_updated_at: datetime,
    prompt_version: str,
) -> LLMAttempt | None:
    stmt = select(LLMAttempt).where(
        LLMAttempt.path == path,
        LLMAttempt.entity_type == entity_type,
        LLMAttempt.entity_id == str(entity_id),
        LLMAttempt.entity_updated_at == _normalise_utc(entity_updated_at),
        LLMAttempt.prompt_version == prompt_version,
    )
    result = await db.execute(stmt)
    maybe_attempt = result.scalar_one_or_none()
    if inspect.isawaitable(maybe_attempt):
        maybe_attempt = await maybe_attempt
    return maybe_attempt if isinstance(maybe_attempt, LLMAttempt) else None


async def _redis_get(redis: Any, key: str) -> str | None:
    value = await redis.get(key)
    if isinstance(value, bytes):
        return value.decode()
    return value if isinstance(value, str) else None


async def _backoff_is_active(
    *,
    redis: Any,
    key: str,
    attempt: LLMAttempt,
    now: datetime,
) -> bool:
    db_next_retry_at = (
        _normalise_utc(attempt.next_retry_at)
        if attempt.next_retry_at is not None
        else None
    )
    if db_next_retry_at is not None:
        return db_next_retry_at > now
    try:
        return await _redis_get(redis, key) is not None
    except Exception:
        logger.warning("Failed to read LLM attempt Redis backoff", exc_info=True)
        return False


def _next_retry_at(
    *,
    now: datetime,
    attempt_count: int,
    base_seconds: int,
    max_seconds: int,
) -> datetime:
    exponent = max(attempt_count - 1, 0)
    seconds = min(base_seconds * (2**exponent), max_seconds)
    return now + timedelta(seconds=seconds)


def _is_retryable_error(error: BaseException) -> bool:
    return isinstance(error, _RETRYABLE_ERRORS)


def _needs_manual_review(error: BaseException) -> bool:
    if not isinstance(error, ValueError):
        return False
    message = str(error).lower()
    return "no messages" in message or "no post-escalation messages" in message


def _error_text(error: BaseException) -> str:
    return f"{type(error).__name__}: {error}"[:4000]


def _hash_value_matches(current: str | None, incoming: str | None) -> bool:
    if incoming is None:
        return True
    return current == incoming


def _attempt_hashes_match(
    attempt: LLMAttempt,
    *,
    input_hash: str | None,
    settings_hash: str | None,
) -> bool:
    return _hash_value_matches(
        attempt.input_hash,
        input_hash,
    ) and _hash_value_matches(
        attempt.settings_hash,
        settings_hash,
    )


async def begin_llm_attempt(
    db: AsyncSession,
    redis: Any,
    *,
    path: str,
    entity_type: str,
    entity_id: Any,
    entity_updated_at: datetime,
    prompt_version: str,
    input_hash: str | None = None,
    settings_hash: str | None = None,
    model: str | None = None,
    provider: str | None = None,
    budget_cents: int | None = None,
    cost_estimate: float | None = None,
    lock_ttl_seconds: int = DEFAULT_LOCK_TTL_SECONDS,
    now: datetime | None = None,
) -> LLMAttemptLease | None:
    """Create or reopen a logical LLM attempt if it is billable now."""
    current_time = _normalise_utc(now or datetime.now(UTC))
    normalized_updated_at = _normalise_utc(entity_updated_at)
    key_payload = _attempt_key_payload(
        path=path,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_updated_at=normalized_updated_at,
        prompt_version=prompt_version,
    )
    lock_key = _lock_key(key_payload)
    backoff_key = _backoff_key(key_payload)

    attempt = await _get_attempt_by_key(
        db,
        path=path,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_updated_at=normalized_updated_at,
        prompt_version=prompt_version,
    )
    if attempt is not None:
        status = validate_llm_attempt_status(attempt.status)
        hashes_match = _attempt_hashes_match(
            attempt,
            input_hash=input_hash,
            settings_hash=settings_hash,
        )
        if status in TERMINAL_STATUSES and hashes_match:
            return None
        if (
            status is LLMAttemptStatus.FAILED_RETRYABLE
            and hashes_match
            and await _backoff_is_active(
                redis=redis,
                key=backoff_key,
                attempt=attempt,
                now=current_time,
            )
        ):
            return None

    token = secrets.token_urlsafe(24)
    try:
        locked = bool(await redis.set(lock_key, token, nx=True, ex=lock_ttl_seconds))
    except Exception:
        logger.warning("Failed to acquire LLM attempt Redis lock", exc_info=True)
        return None
    if not locked:
        return None

    try:
        if attempt is None:
            attempt = LLMAttempt(
                path=path,
                entity_type=entity_type,
                entity_id=str(entity_id),
                entity_updated_at=normalized_updated_at,
                prompt_version=prompt_version,
                input_hash=input_hash,
                settings_hash=settings_hash,
                status=LLMAttemptStatus.PENDING.value,
                attempt_count=0,
                model=model,
                provider=provider,
                budget_cents=budget_cents,
                cost_estimate=cost_estimate,
            )
            maybe_add = cast("Any", db).add(attempt)
            if inspect.isawaitable(maybe_add):
                await maybe_add
        else:
            attempt.status = LLMAttemptStatus.PENDING.value
            attempt.input_hash = input_hash or attempt.input_hash
            attempt.settings_hash = settings_hash or attempt.settings_hash
            attempt.model = model or attempt.model
            attempt.provider = provider or attempt.provider
            attempt.budget_cents = budget_cents
            attempt.cost_estimate = cost_estimate
            attempt.result_json = None
            attempt.last_error = None

        attempt.attempt_count += 1
        attempt.next_retry_at = None
        await db.flush()
        await db.commit()
    except Exception:
        try:
            await db.rollback()
        except Exception:
            logger.warning(
                "Failed to rollback LLM attempt begin transaction", exc_info=True
            )
        try:
            await _release_redis_lock(redis, lock_key, token)
        except Exception:
            logger.warning("Failed to release LLM attempt Redis lock", exc_info=True)
        raise
    return LLMAttemptLease(
        attempt=attempt,
        lock_key=lock_key,
        lock_token=token,
        backoff_key=backoff_key,
        attempt_count=attempt.attempt_count,
    )


async def record_llm_attempt_success(
    db: AsyncSession,
    lease: LLMAttemptLease,
    *,
    result_json: dict[str, Any] | list[Any] | None = None,
    model: str | None = None,
    provider: str | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    reasoning_tokens: int | None = None,
    cached_tokens: int | None = None,
    cache_write_tokens: int | None = None,
    cost_usd: float | None = None,
) -> None:
    attempt = lease.attempt
    attempt.status = LLMAttemptStatus.SUCCESS.value
    attempt.next_retry_at = None
    attempt.last_error = None
    attempt.result_json = result_json
    attempt.model = model or attempt.model
    attempt.provider = provider or attempt.provider
    attempt.prompt_tokens = prompt_tokens
    attempt.completion_tokens = completion_tokens
    attempt.reasoning_tokens = reasoning_tokens
    attempt.cached_tokens = cached_tokens
    attempt.cache_write_tokens = cache_write_tokens
    attempt.cost_usd = cost_usd
    await db.flush()


async def record_llm_attempt_no_action(
    db: AsyncSession,
    lease: LLMAttemptLease,
    *,
    result_json: dict[str, Any] | list[Any] | None = None,
    model: str | None = None,
    provider: str | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    reasoning_tokens: int | None = None,
    cached_tokens: int | None = None,
    cache_write_tokens: int | None = None,
    cost_usd: float | None = None,
) -> None:
    attempt = lease.attempt
    attempt.status = LLMAttemptStatus.NO_ACTION.value
    attempt.next_retry_at = None
    attempt.last_error = None
    attempt.result_json = result_json
    attempt.model = model or attempt.model
    attempt.provider = provider or attempt.provider
    attempt.prompt_tokens = prompt_tokens
    attempt.completion_tokens = completion_tokens
    attempt.reasoning_tokens = reasoning_tokens
    attempt.cached_tokens = cached_tokens
    attempt.cache_write_tokens = cache_write_tokens
    attempt.cost_usd = cost_usd
    await db.flush()


async def record_llm_attempt_error(
    db: AsyncSession,
    lease: LLMAttemptLease,
    error: BaseException,
    *,
    redis: Any,
    now: datetime | None = None,
    max_attempts: int = DEFAULT_MAX_CRON_ATTEMPTS,
    backoff_base_seconds: int = DEFAULT_BACKOFF_SECONDS,
    max_backoff_seconds: int = MAX_BACKOFF_SECONDS,
) -> None:
    attempt = lease.attempt
    attempt_count = (
        lease.attempt_count
        if lease.attempt_count is not None
        else attempt.attempt_count
    )
    attempt.last_error = _error_text(error)
    attempt.result_json = None

    if isinstance(error, LLMBudgetBlocked):
        attempt.status = LLMAttemptStatus.BUDGET_BLOCKED.value
        attempt.next_retry_at = None
    elif _needs_manual_review(error):
        attempt.status = LLMAttemptStatus.NEEDS_MANUAL_REVIEW.value
        attempt.next_retry_at = None
    elif _is_retryable_error(error) and attempt_count < max_attempts:
        current_time = _normalise_utc(now or datetime.now(UTC))
        retry_at = _next_retry_at(
            now=current_time,
            attempt_count=attempt_count,
            base_seconds=backoff_base_seconds,
            max_seconds=max_backoff_seconds,
        )
        attempt.status = LLMAttemptStatus.FAILED_RETRYABLE.value
        attempt.next_retry_at = retry_at
        ttl_seconds = max(int((retry_at - current_time).total_seconds()), 1)
        try:
            await redis.setex(lease.backoff_key, ttl_seconds, retry_at.isoformat())
        except Exception:
            logger.warning("Failed to write LLM attempt Redis backoff", exc_info=True)
    else:
        attempt.status = LLMAttemptStatus.FAILED_FINAL.value
        attempt.next_retry_at = None

    await db.flush()


async def release_llm_attempt_lock(redis: Any, lease: LLMAttemptLease) -> None:
    try:
        await _release_redis_lock(redis, lease.lock_key, lease.lock_token)
    except Exception:
        logger.warning("Failed to release LLM attempt Redis lock", exc_info=True)
