"""ARQ background job for automatic quality evaluation.

Runs hourly to find closed conversations without a quality review
and evaluates them using the LLM judge.
"""
from __future__ import annotations

import logging
from typing import Any

from src.core.database import async_session_factory
from src.quality.evaluator import evaluate_conversation
from src.quality.service import (
    conversation_already_reviewed,
    get_unreviewed_completed_conversations,
    save_review,
)

logger = logging.getLogger(__name__)


async def evaluate_completed_conversations(ctx: dict[str, Any]) -> None:
    """ARQ job: evaluate completed conversations without a quality review.

    Runs hourly via ARQ cron. Finds up to 50 closed conversations
    with no quality_reviews entry and evaluates each using the LLM judge.

    Args:
        ctx: ARQ job context (unused, but required by ARQ protocol).
    """
    async with async_session_factory() as db:
        pending_ids = await get_unreviewed_completed_conversations(db, limit=50)

    if not pending_ids:
        logger.info("Quality evaluator: no pending conversations to evaluate")
        return

    logger.info(
        "Quality evaluator: found %d conversations to evaluate", len(pending_ids)
    )

    evaluated = 0
    errors = 0

    for conv_id in pending_ids:
        try:
            async with async_session_factory() as db:
                # Re-check inside transaction — race condition guard when max_jobs > 1
                if await conversation_already_reviewed(db, conv_id):
                    logger.info("Skipping %s — already reviewed (race guard)", conv_id)
                    continue
                result = await evaluate_conversation(conv_id, db)
                await save_review(db, conv_id, result)
                await db.commit()
            evaluated += 1
            logger.info(
                "Evaluated conversation %s: score=%.1f rating=%s",
                conv_id, result.total_score, result.rating
            )
        except Exception:
            errors += 1
            logger.exception("Failed to evaluate conversation %s", conv_id)

    logger.info(
        "Quality evaluator: done. evaluated=%d, errors=%d", evaluated, errors
    )
