"""Tests for the dedicated daily summary calculator."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.dialects import postgresql


@pytest.mark.asyncio
async def test_calculate_daily_summary_with_values() -> None:
    """Daily summary should aggregate the expected metrics."""
    from src.services.daily_summary import calculate_daily_summary

    db = AsyncMock()
    now = datetime(2026, 4, 4, 12, 0, tzinfo=UTC)

    conv_result = MagicMock()
    conv_result.one.return_value = MagicMock(
        total_conversations=13,
        unique_customers=9,
        escalation_count=3,
    )

    esc_result = MagicMock()
    esc_result.one.return_value = MagicMock(escalation_count=3)

    quality_result = MagicMock()
    quality_result.one.return_value = MagicMock(avg_quality_score=22.5)

    delivered_result = MagicMock()
    delivered_result.one.return_value = MagicMock(delivered_deals=5)

    assistant_result = MagicMock()
    assistant_result.one.return_value = MagicMock(assistant_conversations=20)

    db.execute.side_effect = [
        conv_result,
        esc_result,
        quality_result,
        delivered_result,
        assistant_result,
    ]

    report = await calculate_daily_summary(db, now=now)

    assert report.period_start == now.replace(tzinfo=None) - timedelta(days=1)
    assert report.total_conversations == 13
    assert report.unique_customers == 9
    assert report.escalation_count == 3
    assert report.avg_quality_score == 22.5
    assert report.conversion_rate_7d == 25.0


@pytest.mark.asyncio
async def test_calculate_daily_summary_uses_na_for_missing_basis() -> None:
    """Missing quality or conversion basis should yield N/A-friendly None values."""
    from src.services.daily_summary import calculate_daily_summary

    db = AsyncMock()
    now = datetime(2026, 4, 4, 12, 0, tzinfo=UTC)

    conv_result = MagicMock()
    conv_result.one.return_value = MagicMock(
        total_conversations=0,
        unique_customers=0,
    )

    esc_result = MagicMock()
    esc_result.one.return_value = MagicMock(escalation_count=0)

    quality_result = MagicMock()
    quality_result.one.return_value = MagicMock(avg_quality_score=None)

    delivered_result = MagicMock()
    delivered_result.one.return_value = MagicMock(delivered_deals=0)

    assistant_result = MagicMock()
    assistant_result.one.return_value = MagicMock(assistant_conversations=0)

    db.execute.side_effect = [
        conv_result,
        esc_result,
        quality_result,
        delivered_result,
        assistant_result,
    ]

    report = await calculate_daily_summary(db, now=now)

    assert report.avg_quality_score is None
    assert report.conversion_rate_7d is None
    assert report.total_conversations == 0


@pytest.mark.asyncio
async def test_calculate_daily_summary_uses_separate_7d_activity_window() -> None:
    """Conversion denominator must use a 7-day assistant-activity window."""
    from src.services.daily_summary import calculate_daily_summary

    db = AsyncMock()
    now = datetime(2026, 4, 4, 12, 0, tzinfo=UTC)
    executed: list[object] = []

    def _row(**values: object) -> MagicMock:
        return MagicMock(**values)

    results = [
        MagicMock(
            one=MagicMock(return_value=_row(total_conversations=1, unique_customers=1))
        ),
        MagicMock(one=MagicMock(return_value=_row(escalation_count=0))),
        MagicMock(one=MagicMock(return_value=_row(avg_quality_score=20.0))),
        MagicMock(one=MagicMock(return_value=_row(delivered_deals=1))),
        MagicMock(one=MagicMock(return_value=_row(assistant_conversations=4))),
    ]

    async def _execute(stmt: object, *args: object, **kwargs: object) -> MagicMock:
        executed.append(stmt)
        return results[len(executed) - 1]

    db.execute = AsyncMock(side_effect=_execute)

    await calculate_daily_summary(db, now=now)

    compiled = str(
        executed[-1].compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    assert "2026-03-28 12:00:00" in compiled
