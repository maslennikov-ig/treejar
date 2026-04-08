"""ARQ background job for automatic manager evaluation.

Runs every 30 minutes to find resolved escalations without a manager_review
and evaluates them using the LLM judge + quantitative metrics.

See: src/quality/job.py for bot quality evaluation (similar pattern).
"""

from __future__ import annotations

import logging
from typing import Any

from src.core.database import async_session_factory
from src.quality.manager_evaluator import (
    escalation_already_reviewed,
    evaluate_manager_conversation,
    get_unreviewed_resolved_escalations,
    save_manager_review,
)
from src.services.inbound_channels import (
    should_send_telegram_alert_for_conversation_with_db,
)

logger = logging.getLogger(__name__)


async def evaluate_escalated_conversations(ctx: dict[str, Any]) -> None:
    """ARQ job: evaluate resolved escalations without a manager review.

    Runs every 30 minutes via ARQ cron. Finds up to 50 resolved escalations
    with no manager_reviews entry and evaluates each using the LLM judge
    plus quantitative metrics.

    Args:
        ctx: ARQ job context (unused, but required by ARQ protocol).
    """
    async with async_session_factory() as db:
        pending_ids = await get_unreviewed_resolved_escalations(db, limit=50)

    if not pending_ids:
        logger.info("Manager evaluator: no pending escalations to evaluate")
        return

    logger.info("Manager evaluator: found %d escalations to evaluate", len(pending_ids))

    evaluated = 0
    errors = 0

    for esc_id in pending_ids:
        try:
            async with async_session_factory() as db:
                # Re-check inside transaction — race condition guard
                if await escalation_already_reviewed(db, esc_id):
                    logger.info(
                        "Skipping escalation %s — already reviewed (race guard)",
                        esc_id,
                    )
                    continue

                evaluation, metrics = await evaluate_manager_conversation(esc_id, db)

                # Get manager name from escalation
                from sqlalchemy import select
                from sqlalchemy.orm import selectinload

                from src.models.escalation import Escalation

                esc_stmt = (
                    select(Escalation)
                    .options(selectinload(Escalation.conversation))
                    .where(Escalation.id == esc_id)
                )
                esc_result = await db.execute(esc_stmt)
                escalation = esc_result.scalar_one()

                await save_manager_review(
                    db=db,
                    escalation_id=esc_id,
                    conversation_id=escalation.conversation_id,
                    evaluation=evaluation,
                    metrics=metrics,
                    manager_name=escalation.assigned_to,
                )
                await db.commit()

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
                    if not await should_send_telegram_alert_for_conversation_with_db(
                        escalation.conversation, db
                    ):
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

    logger.info("Manager evaluator: done. evaluated=%d, errors=%d", evaluated, errors)
