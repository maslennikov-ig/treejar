"""Quality persistence service — DB operations for quality reviews.

Provides functions to save, retrieve, and query quality reviews
in the quality_reviews table.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.conversation import Conversation
from src.models.message import Message
from src.models.quality_review import QualityReview
from src.quality.schemas import EvaluationResult, compute_rating

logger = logging.getLogger(__name__)


async def save_review(
    db: AsyncSession,
    conversation_id: UUID,
    result: EvaluationResult,
) -> QualityReview:
    """Save an EvaluationResult to the database as a QualityReview.

    Args:
        db: Async SQLAlchemy session.
        conversation_id: UUID of the evaluated conversation.
        result: Structured LLM evaluation result.

    Returns:
        Persisted QualityReview ORM object.
    """
    # Convert internal schema criteria to JSON-serialisable dict
    criteria_data: list[dict[str, Any]] = [
        {
            "rule_number": c.rule_number,
            "rule_name": c.rule_name,
            "score": c.score,
            "max_score": 2,
            "comment": c.comment,
        }
        for c in result.criteria
    ]

    # Compute score deterministically — don't trust LLM arithmetic
    computed_total = float(sum(c.score for c in result.criteria))
    rating_str = compute_rating(computed_total)

    existing_stmt = select(QualityReview).where(
        QualityReview.conversation_id == conversation_id
    )
    existing_result = await db.execute(existing_stmt)
    review = existing_result.scalar_one_or_none()

    if review is None:
        review = QualityReview(
            conversation_id=conversation_id,
            total_score=computed_total,
            max_score=30,
            criteria=criteria_data,
            rating=rating_str,
            summary=result.summary,
            reviewer="ai",
        )
        db.add(review)
    else:
        review.total_score = computed_total
        review.max_score = 30
        review.criteria = criteria_data
        review.rating = rating_str
        review.summary = result.summary
        review.reviewer = "ai"

    await db.flush()  # get the ID without committing
    return review


async def conversation_already_reviewed(
    db: AsyncSession,
    conversation_id: UUID,
) -> bool:
    """Check if a conversation already has a quality review.

    Args:
        db: Async SQLAlchemy session.
        conversation_id: UUID to check.

    Returns:
        True if at least one review exists for this conversation.
    """
    stmt = (
        select(func.count())
        .select_from(QualityReview)
        .where(QualityReview.conversation_id == conversation_id)
    )
    result = await db.execute(stmt)
    count = result.scalar_one()
    return count > 0


async def get_unreviewed_completed_conversations(
    db: AsyncSession,
    limit: int = 50,
) -> list[UUID]:
    """Find closed conversations that have not been reviewed yet.

    A conversation is eligible for review if:
    - status == 'closed'
    - No entry in quality_reviews for this conversation_id

    Args:
        db: Async SQLAlchemy session.
        limit: Maximum number of conversation IDs to return.

    Returns:
        List of conversation UUIDs eligible for evaluation.
    """
    stmt = (
        select(Conversation.id)
        .where(
            Conversation.status == "closed",
            ~exists().where(QualityReview.conversation_id == Conversation.id),
        )
        .order_by(Conversation.updated_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


def _normalize_naive_utc(value: datetime) -> datetime:
    """Normalize datetimes to naive UTC for timestamp-without-time-zone columns."""
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


async def get_recent_conversation_ids_with_assistant_activity(
    db: AsyncSession,
    *,
    since: datetime | None = None,
    limit: int = 50,
) -> list[UUID]:
    """Return recent conversation IDs with assistant activity ordered by latest turn.

    This powers rolling quality evaluation for active bot dialogues.
    """
    threshold = _normalize_naive_utc(since or (datetime.now(UTC) - timedelta(days=1)))
    stmt = (
        select(
            Message.conversation_id,
            func.max(Message.created_at).label("last_assistant_at"),
        )
        .where(
            Message.role == "assistant",
            Message.created_at >= threshold,
        )
        .group_by(Message.conversation_id)
        .order_by(func.max(Message.created_at).desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return [row.conversation_id for row in result.all()]


async def get_reviews(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    min_score: float | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    conversation_id: UUID | None = None,
) -> tuple[list[QualityReview], int]:
    """List quality reviews with optional filters.

    Args:
        db: Async SQLAlchemy session.
        page: 1-based page number.
        page_size: Number of results per page.
        min_score: Only return reviews with total_score >= min_score.
        date_from: Only return reviews created on or after this date.
        date_to: Only return reviews created on or before this date.
        conversation_id: Filter to a specific conversation.

    Returns:
        Tuple of (list of QualityReview items, total count).
    """
    base_stmt = select(QualityReview)
    count_stmt = select(func.count()).select_from(QualityReview)

    filters = []
    if min_score is not None:
        filters.append(QualityReview.total_score >= min_score)
    if date_from is not None:
        # Normalize to UTC — server_default=func.now() stores UTC
        if date_from.tzinfo is None:
            date_from = date_from.replace(tzinfo=UTC)
        filters.append(QualityReview.created_at >= date_from)
    if date_to is not None:
        if date_to.tzinfo is None:
            date_to = date_to.replace(tzinfo=UTC)
        filters.append(QualityReview.created_at <= date_to)
    if conversation_id is not None:
        filters.append(QualityReview.conversation_id == conversation_id)

    if filters:
        base_stmt = base_stmt.where(*filters)
        count_stmt = count_stmt.where(*filters)

    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    offset = (page - 1) * page_size
    items_result = await db.execute(
        base_stmt.order_by(QualityReview.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    items = list(items_result.scalars().all())
    return items, total
