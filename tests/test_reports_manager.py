"""Tests for Telegram report manager section (Component 10).

Verifies:
- ReportData includes manager fields
- format_report_text includes manager section when data present
- No manager section when count is 0
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from src.services.reports import ReportData, format_report_text


def test_report_data_has_manager_fields() -> None:
    """ReportData includes manager performance fields."""
    now = datetime.now(tz=UTC)
    data = ReportData(period_start=now - timedelta(days=7), period_end=now)

    assert hasattr(data, "avg_manager_score")
    assert hasattr(data, "avg_manager_response_time_seconds")
    assert hasattr(data, "manager_deal_conversion_rate")
    assert hasattr(data, "manager_reviews_count")
    assert hasattr(data, "top_managers")


def test_format_report_includes_manager_section() -> None:
    """format_report_text includes Manager Performance section."""
    now = datetime.now(tz=UTC)
    data = ReportData(
        period_start=now - timedelta(days=7),
        period_end=now,
        total_conversations=50,
        avg_manager_score=16.2,
        avg_manager_response_time_seconds=480.0,
        manager_deal_conversion_rate=65.0,
        manager_reviews_count=12,
        top_managers=[
            {"name": "Israullah", "avg_score": 17.5},
            {"name": "Annabelle", "avg_score": 16.8},
        ],
    )

    text = format_report_text(data)

    assert "Manager Performance" in text
    assert "16.2/20" in text
    assert "8.0 min" in text
    assert "65.0%" in text
    assert "12" in text
    assert "Israullah" in text
    assert "Annabelle" in text


def test_format_report_no_manager_section_when_empty() -> None:
    """No manager section when manager_reviews_count is 0."""
    now = datetime.now(tz=UTC)
    data = ReportData(
        period_start=now - timedelta(days=7),
        period_end=now,
    )

    text = format_report_text(data)

    assert "Manager Performance" not in text
