"""ARQ background jobs for automatic quality evaluation."""

from __future__ import annotations

import logging
from typing import Any

from src.core.database import async_session_factory
from src.quality.evaluator import evaluate_conversation
from src.quality.service import (
    get_recent_conversation_ids_with_assistant_activity,
    save_review,
)

logger = logging.getLogger(__name__)


async def evaluate_completed_conversations(ctx: dict[str, Any]) -> None:
    """Backward-compatible wrapper around the rolling quality evaluator."""
    await evaluate_recent_conversations_quality(ctx)


async def evaluate_recent_conversations_quality(ctx: dict[str, Any]) -> None:
    """ARQ job: evaluate recent bot conversations and upsert current reviews."""
    async with async_session_factory() as db:
        pending_ids = await get_recent_conversation_ids_with_assistant_activity(
            db,
            limit=50,
        )

    if not pending_ids:
        logger.info("Quality evaluator: no recent assistant conversations to evaluate")
        return

    logger.info(
        "Quality evaluator: found %d recent conversations to evaluate",
        len(pending_ids),
    )

    evaluated = 0
    errors = 0

    for conv_id in pending_ids:
        try:
            async with async_session_factory() as db:
                result = await evaluate_conversation(conv_id, db)
                await save_review(db, conv_id, result)
                await db.commit()
            evaluated += 1
            logger.info(
                "Evaluated conversation %s: score=%.1f rating=%s",
                conv_id,
                result.total_score,
                result.rating,
            )

            # Send Telegram alert for poor quality dialogues
            if result.total_score < 14:
                try:
                    from src.services.notifications import notify_quality_alert

                    await notify_quality_alert(
                        conv_id,
                        score=result.total_score,
                        rating=result.rating,
                        summary=result.summary,
                    )
                except Exception:
                    logger.exception("Failed to send quality alert for %s", conv_id)
        except Exception:
            errors += 1
            logger.exception(
                "Failed to evaluate conversation %s (%d/%d)",
                conv_id,
                pending_ids.index(conv_id) + 1,
                len(pending_ids),
            )

    logger.info(
        "Rolling quality evaluator: done. evaluated=%d, errors=%d",
        evaluated,
        errors,
    )
