"""DB integration tests for reports and recommendations.

CR-12: Tests that exercise the actual SQL query construction
with mocked AsyncSession.execute() responses.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

# =============================================================================
# Reports: generate_report() DB integration tests
# =============================================================================


@pytest.mark.asyncio
async def test_generate_report_returns_correct_structure() -> None:
    """generate_report should return ReportData with all expected fields."""
    from src.services.reports import generate_report

    mock_db = AsyncMock()

    # Simulate DB responses for each query in generate_report():
    # 1. conv_q: (total_conversations, unique_customers)
    mock_conv_result = MagicMock()
    mock_conv_result.one.return_value = (42, 30)

    # 2. deals_q: (total_deals, avg_deal_value)
    mock_deals_result = MagicMock()
    mock_deals_result.one.return_value = (5, 1500.0)

    # 3. qr_q: avg_quality_score (scalar)
    # 4. esc_count_q: escalation_count (scalar)
    # 5. esc_reasons_q: escalation reasons grouped
    mock_esc_reasons_result = MagicMock()
    mock_esc_reasons_result.all.return_value = [
        ("Price too high", 3),
        ("Competitor preferred", 2),
    ]

    # 6. top_prod_sql: top products
    mock_top_prod_result = MagicMock()
    mock_top_prod_result.all.return_value = [
        ("Executive Desk", "TJ-DESK-001", 10),
        ("Ergonomic Chair", "TJ-CHAIR-001", 7),
    ]

    mock_db.execute.side_effect = [
        mock_conv_result,  # conv_q
        mock_deals_result,  # deals_q
        mock_esc_reasons_result,  # esc_reasons_q
        mock_top_prod_result,  # top_prod_sql
    ]

    # scalar() calls are separate
    mock_db.scalar.side_effect = [
        22.5,  # avg_quality_score
        8,  # escalation_count
    ]

    start = datetime.now(tz=UTC) - timedelta(days=7)
    end = datetime.now(tz=UTC)
    report = await generate_report(mock_db, start_date=start, end_date=end)

    assert report.total_conversations == 42
    assert report.unique_customers == 30
    assert report.total_deals == 5
    assert report.avg_deal_value == 1500.0
    assert report.conversion_rate > 0
    assert report.avg_quality_score == 22.5
    assert report.escalation_count == 8
    assert "Price too high" in report.escalation_reasons
    assert len(report.top_products) == 2


@pytest.mark.asyncio
async def test_generate_report_handles_empty_data() -> None:
    """generate_report should handle zero conversations gracefully."""
    from src.services.reports import generate_report

    mock_db = AsyncMock()

    mock_conv_result = MagicMock()
    mock_conv_result.one.return_value = (0, 0)

    mock_deals_result = MagicMock()
    mock_deals_result.one.return_value = (0, None)

    mock_esc_reasons_result = MagicMock()
    mock_esc_reasons_result.all.return_value = []

    mock_top_prod_result = MagicMock()
    mock_top_prod_result.all.return_value = []

    mock_mgr_result = MagicMock()
    mock_mgr_result.one.return_value = (None, None, 0, 0)

    mock_mgr_conv_result = MagicMock()
    mock_mgr_conv_result.one.return_value = (0, 0)

    mock_top_mgr_result = MagicMock()
    mock_top_mgr_result.all.return_value = []

    mock_db.execute.side_effect = [
        mock_conv_result,
        mock_deals_result,
        mock_esc_reasons_result,
        mock_top_prod_result,
        mock_mgr_result,
        mock_mgr_conv_result,
        mock_top_mgr_result,
    ]
    mock_db.scalar.side_effect = [None, 0]

    report = await generate_report(mock_db)

    assert report.total_conversations == 0
    assert report.conversion_rate == 0.0
    assert report.avg_deal_value == 0.0
    assert report.top_products == []


@pytest.mark.asyncio
async def test_generate_report_quality_uses_active_conversation_window() -> None:
    """Weekly report quality should be tied to assistant activity, not review created_at."""
    from src.services.reports import generate_report

    mock_db = AsyncMock()

    mock_conv_result = MagicMock()
    mock_conv_result.one.return_value = (1, 1)

    mock_deals_result = MagicMock()
    mock_deals_result.one.return_value = (0, None)

    mock_esc_reasons_result = MagicMock()
    mock_esc_reasons_result.all.return_value = []

    mock_top_prod_result = MagicMock()
    mock_top_prod_result.all.return_value = []

    mock_db.execute.side_effect = [
        mock_conv_result,
        mock_deals_result,
        mock_esc_reasons_result,
        mock_top_prod_result,
    ]
    mock_db.scalar.side_effect = [22.5, 0]

    start = datetime.now(tz=UTC) - timedelta(days=7)
    end = datetime.now(tz=UTC)
    await generate_report(mock_db, start_date=start, end_date=end)

    quality_stmt = mock_db.scalar.call_args_list[0].args[0]
    compiled = str(
        quality_stmt.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    ).lower()

    assert "messages" in compiled
    assert "quality_reviews.created_at" not in compiled


@pytest.mark.asyncio
async def test_dashboard_metrics_quality_uses_active_conversation_window() -> None:
    """Dashboard quality should follow assistant activity, not review created_at."""
    from src.services.dashboard_metrics import calculate_dashboard_metrics

    mock_db = AsyncMock()

    conv_result = MagicMock()
    conv_result.one.return_value = MagicMock(
        total_conversations=1,
        unique_customers=1,
        target_count=1,
        escalation_count=0,
        noor_sales_count=0,
        post_esc_sales_count=0,
        avg_deal_value=None,
    )

    lang_result = MagicMock()
    lang_result.all.return_value = []

    seg_result = MagicMock()
    seg_result.all.return_value = []

    esc_result = MagicMock()
    esc_result.all.return_value = []

    mgr_result = MagicMock()
    mgr_result.one.return_value = (None, None)

    mgr_conv_result = MagicMock()
    mgr_conv_result.one.return_value = (0, 0)

    lb_result = MagicMock()
    lb_result.all.return_value = []

    fb_result = MagicMock()
    fb_result.one.return_value = (0, None, None, 0, 0)

    mock_db.execute.side_effect = [
        conv_result,
        lang_result,
        seg_result,
        esc_result,
        mgr_result,
        mgr_conv_result,
        lb_result,
        fb_result,
    ]
    mock_db.scalar.side_effect = [0, 0, 0.0, 0.0, 22.5, 0.0]

    await calculate_dashboard_metrics(mock_db, period="week")

    quality_stmt = mock_db.scalar.call_args_list[4].args[0]
    compiled = str(
        quality_stmt.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    ).lower()

    assert "messages" in compiled
    assert "quality_reviews.created_at" not in compiled


# =============================================================================
# Recommendations: get_similar_products() DB integration tests
# =============================================================================


@pytest.mark.asyncio
async def test_get_similar_products_no_source() -> None:
    """get_similar_products should return [] if source product not found."""
    from src.services.recommendations import get_similar_products

    mock_db = AsyncMock()
    mock_db.get.return_value = None  # product not found

    result = await get_similar_products(mock_db, uuid4())
    assert result == []


@pytest.mark.asyncio
async def test_get_similar_products_no_embedding() -> None:
    """get_similar_products should return [] if source has no embedding."""
    from src.services.recommendations import get_similar_products

    mock_product = MagicMock()
    mock_product.embedding = None

    mock_db = AsyncMock()
    mock_db.get.return_value = mock_product

    result = await get_similar_products(mock_db, uuid4())
    assert result == []


@pytest.mark.asyncio
async def test_get_cross_sell_no_rules() -> None:
    """get_cross_sell should return [] if no cross_sell_rules config exists."""
    from src.services.recommendations import get_cross_sell

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    result = await get_cross_sell(mock_db, "desk")
    assert result == []


@pytest.mark.asyncio
async def test_get_cross_sell_with_rules() -> None:
    """get_cross_sell should find products in target categories."""
    from src.services.recommendations import get_cross_sell

    # Mock SystemConfig with rules
    mock_config = MagicMock()
    mock_config.value = {"desk": ["chair", "monitor_arm"], "chair": ["cushion"]}

    mock_config_result = MagicMock()
    mock_config_result.scalar_one_or_none.return_value = mock_config

    # Mock products found
    mock_product = MagicMock()
    mock_product.id = uuid4()
    mock_product.name_en = "Office Chair"
    mock_product.price = 299.0
    mock_product.stock = 15
    mock_product.category = "chair"

    mock_products_result = MagicMock()
    mock_products_result.scalars.return_value.all.return_value = [mock_product]

    mock_db = AsyncMock()
    mock_db.execute.side_effect = [
        mock_config_result,  # SystemConfig query
        mock_products_result,  # Products query
    ]

    result = await get_cross_sell(mock_db, "desk")
    assert len(result) == 1
    assert result[0].name == "Office Chair"
    assert result[0].recommendation_type == "cross_sell"
