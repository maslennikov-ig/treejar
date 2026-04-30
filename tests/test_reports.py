"""Tests for report generation service (TDD)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

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
    assert report.refusal_count == 0
    assert report.refusal_rate == 0.0
    assert report.feedback_count == 0
    assert report.llm_cost_usd == 0.0
    assert report.qa_llm_cost_usd == 0.0
    assert report.qa_llm_attempts_count == 0
    assert report.qa_cached_tokens == 0


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
    assert "Недельный отчёт" in text
    assert "Диалоги" in text
    assert "клиент недоволен" in text


def test_format_report_text_localizes_manager_metrics() -> None:
    """format_report_text should use Russian labels for manager metrics."""
    from src.services.reports import ReportData, format_report_text

    now = datetime.now(tz=UTC)
    report = ReportData(
        period_start=now,
        period_end=now,
        manager_reviews_count=4,
        avg_manager_score=12.5,
        avg_manager_response_time_seconds=1800,
        manager_deal_conversion_rate=25.0,
        top_managers=[{"name": "Анна", "avg_score": 15.5}],
    )

    text = format_report_text(report)

    assert "Показатели менеджеров" in text
    assert "Средний балл" in text
    assert "Среднее время ответа" in text
    assert "Лучшие" in text


def test_format_report_text_contains_final_acceptance_fields() -> None:
    """Weekly report text should include refusal, feedback, and cost controls."""
    from src.services.reports import ReportData, format_report_text

    now = datetime.now(tz=UTC)
    report = ReportData(
        period_start=now,
        period_end=now,
        total_conversations=20,
        total_deals=5,
        conversion_rate=25.0,
        refusal_count=3,
        refusal_rate=15.0,
        feedback_count=4,
        avg_feedback_rating=4.5,
        avg_delivery_rating=4.0,
        feedback_recommend_rate=75.0,
        feedback_nps_score=50.0,
        llm_cost_usd=0.1234,
        qa_llm_cost_usd=0.0123,
        qa_llm_attempts_count=6,
        qa_budget_blocked_count=1,
        qa_prompt_tokens=1200,
        qa_completion_tokens=300,
        qa_reasoning_tokens=20,
        qa_cached_tokens=900,
        qa_cache_write_tokens=40,
    )

    text = format_report_text(report)

    assert "Отказы" in text
    assert "3 (15.0%)" in text
    assert "Обратная связь" in text
    assert "4.5/5" in text
    assert "75.0%" in text
    assert "Контроль LLM расходов" in text
    assert "$0.1234" in text
    assert "$0.0123" in text
    assert "cache" in text.lower()


@pytest.mark.asyncio
async def test_generate_report_populates_final_acceptance_fields() -> None:
    """generate_report should aggregate feedback, refusal, and LLM cost fields."""
    from src.services.reports import generate_report

    mock_db = AsyncMock()

    conv_result = MagicMock()
    conv_result.one.return_value = (20, 15)

    deals_result = MagicMock()
    deals_result.one.return_value = (5, 1200.0)

    esc_reasons_result = MagicMock()
    esc_reasons_result.all.return_value = []

    top_prod_result = MagicMock()
    top_prod_result.all.return_value = []

    manager_result = MagicMock()
    manager_result.one.return_value = (16.0, 600.0, 3, 2)

    top_manager_result = MagicMock()
    top_manager_result.all.return_value = []

    feedback_result = MagicMock()
    feedback_result.one.return_value = (4, 4.5, 4.0, 3, 1)

    qa_cost_result = MagicMock()
    qa_cost_result.one.return_value = (6, 0.0123, 1200, 300, 20, 900, 40, 1)

    mock_db.execute.side_effect = [
        conv_result,
        deals_result,
        esc_reasons_result,
        top_prod_result,
        manager_result,
        top_manager_result,
        feedback_result,
        qa_cost_result,
    ]
    mock_db.scalar.side_effect = [
        24.0,
        2,
        3,
        0.1234,
    ]

    start = datetime(2026, 4, 1, tzinfo=UTC)
    end = datetime(2026, 4, 8, tzinfo=UTC)
    report = await generate_report(mock_db, start_date=start, end_date=end)

    assert report.avg_quality_score == 24.0
    assert report.escalation_count == 2
    assert report.refusal_count == 3
    assert report.refusal_rate == 15.0
    assert report.feedback_count == 4
    assert report.avg_feedback_rating == 4.5
    assert report.avg_delivery_rating == 4.0
    assert report.feedback_recommend_rate == 75.0
    assert report.feedback_nps_score == 50.0
    assert report.llm_cost_usd == 0.1234
    assert report.qa_llm_cost_usd == 0.0123
    assert report.qa_llm_attempts_count == 6
    assert report.qa_budget_blocked_count == 1
    assert report.qa_prompt_tokens == 1200
    assert report.qa_completion_tokens == 300
    assert report.qa_reasoning_tokens == 20
    assert report.qa_cached_tokens == 900
    assert report.qa_cache_write_tokens == 40


def test_format_report_text_empty_report() -> None:
    """format_report_text should handle empty report gracefully."""
    from src.services.reports import ReportData, format_report_text

    now = datetime.now(tz=UTC)
    report = ReportData(period_start=now, period_end=now)
    text = format_report_text(report)
    assert "Недельный отчёт" in text
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
