"""Quality API endpoints — conversation quality reviews and reports."""

from __future__ import annotations

import asyncio
import logging
import math
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic_ai import UnexpectedModelBehavior
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db
from src.quality.evaluator import evaluate_conversation
from src.quality.service import conversation_already_reviewed, get_reviews, save_review
from src.schemas import (
    PaginatedResponse,
    QualityReportRequest,
    QualityReportResponse,
    QualityReviewCreate,
    QualityReviewRead,
)

router = APIRouter()
logger = logging.getLogger(__name__)

DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.get("/reviews/", response_model=PaginatedResponse[QualityReviewRead])
async def list_reviews(
    db: DbSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    min_score: float | None = Query(None, ge=0, le=30),
    conversation_id: uuid.UUID | None = Query(None),
) -> PaginatedResponse[QualityReviewRead]:
    """List quality reviews with optional filters.

    Supports pagination and filtering by minimum score and conversation ID.
    """
    items, total = await get_reviews(
        db,
        page=page,
        page_size=page_size,
        min_score=min_score,
        conversation_id=conversation_id,
    )
    pages = math.ceil(total / page_size) if total > 0 else 1
    return PaginatedResponse(
        items=[QualityReviewRead.model_validate(r) for r in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.post("/reviews/", response_model=QualityReviewRead, status_code=201)
async def create_review(
    body: QualityReviewCreate,
    db: DbSession,
) -> QualityReviewRead:
    """Trigger LLM evaluation for a conversation and store the result.

    If the conversation has already been reviewed, raises 409 Conflict.
    """
    already = await conversation_already_reviewed(db, body.conversation_id)
    if already:
        raise HTTPException(
            status_code=409,
            detail=f"Conversation {body.conversation_id} has already been reviewed.",
        )

    try:
        result = await asyncio.wait_for(
            evaluate_conversation(body.conversation_id, db),
            timeout=60.0,  # CR-06: prevent client hanging indefinitely
        )
    except TimeoutError as e:
        raise HTTPException(status_code=504, detail="LLM evaluation timed out") from e
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except UnexpectedModelBehavior as e:
        logger.error(
            "LLM judge failed for conversation %s: %s", body.conversation_id, e
        )
        raise HTTPException(
            status_code=502, detail="LLM evaluation failed after retries"
        ) from e

    review = await save_review(db, body.conversation_id, result)
    await db.commit()
    return QualityReviewRead.model_validate(review)


@router.post("/reports/", response_model=QualityReportResponse)
async def generate_report(
    body: QualityReportRequest,
) -> QualityReportResponse:
    """Generate an aggregate quality report for a period.

    Not yet implemented — coming in Week 11.
    """
    raise HTTPException(status_code=501, detail="Not implemented")
