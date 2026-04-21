"""ARQ background jobs for bot quality monitoring."""

from __future__ import annotations

import hashlib
import inspect
import json
import logging
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from sqlalchemy import select

from src.core.database import async_session_factory
from src.core.redis import get_redis_client
from src.integrations.crm.zoho_crm import ZohoCRMClient
from src.llm.attempts import (
    LLMAttemptLease,
    LLMAttemptStatus,
    begin_llm_attempt,
    record_llm_attempt_error,
    record_llm_attempt_no_action,
    record_llm_attempt_success,
    release_llm_attempt_lock,
)
from src.llm.safety import PATH_QUALITY_FINAL, PATH_QUALITY_RED_FLAGS
from src.models.llm_attempt import LLMAttempt
from src.quality.config import (
    AIQualityScope,
    consume_ai_quality_daily_call_from_ctx,
    get_ai_quality_run_gate_from_ctx,
    reserve_ai_quality_daily_sample_from_ctx,
)
from src.quality.evaluator import evaluate_conversation, evaluate_red_flags
from src.quality.schemas import (
    CriterionScore,
    EvaluationResult,
    RedFlagEvaluationResult,
    RedFlagItem,
    finalize_evaluation_result,
)
from src.quality.service import (
    QualityConversationCandidate,
    get_recent_assistant_conversation_candidates,
    get_recent_updated_conversation_candidates,
    get_review_for_conversation,
    save_review,
)
from src.services.customer_identity import resolve_owner_customer_name
from src.services.inbound_channels import (
    get_conversation_inbound_channel_phone,
    should_send_telegram_alert_for_conversation_with_db,
)

logger = logging.getLogger(__name__)

_RED_FLAG_TTL_SECONDS = 30 * 24 * 60 * 60
_FINAL_TTL_SECONDS = 30 * 24 * 60 * 60
_RED_FLAG_LOOKBACK = timedelta(days=1)
_FINAL_LOOKBACK = timedelta(days=7)
_FINAL_IDLE_THRESHOLD = timedelta(hours=3)
_QUERY_BATCH_SIZE = 50
_OPENROUTER_PROVIDER = "openrouter"
_ENTITY_TYPE_CONVERSATION = "conversation"
_PROMPT_VERSION_FINAL = "quality-final:v1"
_PROMPT_VERSION_RED_FLAGS = "quality-red-flags:v1"


def _normalise_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _updated_at_iso(value: datetime) -> str:
    return _normalise_utc(value).isoformat()


def _activity_at(candidate: QualityConversationCandidate) -> datetime:
    return candidate.activity_at or candidate.updated_at


def _attempt_entity_updated_at(
    candidate: QualityConversationCandidate,
    *,
    path: str,
) -> datetime:
    return _activity_at(candidate)


def _red_flag_marker_key(conversation_id: Any) -> str:
    return f"quality:redflag:{conversation_id}"


def _final_marker_key(conversation_id: Any) -> str:
    return f"quality:final:{conversation_id}"


def _build_red_flag_signature(flags: list[RedFlagItem]) -> str:
    joined_codes = "|".join(sorted(flag.code for flag in flags))
    return hashlib.sha256(joined_codes.encode("utf-8")).hexdigest()


def _stable_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, default=str, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _candidate_input_hash(
    candidate: QualityConversationCandidate,
    *,
    prompt_version: str,
) -> str:
    return _stable_hash(
        {
            "conversation_id": str(candidate.conversation_id),
            "updated_at": _updated_at_iso(candidate.updated_at),
            "activity_at": _updated_at_iso(_activity_at(candidate)),
            "status": candidate.status,
            "sales_stage": candidate.sales_stage,
            "prompt_version": prompt_version,
        }
    )


def _attempt_settings_hash(
    *,
    path: str,
    prompt_version: str,
    model: str,
) -> str:
    return _stable_hash(
        {
            "path": path,
            "prompt_version": prompt_version,
            "model": model,
            "provider": _OPENROUTER_PROVIDER,
        }
    )


def _result_payload(result: Any) -> dict[str, Any] | list[Any] | None:
    model_dump = getattr(result, "model_dump", None)
    if callable(model_dump):
        payload = model_dump(mode="json")
        if isinstance(payload, dict | list):
            return payload
    return None


