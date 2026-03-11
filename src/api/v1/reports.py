"""API endpoints for report generation and retrieval."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from src.core.database import async_session_factory
from src.services.reports import ReportData, format_report_text, generate_report

router = APIRouter()


class ReportRequest(BaseModel):
    """Request body for report generation."""

    start_date: datetime | None = None
    end_date: datetime | None = None


class ReportResponse(BaseModel):
    """API response with report data and formatted text."""

    data: ReportData
    text: str


@router.post("/generate", response_model=ReportResponse)
async def generate_report_endpoint(request: ReportRequest) -> ReportResponse:
    """Generate a report for the specified period.

    Defaults to the last 7 days if no dates are provided.
    """
    async with async_session_factory() as db:
        report = await generate_report(
            db,
            start_date=request.start_date,
            end_date=request.end_date,
        )

    return ReportResponse(
        data=report,
        text=format_report_text(report),
    )


@router.get("/")
async def list_reports() -> list[dict[str, str]]:
    """List generated reports.

    Currently returns empty list — reports are generated on-demand.
    """
    return []
