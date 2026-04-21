"""ARQ background job for automatic manager evaluation.

Runs every 30 minutes to find resolved escalations without a manager_review
and evaluates them using the LLM judge + quantitative metrics.

See: src/quality/job.py for bot quality evaluation (similar pattern).
"""

from __future__ import annotations

import hashlib
import inspect
import json
import logging
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from src.core.config import settings
from src.core.database import async_session_factory
from src.core.redis import get_redis_client
from src.llm.attempts import (
    LLMAttemptLease,
    LLMAttemptStatus,
    begin_llm_attempt,
    record_llm_attempt_error,
    record_llm_attempt_success,
    release_llm_attempt_lock,
)
from src.llm.safety import PATH_QUALITY_MANAGER
from src.models.escalation import Escalation
from src.models.llm_attempt import LLMAttempt
from src.models.message import Message
from src.quality.manager_evaluator import (
    ManagerMetrics,
    escalation_already_reviewed,
    evaluate_manager_conversation,
    get_unreviewed_resolved_escalations,
    save_manager_review,
)
from src.quality.manager_schemas import ManagerEvaluationResult
from src.services.inbound_channels import (
    should_send_telegram_alert_for_conversation_with_db,
)

logger = logging.getLogger(__name__)

_OPENROUTER_PROVIDER = "openrouter"
_ENTITY_TYPE_ESCALATION = "escalation"
_PROMPT_VERSION_MANAGER = "quality-manager:v1"


def _resolve_redis(ctx: dict[str, Any]) -> Any:
    return ctx.get("redis") or get_redis_client()


def _normalise_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _stable_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, default=str, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _escalation_updated_at(escalation: Any) -> datetime:
    value = getattr(escalation, "updated_at", None) or getattr(
        escalation, "created_at", None
    )
    if isinstance(value, datetime):
        return _normalise_utc(value)
    return datetime.now(UTC)


def _attempt_input_hash(escalation: Any, activity_at: datetime) -> str:
    return _stable_hash(
        {
            "escalation_id": str(escalation.id),
            "conversation_id": str(escalation.conversation_id),
            "updated_at": _normalise_utc(activity_at).isoformat(),
            "status": getattr(escalation, "status", None),
            "assigned_to": getattr(escalation, "assigned_to", None),
            "prompt_version": _PROMPT_VERSION_MANAGER,
        }
    )


def _settings_hash() -> str:
    return _stable_hash(
        {
            "path": PATH_QUALITY_MANAGER,
            "prompt_version": _PROMPT_VERSION_MANAGER,
            "model": settings.openrouter_model_main,
            "provider": _OPENROUTER_PROVIDER,
        }
    )


def _evaluation_payload(evaluation: Any, metrics: Any) -> dict[str, Any]:
    model_dump = getattr(evaluation, "model_dump", None)
    evaluation_payload = (
        model_dump(mode="json") if callable(model_dump) else vars(evaluation)
    )
    return {
        "evaluation": evaluation_payload,
        "metrics": {
            "first_response_time_seconds": getattr(
                metrics, "first_response_time_seconds", None
            ),
            "message_count": getattr(metrics, "message_count", None),
            "deal_converted": getattr(metrics, "deal_converted", None),
            "deal_amount": getattr(metrics, "deal_amount", None),
        },
    }


async def _escalation_activity_at(db: Any, escalation: Any) -> datetime:
    anchor_at = getattr(escalation, "created_at", None)
    if not isinstance(anchor_at, datetime):
        return _escalation_updated_at(escalation)

    stmt = select(func.max(Message.created_at)).where(
        Message.conversation_id == escalation.conversation_id,
        Message.created_at >= anchor_at,
        Message.role.in_(("user", "manager")),
    )
    activity_at = await db.scalar(stmt)
    if isinstance(activity_at, datetime):
        return _normalise_utc(activity_at)
    return _escalation_updated_at(escalation)


