from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from src.schemas import (
    PaginatedResponse,
    QualityReportRequest,
    QualityReportResponse,
    QualityReviewCreate,
    QualityReviewRead,
)

router = APIRouter()


@router.get("/reviews/", response_model=PaginatedResponse[QualityReviewRead])
async def list_reviews(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[QualityReviewRead]:
    """List quality reviews with pagination."""
    raise HTTPException(status_code=501, detail="Not implemented")


@router.post("/reviews/", response_model=QualityReviewRead)
async def create_review(
    body: QualityReviewCreate,
) -> QualityReviewRead:
    """Create a quality review for a conversation."""
    raise HTTPException(status_code=501, detail="Not implemented")


@router.post("/reports/", response_model=QualityReportResponse)
async def generate_report(
    body: QualityReportRequest,
) -> QualityReportResponse:
    """Generate an aggregate quality report for a period."""
    raise HTTPException(status_code=501, detail="Not implemented")
