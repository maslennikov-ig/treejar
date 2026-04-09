"""ARQ background jobs for bot quality monitoring."""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

from src.core.database import async_session_factory
from src.core.redis import get_redis_client
from src.integrations.crm.zoho_crm import ZohoCRMClient
from src.quality.evaluator import evaluate_conversation, evaluate_red_flags
from src.quality.schemas import RedFlagItem
from src.quality.service import (
    QualityConversationCandidate,
    get_recent_assistant_conversation_candidates,
    get_recent_updated_conversation_candidates,
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


def _normalise_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _updated_at_iso(value: datetime) -> str:
    return _normalise_utc(value).isoformat()


def _red_flag_marker_key(conversation_id: Any) -> str:
    return f"quality:redflag:{conversation_id}"


def _final_marker_key(conversation_id: Any) -> str:
    return f"quality:final:{conversation_id}"


def _build_red_flag_signature(flags: list[RedFlagItem]) -> str:
    joined_codes = "|".join(sorted(flag.code for flag in flags))
    return hashlib.sha256(joined_codes.encode("utf-8")).hexdigest()


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
        "last_activity_at": candidate.updated_at,
    }


async def _load_candidates_in_batches(
    fetch_page: Callable[..., Awaitable[list[QualityConversationCandidate]]],
    *,
    since: datetime,
) -> list[QualityConversationCandidate]:
    """Read the full eligible candidate set in deterministic pages."""
    candidates: list[QualityConversationCandidate] = []
    offset = 0

    async with async_session_factory() as db:
        while True:
            batch = await fetch_page(
                db,
                since=since,
                limit=_QUERY_BATCH_SIZE,
                offset=offset,
            )
            if not batch:
                break
            candidates.extend(batch)
            if len(batch) < _QUERY_BATCH_SIZE:
                break
            offset += len(batch)

    return candidates


def _final_review_trigger(
    candidate: QualityConversationCandidate,
    *,
    now: datetime,
) -> str | None:
    if candidate.status == "closed":
        return "closed"
    if _normalise_utc(candidate.updated_at) <= now - _FINAL_IDLE_THRESHOLD:
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
    now = datetime.now(UTC)
    redis = _resolve_redis(ctx)
    candidates = await _load_candidates_in_batches(
        get_recent_assistant_conversation_candidates,
        since=now - _RED_FLAG_LOOKBACK,
    )

    if not candidates:
        logger.info("Quality red-flag evaluator: no recent assistant conversations")
        return

    sent = 0
    errors = 0

    async with _quality_crm_client(ctx, redis) as crm_client:
        for candidate in candidates:
            try:
                async with async_session_factory() as db:
                    result = await evaluate_red_flags(candidate.conversation_id, db)

                    if not result.flags:
                        continue
                    should_notify = (
                        await should_send_telegram_alert_for_conversation_with_db(
                            candidate, db
                        )
                    )

                signature = _build_red_flag_signature(result.flags)
                marker_key = _red_flag_marker_key(candidate.conversation_id)
                previous_signature = _extract_previous_signature(
                    await redis.get(marker_key)
                )

                if previous_signature == signature:
                    continue

                if not should_notify:
                    logger.info(
                        "Skipping red-flag warning for %s due to inbound channel gating",
                        candidate.conversation_id,
                    )
                    await redis.setex(
                        marker_key,
                        _RED_FLAG_TTL_SECONDS,
                        json.dumps(
                            {
                                "signature": signature,
                                "updated_at": _updated_at_iso(candidate.updated_at),
                            }
                        ),
                    )
                    continue

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
                            "updated_at": _updated_at_iso(candidate.updated_at),
                        }
                    ),
                )
                sent += 1
            except Exception:
                errors += 1
                logger.exception(
                    "Failed to evaluate realtime red flags for conversation %s",
                    candidate.conversation_id,
                )

    logger.info(
        "Quality red-flag evaluator: done. sent=%d, errors=%d",
        sent,
        errors,
    )


async def evaluate_mature_conversations_quality(ctx: dict[str, Any]) -> None:
    """ARQ job: persist and send owner-facing final reviews for mature dialogues."""
    now = datetime.now(UTC)
    redis = _resolve_redis(ctx)
    candidates = await _load_candidates_in_batches(
        get_recent_updated_conversation_candidates,
        since=now - _FINAL_LOOKBACK,
    )

    if not candidates:
        logger.info("Quality final-review evaluator: no recent conversations")
        return

    reviewed = 0
    errors = 0

    async with _quality_crm_client(ctx, redis) as crm_client:
        for candidate in candidates:
            trigger = _final_review_trigger(candidate, now=now)
            if trigger is None:
                continue

            current_updated_at = _updated_at_iso(candidate.updated_at)
            marker_key = _final_marker_key(candidate.conversation_id)
            previous_updated_at = await redis.get(marker_key)
            if previous_updated_at == current_updated_at:
                continue

            try:
                async with async_session_factory() as db:
                    result = await evaluate_conversation(
                        candidate.conversation_id,
                        db,
                        candidate.sales_stage,
                    )
                    await save_review(db, candidate.conversation_id, result)
                    await db.commit()
                    should_notify = (
                        await should_send_telegram_alert_for_conversation_with_db(
                            candidate, db
                        )
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
                reviewed += 1
            except Exception:
                errors += 1
                logger.exception(
                    "Failed to evaluate mature conversation %s",
                    candidate.conversation_id,
                )

    logger.info(
        "Quality final-review evaluator: done. reviewed=%d, errors=%d",
        reviewed,
        errors,
    )