async def _load_manager_attempt(
    db: Any,
    *,
    escalation_id: Any,
    entity_updated_at: datetime,
) -> LLMAttempt | None:
    stmt = select(LLMAttempt).where(
        LLMAttempt.path == PATH_QUALITY_MANAGER,
        LLMAttempt.entity_type == _ENTITY_TYPE_ESCALATION,
        LLMAttempt.entity_id == str(escalation_id),
        LLMAttempt.entity_updated_at == _normalise_utc(entity_updated_at),
        LLMAttempt.prompt_version == _PROMPT_VERSION_MANAGER,
    )
    result = await db.execute(stmt)
    attempt = result.scalar_one_or_none()
    if inspect.isawaitable(attempt):
        attempt = await attempt
    if attempt is None:
        return None
    if (
        attempt.entity_id != str(escalation_id)
        or attempt.entity_type != _ENTITY_TYPE_ESCALATION
    ):
        return None
    return cast("LLMAttempt", attempt)


def _manager_result_from_attempt_payload(
    payload: Any,
) -> tuple[ManagerEvaluationResult, ManagerMetrics]:
    evaluation_payload = (
        payload.get("evaluation") if isinstance(payload, dict) else None
    )
    metrics_payload = payload.get("metrics") if isinstance(payload, dict) else None
    if not isinstance(evaluation_payload, dict) or not isinstance(
        metrics_payload, dict
    ):
        raise ValueError("Invalid manager attempt payload")

    evaluation = ManagerEvaluationResult.model_validate(evaluation_payload)
    metrics = ManagerMetrics(
        first_response_time_seconds=metrics_payload.get("first_response_time_seconds"),
        message_count=metrics_payload.get("message_count"),
        deal_converted=bool(metrics_payload.get("deal_converted", False)),
        deal_amount=metrics_payload.get("deal_amount"),
    )
    return evaluation, metrics


async def _replay_terminal_manager_review(
    *,
    db: Any,
    redis: Any,
    escalation: Any,
    entity_updated_at: datetime,
) -> bool:
    if await escalation_already_reviewed(db, escalation.id):
        return False

    attempt = await _load_manager_attempt(
        db,
        escalation_id=escalation.id,
        entity_updated_at=entity_updated_at,
    )
    if attempt is None or attempt.status != LLMAttemptStatus.SUCCESS.value:
        return False
    if attempt.result_json is None:
        return False

    evaluation, metrics = _manager_result_from_attempt_payload(attempt.result_json)
    await save_manager_review(
        db=db,
        escalation_id=escalation.id,
        conversation_id=escalation.conversation_id,
        evaluation=evaluation,
        metrics=metrics,
        manager_name=escalation.assigned_to,
    )
    await _commit_or_rollback(db)

    if (
        evaluation.total_score < 9
        and await should_send_telegram_alert_for_conversation_with_db(
            escalation.conversation,
            db,
        )
    ):
        from src.services.notifications import (
            format_low_manager_score_alert_message,
            send_telegram_message,
        )

        alert_text = format_low_manager_score_alert_message(
            escalation_id=str(escalation.id),
            manager_name=escalation.assigned_to,
            score=evaluation.total_score,
            rating=evaluation.rating,
            summary=evaluation.summary[:200] if evaluation.summary else None,
        )
        await send_telegram_message(alert_text)
    return True


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


async def _load_escalation(db: Any, esc_id: Any) -> Any:
    esc_stmt = (
        select(Escalation)
        .options(selectinload(Escalation.conversation))
        .where(Escalation.id == esc_id)
    )
    esc_result = await db.execute(esc_stmt)
    return esc_result.scalar_one()