async def _load_quality_attempt(
    db: Any,
    candidate: QualityConversationCandidate,
    *,
    path: str,
    prompt_version: str,
) -> LLMAttempt | None:
    stmt = select(LLMAttempt).where(
        LLMAttempt.path == path,
        LLMAttempt.entity_type == _ENTITY_TYPE_CONVERSATION,
        LLMAttempt.entity_id == str(candidate.conversation_id),
        LLMAttempt.entity_updated_at
        == _normalise_utc(
            _attempt_entity_updated_at(
                candidate,
                path=path,
            )
        ),
        LLMAttempt.prompt_version == prompt_version,
    )
    result = await db.execute(stmt)
    attempt = result.scalar_one_or_none()
    if inspect.isawaitable(attempt):
        attempt = await attempt
    return cast("LLMAttempt | None", attempt)


def _evaluation_result_from_attempt_payload(payload: Any) -> EvaluationResult:
    return EvaluationResult.model_validate(payload)


def _evaluation_result_from_review(review: Any) -> EvaluationResult:
    criteria = [CriterionScore.model_validate(item) for item in (review.criteria or [])]
    base_result = EvaluationResult(
        criteria=criteria,
        summary=review.summary or "",
        total_score=float(review.total_score),
        rating=review.rating,
        strengths=[],
        weaknesses=[],
        recommendations=[],
        next_best_action="",
        block_scores=[],
    )
    return finalize_evaluation_result(base_result)


async def _load_terminal_final_review(
    db: Any,
    candidate: QualityConversationCandidate,
) -> tuple[EvaluationResult | None, bool]:
    attempt = await _load_quality_attempt(
        db,
        candidate,
        path=PATH_QUALITY_FINAL,
        prompt_version=_PROMPT_VERSION_FINAL,
    )
    if attempt is None or attempt.status != LLMAttemptStatus.SUCCESS.value:
        return None, False

    review = await get_review_for_conversation(db, candidate.conversation_id)

    if attempt.result_json is not None:
        return (
            _evaluation_result_from_attempt_payload(attempt.result_json),
            review is None,
        )

    if review is None:
        return None, False
    return _evaluation_result_from_review(review), False


async def _load_terminal_red_flag_result(
    db: Any,
    candidate: QualityConversationCandidate,
) -> RedFlagEvaluationResult | None:
    attempt = await _load_quality_attempt(
        db,
        candidate,
        path=PATH_QUALITY_RED_FLAGS,
        prompt_version=_PROMPT_VERSION_RED_FLAGS,
    )
    if attempt is None or attempt.status != LLMAttemptStatus.SUCCESS.value:
        return None
    if attempt.result_json is None:
        return None
    return RedFlagEvaluationResult.model_validate(attempt.result_json)


async def _replay_terminal_red_flag_delivery(
    *,
    db: Any,
    redis: Any,
    candidate: QualityConversationCandidate,
    crm_client: Any | None,
) -> bool:
    result = await _load_terminal_red_flag_result(db, candidate)
    if result is None:
        return False

    marker_key = _red_flag_marker_key(candidate.conversation_id)
    previous_signature = _extract_previous_signature(await redis.get(marker_key))
    signature = _build_red_flag_signature(result.flags)

    if previous_signature == signature:
        return False

    should_notify = await should_send_telegram_alert_for_conversation_with_db(
        candidate,
        db,
    )

    if not should_notify:
        await redis.setex(
            marker_key,
            _RED_FLAG_TTL_SECONDS,
            json.dumps(
                {
                    "signature": signature,
                    "updated_at": _updated_at_iso(_activity_at(candidate)),
                }
            ),
        )
        return False

    identity_context = await _build_quality_identity_context(
        candidate,
        redis=redis,
        crm_client=crm_client,
    )

    from src.services.notifications import notify_red_flag_warning

    await notify_red_flag_warning(
        conversation_id=candidate.conversation_id,
        phone=candidate.phone,
        sales_stage=candidate.sales_stage,
        flags=result.flags,
        recommended_action=result.recommended_action,
        **identity_context,
    )
    await redis.setex(
        marker_key,
        _RED_FLAG_TTL_SECONDS,
        json.dumps(
            {
                "signature": signature,
                "updated_at": _updated_at_iso(_activity_at(candidate)),
            }
        ),
    )
    return True


