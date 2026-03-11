"""Tests for report generation service (TDD)."""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# =============================================================================
# ReportData structure tests
# =============================================================================


def test_report_data_defaults() -> None:
    """ReportData should have sensible defaults."""
    from src.services.reports import ReportData

    now = datetime.now(tz=UTC)
    report = ReportData(period_start=now, period_end=now)
    assert report.total_conversations == 0
    assert report.conversion_rate == 0.0
    assert report.escalation_reasons == {}
    assert report.top_products == []


def test_format_report_text_contains_key_fields() -> None:
    """format_report_text should include all key metrics."""
    from src.services.reports import ReportData, format_report_text

    now = datetime.now(tz=UTC)
    report = ReportData(
        period_start=now,
        period_end=now,
        total_conversations=42,
        conversations_per_day=6.0,
        unique_customers=30,
        total_deals=5,
        conversion_rate=11.9,
        avg_deal_value=5000.0,
        avg_quality_score=22.5,
        escalation_count=3,
        escalation_reasons={"customer_angry": 2, "complex_order": 1},
        top_products=[
            {"name": "Executive Desk", "sku": "ED-001", "mentions": 10},
        ],
    )
    text = format_report_text(report)
    assert "42" in text
    assert "11.9%" in text
    assert "22.5" in text
    assert "Executive Desk" in text
    assert "customer_angry" in text


def test_format_report_text_empty_report() -> None:
    """format_report_text should handle empty report gracefully."""
    from src.services.reports import ReportData, format_report_text

    now = datetime.now(tz=UTC)
    report = ReportData(period_start=now, period_end=now)
    text = format_report_text(report)
    assert "Weekly Report" in text
    assert "0" in text


# =============================================================================
# API tests
# =============================================================================


@pytest.mark.asyncio
async def test_api_reports_list() -> None:
    """GET /api/v1/reports/ should return empty list."""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get("/api/v1/reports/")
    assert resp.status_code == 200
    assert resp.json() == []