async def evaluate_escalated_conversations(ctx: dict[str, Any]) -> None:
    """ARQ job: evaluate resolved escalations without a manager review.

    Runs every 30 minutes via ARQ cron. Finds up to 50 resolved escalations
    with no manager_reviews entry and evaluates each using the LLM judge
    plus quantitative metrics.

    Args:
        ctx: ARQ job context (unused, but required by ARQ protocol).
    """
    redis = _resolve_redis(ctx)

    async with async_session_factory() as db:
        pending_ids = await get_unreviewed_resolved_escalations(db, limit=50)

    if not pending_ids:
        logger.info("Manager evaluator: no pending escalations to evaluate")
        return

    logger.info("Manager evaluator: found %d escalations to evaluate", len(pending_ids))

    evaluated = 0
    errors = 0

    for esc_id in pending_ids:
        lease: LLMAttemptLease | None = None
        send_low_score_alert = False
        try:
            async with async_session_factory() as db:
                # Re-check inside transaction — race condition guard
                if await escalation_already_reviewed(db, esc_id):
                    logger.info(
                        "Skipping escalation %s — already reviewed (race guard)",
                        esc_id,
                    )
                    continue

                escalation = await _load_escalation(db, esc_id)
                activity_at = await _escalation_activity_at(db, escalation)
                lease = await begin_llm_attempt(
                    db,
                    redis,
                    path=PATH_QUALITY_MANAGER,
                    entity_type=_ENTITY_TYPE_ESCALATION,
                    entity_id=esc_id,
                    entity_updated_at=activity_at,
                    prompt_version=_PROMPT_VERSION_MANAGER,
                    input_hash=_attempt_input_hash(escalation, activity_at),
                    settings_hash=_settings_hash(),
                    model=settings.openrouter_model_main,
                    provider=_OPENROUTER_PROVIDER,
                )
                if lease is None:
                    if await _replay_terminal_manager_review(
                        db=db,
                        redis=redis,
                        escalation=escalation,
                        entity_updated_at=activity_at,
                    ):
                        send_low_score_alert = False
                    continue

                try:
                    evaluation, metrics = await evaluate_manager_conversation(
                        esc_id, db
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
                    result_json=_evaluation_payload(evaluation, metrics),
                    model=settings.openrouter_model_main,
                    provider=_OPENROUTER_PROVIDER,
                )
                await _commit_or_rollback(db)

                try:
                    await save_manager_review(
                        db=db,
                        escalation_id=esc_id,
                        conversation_id=escalation.conversation_id,
                        evaluation=evaluation,
                        metrics=metrics,
                        manager_name=escalation.assigned_to,
                    )
                except Exception:
                    await db.rollback()
                    raise

                await _commit_or_rollback(db)

                if evaluation.total_score < 9:
                    send_low_score_alert = (
                        await should_send_telegram_alert_for_conversation_with_db(
                            escalation.conversation, db
                        )
                    )

            evaluated += 1
            logger.info(
                "Evaluated manager for escalation %s: score=%.1f rating=%s",
                esc_id,
                evaluation.total_score,
                evaluation.rating,
            )

            # Send Telegram alert for poor manager performance
            if evaluation.total_score < 9:
                try:
                    if not send_low_score_alert:
                        logger.info(
                            "Skipping low-score manager alert for %s due to inbound channel gating",
                            esc_id,
                        )
                        continue

                    from src.services.notifications import (
                        format_low_manager_score_alert_message,
                        send_telegram_message,
                    )

                    alert_text = format_low_manager_score_alert_message(
                        escalation_id=str(esc_id),
                        manager_name=escalation.assigned_to,
                        score=evaluation.total_score,
                        rating=evaluation.rating,
                        summary=evaluation.summary[:200]
                        if evaluation.summary
                        else None,
                    )
                    await send_telegram_message(alert_text)
                except Exception:
                    logger.exception(
                        "Failed to send manager alert for escalation %s", esc_id
                    )
        except Exception:
            errors += 1
            logger.exception("Failed to evaluate escalation %s", esc_id)
        finally:
            if lease is not None:
                await release_llm_attempt_lock(redis, lease)

    logger.info("Manager evaluator: done. evaluated=%d, errors=%d", evaluated, errors)