async def _replay_terminal_final_review(
    *,
    db: Any,
    redis: Any,
    candidate: QualityConversationCandidate,
    crm_client: Any | None,
    trigger: str,
) -> bool:
    result, should_materialize_review = await _load_terminal_final_review(db, candidate)
    if result is None:
        return False

    marker_key = _final_marker_key(candidate.conversation_id)
    current_updated_at = _updated_at_iso(_activity_at(candidate))
    previous_updated_at = await redis.get(marker_key)
    if previous_updated_at == current_updated_at:
        return False

    if should_materialize_review:
        await save_review(db, candidate.conversation_id, result)
        await _commit_or_rollback(db)

    should_notify = await should_send_telegram_alert_for_conversation_with_db(
        candidate,
        db,
    )

    if should_notify:
        identity_context = await _build_quality_identity_context(
            candidate,
            redis=redis,
            crm_client=crm_client,
        )

        from src.services.notifications import notify_final_quality_review

        await notify_final_quality_review(
            conversation_id=candidate.conversation_id,
            phone=candidate.phone,
            sales_stage=candidate.sales_stage,
            trigger=trigger,
            result=result,
            **identity_context,
        )
    else:
        logger.info(
            "Skipping final quality review alert for %s due to inbound channel gating",
            candidate.conversation_id,
        )

    await redis.setex(marker_key, _FINAL_TTL_SECONDS, current_updated_at)
    return True


def _extract_previous_signature(raw_marker: str | None) -> str | None:
    if not raw_marker:
        return None
    try:
        payload = json.loads(raw_marker)
    except json.JSONDecodeError:
        return None
    if isinstance(payload, dict):
        signature = payload.get("signature")
        if isinstance(signature, str):
            return signature
    return None


def _resolve_redis(ctx: dict[str, Any]) -> Any:
    return ctx.get("redis") or get_redis_client()


@asynccontextmanager
async def _quality_crm_client(ctx: dict[str, Any], redis: Any) -> Any:
    existing_client = ctx.get("crm_client")
    if existing_client is not None:
        yield existing_client
        return

    async with ZohoCRMClient(redis) as crm_client:
        yield crm_client


async def _build_quality_identity_context(
    candidate: QualityConversationCandidate,
    *,
    redis: Any,
    crm_client: Any | None,
) -> dict[str, Any]:
    customer_name = await resolve_owner_customer_name(
        phone=candidate.phone,
        conversation_customer_name=candidate.customer_name,
        redis=redis,
        crm_client=crm_client,
    )
    return {
        "customer_name": customer_name,
        "inbound_channel_phone": get_conversation_inbound_channel_phone(candidate),
        "conversation_created_at": candidate.created_at,
        "last_activity_at": _activity_at(candidate),
    }


async def _commit_or_rollback(db: Any) -> None:
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise


async def _record_attempt_error_after_rollback(
    db: Any,
    lease: LLMAttemptLease,
    exc: BaseException,
    *,
    redis: Any,
) -> None:
    await db.rollback()
    await record_llm_attempt_error(
        db,
        lease,
        exc,
        redis=redis,
    )
    await _commit_or_rollback(db)


async def _load_candidates_in_batches(
    fetch_page: Callable[..., Awaitable[list[QualityConversationCandidate]]],
    *,
    since: datetime,
    max_candidates: int | None = None,
) -> list[QualityConversationCandidate]:
    """Read the full eligible candidate set in deterministic pages."""
    candidates: list[QualityConversationCandidate] = []
    offset = 0

    async with async_session_factory() as db:
        while True:
            if max_candidates is not None and len(candidates) >= max_candidates:
                break
            limit = _QUERY_BATCH_SIZE
            if max_candidates is not None:
                limit = min(limit, max_candidates - len(candidates))
            batch = await fetch_page(
                db,
                since=since,
                limit=limit,
                offset=offset,
            )
            if not batch:
                break
            candidates.extend(batch)
            if len(batch) < limit:
                break
            offset += len(batch)

    if max_candidates is None:
        return candidates
    return candidates[:max_candidates]


async def _begin_quality_attempt(
    db: Any,
    redis: Any,
    candidate: QualityConversationCandidate,
    *,
    path: str,
    prompt_version: str,
    model: str,
) -> LLMAttemptLease | None:
    return await begin_llm_attempt(
        db,
        redis,
        path=path,
        entity_type=_ENTITY_TYPE_CONVERSATION,
        entity_id=candidate.conversation_id,
        entity_updated_at=_attempt_entity_updated_at(candidate, path=path),
        prompt_version=prompt_version,
        input_hash=_candidate_input_hash(candidate, prompt_version=prompt_version),
        settings_hash=_attempt_settings_hash(
            path=path,
            prompt_version=prompt_version,
            model=model,
        ),
        model=model,
        provider=_OPENROUTER_PROVIDER,
    )


def _final_review_trigger(
    candidate: QualityConversationCandidate,
    *,
    now: datetime,
) -> str | None:
    if candidate.status == "closed":
        return "closed"
    if _normalise_utc(_activity_at(candidate)) <= now - _FINAL_IDLE_THRESHOLD:
        return "idle 3h"
    return None


