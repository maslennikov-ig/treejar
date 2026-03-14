"""Manager reviews API router (Component 8).

Endpoints:
- GET /  — list reviews with filters
- GET /{review_id} — review details
- POST /{escalation_id}/evaluate — manual evaluation trigger
"""

from __future__ import annotations

import logging
import math
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db
from src.models.manager_review import ManagerReview
from src.schemas.common import PaginatedResponse
from src.schemas.manager_review import ManagerReviewDetail, ManagerReviewRead

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_model=PaginatedResponse[ManagerReviewRead])
async def list_manager_reviews(
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    manager_name: str | None = None,
    rating: str | None = None,
    period: str | None = None,
) -> PaginatedResponse[ManagerReviewRead]:
    """List manager reviews with optional filters."""
    from datetime import UTC, datetime, timedelta

    base_stmt = select(ManagerReview)
    count_stmt = select(func.count()).select_from(ManagerReview)

    filters = []
    if manager_name:
        filters.append(ManagerReview.manager_name == manager_name)
    if rating:
        filters.append(ManagerReview.rating == rating)
    if period:
        now = datetime.now(tz=UTC)
        match period:
            case "day":
                filters.append(ManagerReview.created_at >= now - timedelta(days=1))
            case "week":
                filters.append(ManagerReview.created_at >= now - timedelta(weeks=1))
            case "month":
                filters.append(ManagerReview.created_at >= now - timedelta(days=30))

    if filters:
        base_stmt = base_stmt.where(*filters)
        count_stmt = count_stmt.where(*filters)

    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    offset = (page - 1) * page_size
    items_result = await db.execute(
        base_stmt.order_by(ManagerReview.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    items = [ManagerReviewRead.model_validate(r) for r in items_result.scalars().all()]

    return PaginatedResponse[ManagerReviewRead](
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if page_size > 0 else 0,
    )


@router.get("/{review_id}", response_model=ManagerReviewDetail)
async def get_manager_review(
    review_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> ManagerReviewDetail:
    """Get detailed manager review by ID."""
    stmt = select(ManagerReview).where(ManagerReview.id == review_id)
    result = await db.execute(stmt)
    review = result.scalar_one_or_none()

    if review is None:
        raise HTTPException(status_code=404, detail="Manager review not found")

    return ManagerReviewDetail.model_validate(review)


@router.post("/{escalation_id}/evaluate", response_model=ManagerReviewDetail)
async def evaluate_escalation(
    escalation_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> ManagerReviewDetail:
    """Manually trigger evaluation for a specific escalation."""
    from src.quality.manager_evaluator import (
        escalation_already_reviewed,
        evaluate_manager_conversation,
        save_manager_review,
    )

    # Check if already reviewed
    if await escalation_already_reviewed(db, escalation_id):
        raise HTTPException(
            status_code=409, detail="Escalation already has a manager review"
        )

    try:
        evaluation, metrics = await evaluate_manager_conversation(escalation_id, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    # Get manager name from escalation
    from src.models.escalation import Escalation

    esc_stmt = select(Escalation).where(Escalation.id == escalation_id)
    esc_result = await db.execute(esc_stmt)
    escalation = esc_result.scalar_one_or_none()

    if escalation is None:
        raise HTTPException(status_code=404, detail="Escalation not found")

    review = await save_manager_review(
        db=db,
        escalation_id=escalation_id,
        conversation_id=escalation.conversation_id,
        evaluation=evaluation,
        metrics=metrics,
        manager_name=escalation.assigned_to,
    )
    await db.commit()

    return ManagerReviewDetail.model_validate(review)
