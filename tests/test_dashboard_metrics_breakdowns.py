"""tj-ierv.5: escalation categories and sales-stage distribution metrics."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.dashboard_metrics import (
    _int_mapping,
    calculate_dashboard_metrics,
    categorize_escalation_reason,
    categorize_escalation_reasons,
)


@pytest.mark.parametrize(
    ("reason", "category"),
    [
        (
            "Critical escalation: the customer explicitly requested a human response.",
            "human_request",
        ),
        (
            "Critical escalation: the customer accepted a prepared quotation and "
            "human order processing is required.",
            "quotation_bulk",
        ),
        (
            "Critical escalation: the customer reported an existing-order, payment, "
            "legal, or safety incident.",
            "urgent_complaint",
        ),
        (
            "B2B handoff: the customer asked for a wholesale or bulk project order "
            "(20+ units or bulk pricing).",
            "quotation_bulk",
        ),
        (
            "B2B handoff: the customer asked for furniture made to order (custom "
            "dimensions, materials or built-in power).",
            "custom_out_of_catalog",
        ),
        ("Customer asks about delivery to Abu Dhabi", "delivery_terms"),
        ("something else", "other"),
        (None, "other"),
    ],
)
def test_categorize_escalation_reason(reason: str | None, category: str) -> None:
    assert categorize_escalation_reason(reason) == category


def test_categorize_escalation_reasons_sums_counts() -> None:
    grouped = categorize_escalation_reasons(
        {
            "wholesale order of 40 chairs": 3,
            "customer wants a quotation": 2,
            "please call me": 1,
            "?": 4,
        }
    )
    assert grouped == {"quotation_bulk": 5, "human_request": 1, "other": 4}


def test_int_mapping_accepts_json_text_and_ignores_garbage() -> None:
    assert _int_mapping('{"greeting": 3, "quoting": 1}') == {
        "greeting": 3,
        "quoting": 1,
    }
    assert _int_mapping({"solution": 2.0, "bad": "x"}) == {"solution": 2}
    assert _int_mapping(None) == {}
    assert _int_mapping("not json") == {}
    assert _int_mapping(MagicMock()) == {}


@pytest.mark.asyncio
async def test_dashboard_metrics_exposes_new_breakdowns() -> None:
    mock_db = AsyncMock()

    conv_result = MagicMock()
    conv_result.one.return_value = MagicMock(
        total_conversations=4,
        unique_customers=3,
        target_count=3,
        escalation_count=2,
        noor_sales_count=1,
        post_esc_sales_count=0,
        avg_deal_value=None,
        sales_stage_distribution={"greeting": 2, "quoting": 2},
    )
    lang_result = MagicMock()
    lang_result.all.return_value = [("en", 4)]
    seg_result = MagicMock()
    seg_result.all.return_value = []
    esc_result = MagicMock()
    esc_result.all.return_value = [
        ("B2B handoff: wholesale or bulk project order", 1),
        ("Critical escalation: explicitly requested a human response.", 1),
    ]
    mgr_result = MagicMock()
    mgr_result.one.return_value = (None, None)
    mgr_conv_result = MagicMock()
    mgr_conv_result.one.return_value = (0, 0)
    lb_result = MagicMock()
    lb_result.all.return_value = []
    fb_result = MagicMock()
    fb_result.one.return_value = (0, None, None, 0, 0)
    recent_fb_result = MagicMock()
    recent_fb_result.all.return_value = []

    mock_db.execute.side_effect = [
        conv_result,
        lang_result,
        seg_result,
        esc_result,
        mgr_result,
        mgr_conv_result,
        lb_result,
        fb_result,
        recent_fb_result,
    ]
    mock_db.scalar.side_effect = [0, 0, 0.0, 0.0, 0.0, 0.0]

    metrics = await calculate_dashboard_metrics(mock_db, period="week")

    assert metrics.escalation_by_reason == {"quotation_bulk": 1, "human_request": 1}
    assert metrics.sales_stage_distribution == {"greeting": 2, "quoting": 2}
    conv_sql = str(mock_db.execute.call_args_list[0].args[0])
    assert "json_object_agg" in conv_sql