async def evaluate_completed_conversations(ctx: dict[str, Any]) -> None:
    """Backward-compatible wrapper around the mature final-review job."""
    await evaluate_mature_conversations_quality(ctx)


async def evaluate_recent_conversations_quality(ctx: dict[str, Any]) -> None:
    """Backward-compatible wrapper around the mature final-review job."""
    await evaluate_mature_conversations_quality(ctx)


async def evaluate_realtime_red_flags(ctx: dict[str, Any]) -> None:
    """ARQ job: send compact realtime warnings only for critical red flags."""
    gate = await get_ai_quality_run_gate_from_ctx(
        ctx,
        scope=AIQualityScope.RED_FLAGS,
        trigger="scheduled",
    )
    if not gate.allowed:
        logger.info(
            "Quality red-flag evaluator disabled by AI Quality Controls: %s",
            gate.reason,
        )
        return

    now = datetime.now(UTC)
    redis = _resolve_redis(ctx)
    candidates = await _load_candidates_in_batches(
        get_recent_assistant_conversation_candidates,
        since=now - _RED_FLAG_LOOKBACK,
        max_candidates=gate.max_calls,
    )

    if not candidates:
        logger.info("Quality red-flag evaluator: no recent assistant conversations")
        return

    gate = await reserve_ai_quality_daily_sample_from_ctx(ctx, gate)
    if not gate.allowed:
        logger.info(
            "Quality red-flag evaluator skipped by AI Quality Controls: %s",
            gate.reason,
        )
        return

    sent = 0
    errors = 0

    async with _quality_crm_client(ctx, redis) as crm_client:
        for candidate in candidates:
            if not await consume_ai_quality_daily_call_from_ctx(ctx, gate):
                logger.info(
                    "Quality red-flag evaluator stopped by daily call quota: %s",
                    gate.scope.value,
                )
                break

            lease: LLMAttemptLease | None = None
            try:
                async with async_session_factory() as db:
                    lease = await _begin_quality_attempt(
                        db,
                        redis,
                        candidate,
                        path=PATH_QUALITY_RED_FLAGS,
                        prompt_version=_PROMPT_VERSION_RED_FLAGS,
                        model=gate.model,
                    )
                    if lease is None:
                        if await _replay_terminal_red_flag_delivery(
                            db=db,
                            redis=redis,
                            candidate=candidate,
                            crm_client=crm_client,
                        ):
                            sent += 1
                            continue
                        continue

                    try:
                        result = await evaluate_red_flags(
                            candidate.conversation_id,
                            db,
                            model_name=gate.model,
                        )
                    except Exception as exc:
                        await _record_attempt_error_after_rollback(
                            db,
                            lease,
                            exc,
                            redis=redis,
                        )
                        raise

                    if not result.flags:
                        await record_llm_attempt_no_action(
                            db,
                            lease,
                            result_json=_result_payload(result),
                        )
                        await _commit_or_rollback(db)
                        continue

                    await record_llm_attempt_success(
                        db,
                        lease,
                        result_json=_result_payload(result),
                        model=gate.model,
                        provider=_OPENROUTER_PROVIDER,
                    )
                    await _commit_or_rollback(db)

                    marker_key = _red_flag_marker_key(candidate.conversation_id)
                    previous_signature = _extract_previous_signature(
                        await redis.get(marker_key)
                    )
                    signature = _build_red_flag_signature(result.flags)
                    if previous_signature == signature:
                        continue

                    should_notify = (
                        await should_send_telegram_alert_for_conversation_with_db(
                            candidate,
                            db,
                        )
                    )
                    if should_notify:
                        identity_context = await _build_quality_identity_context(
                            candidate,
                            redis=redis,
                            crm_client=crm_client,
                        )

                        from src.services.notifications import notify_red_flag_warning

                        await notify_red_flag_warning(
                            conversation_id=candidate.conversation_id,
                            phone=candidate.phone,
                            sales_stage=candidate.sales_stage,
                            flags=result.flags,
                            recommended_action=result.recommended_action,
                            **identity_context,
                        )
                    else:
                        logger.info(
                            "Skipping red-flag alert for %s due to inbound channel gating",
                            candidate.conversation_id,
                        )

                    await redis.setex(
                        marker_key,
                        _RED_FLAG_TTL_SECONDS,
                        json.dumps(
                            {
                                "signature": signature,
                                "updated_at": _updated_at_iso(_activity_at(candidate)),
                            }
                        ),
                    )
                    if should_notify:
                        sent += 1
            except Exception:
                errors += 1
                logger.exception(
                    "Failed to evaluate realtime red flags for conversation %s",
                    candidate.conversation_id,
                )
            finally:
                if lease is not None:
                    await release_llm_attempt_lock(redis, lease)

    logger.info(
        "Quality red-flag evaluator: done. sent=%d, errors=%d",
        sent,
        errors,
    )


async def evaluate_mature_conversations_quality(ctx: dict[str, Any]) -> None:
    """ARQ job: persist and send owner-facing final reviews for mature dialogues."""
    gate = await get_ai_quality_run_gate_from_ctx(
        ctx,
        scope=AIQualityScope.BOT_QA,
        trigger="scheduled",
    )
    if not gate.allowed:
        logger.info(
            "Quality final-review evaluator disabled by AI Quality Controls: %s",
            gate.reason,
        )
        return

    now = datetime.now(UTC)
    redis = _resolve_redis(ctx)
    candidates = await _load_candidates_in_batches(
        get_recent_updated_conversation_candidates,
        since=now - _FINAL_LOOKBACK,
        max_candidates=gate.max_calls,
    )

    if not candidates:
        logger.info("Quality final-review evaluator: no recent conversations")
        return

    gate = await reserve_ai_quality_daily_sample_from_ctx(ctx, gate)
    if not gate.allowed:
        logger.info(
            "Quality final-review evaluator skipped by AI Quality Controls: %s",
            gate.reason,
        )
        return

    reviewed = 0
    errors = 0

    async with _quality_crm_client(ctx, redis) as crm_client:
        for candidate in candidates:
            trigger = _final_review_trigger(candidate, now=now)
            if trigger is None:
                continue

            current_updated_at = _updated_at_iso(_activity_at(candidate))
            marker_key = _final_marker_key(candidate.conversation_id)
            previous_updated_at = await redis.get(marker_key)
            if previous_updated_at == current_updated_at:
                continue

            if not await consume_ai_quality_daily_call_from_ctx(ctx, gate):
                logger.info(
                    "Quality final-review evaluator stopped by daily call quota: %s",
                    gate.scope.value,
                )
                break

            lease: LLMAttemptLease | None = None
            try:
                async with async_session_factory() as db:
                    lease = await _begin_quality_attempt(
                        db,
                        redis,
                        candidate,
                        path=PATH_QUALITY_FINAL,
                        prompt_version=_PROMPT_VERSION_FINAL,
                        model=gate.model,
                    )
                    if lease is None:
                        if await _replay_terminal_final_review(
                            db=db,
                            redis=redis,
                            candidate=candidate,
                            crm_client=crm_client,
                            trigger=trigger,
                        ):
                            reviewed += 1
                        continue

                    try:
                        result = await evaluate_conversation(
                            candidate.conversation_id,
                            db,
                            candidate.sales_stage,
                            model_name=gate.model,
                        )
                    except Exception as exc:
                        await _record_attempt_error_after_rollback(
                            db,
                            lease,
                            exc,
                            redis=redis,
                        )
                        raise

                    await record_llm_attempt_success(
                        db,
                        lease,
                        result_json=_result_payload(result),
                        model=gate.model,
                        provider=_OPENROUTER_PROVIDER,
                    )
                    await _commit_or_rollback(db)

                    try:
                        await save_review(db, candidate.conversation_id, result)
                    except Exception:
                        await db.rollback()
                        raise

                    await _commit_or_rollback(db)

                    should_notify = (
                        await should_send_telegram_alert_for_conversation_with_db(
                            candidate,
                            db,
                        )
                    )
                    if should_notify:
                        identity_context = await _build_quality_identity_context(
                            candidate,
                            redis=redis,
                            crm_client=crm_client,
                        )

                        from src.services.notifications import (
                            notify_final_quality_review,
                        )

                        await notify_final_quality_review(
                            conversation_id=candidate.conversation_id,
                            phone=candidate.phone,
                            sales_stage=candidate.sales_stage,
                            trigger=trigger,
                            result=result,
                            **identity_context,
                        )
                    else:
                        logger.info(
                            "Skipping final quality review alert for %s due to inbound channel gating",
                            candidate.conversation_id,
                        )

                    await redis.setex(
                        marker_key, _FINAL_TTL_SECONDS, current_updated_at
                    )
                    reviewed += 1

            except Exception:
                errors += 1
                logger.exception(
                    "Failed to evaluate mature conversation %s",
                    candidate.conversation_id,
                )
            finally:
                if lease is not None:
                    await release_llm_attempt_lock(redis, lease)

    logger.info(
        "Quality final-review evaluator: done. reviewed=%d, errors=%d",
        reviewed,
        errors,
    )
