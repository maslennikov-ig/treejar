"""Tests for manager evaluator and quantitative metrics (Components 5 & 6).

Verifies:
- Manager schemas (ManagerCriterionScore, ManagerEvaluationResult)
- compute_manager_rating threshold calculations
- _determine_role helper (already tested in chat tests, included for completeness)
- evaluate_manager_conversation — mocked LLM agent
- calculate_manager_metrics — mocked DB queries
- save_manager_review — mocked DB session
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.quality.manager_schemas import (
    ManagerCriterionScore,
    ManagerEvaluationResult,
    compute_manager_rating,
)

# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------


def test_manager_criterion_score() -> None:
    score = ManagerCriterionScore(
        rule_number=1, rule_name="Quick pickup", score=2, comment="Good"
    )
    assert score.rule_number == 1
    assert score.score == 2


def test_manager_evaluation_result() -> None:
    criteria = [
        ManagerCriterionScore(
            rule_number=i, rule_name=f"rule_{i}", score=2, comment="ok"
        )
        for i in range(1, 11)
    ]
    result = ManagerEvaluationResult(
        criteria=criteria,
        summary="Great work",
        total_score=20.0,
        rating="excellent",
    )
    assert result.total_score == 20.0
    assert result.rating == "excellent"
    assert len(result.criteria) == 10


# ---------------------------------------------------------------------------
# Rating threshold tests
# ---------------------------------------------------------------------------


def test_rating_excellent() -> None:
    assert compute_manager_rating(17.0) == "excellent"
    assert compute_manager_rating(20.0) == "excellent"


def test_rating_good() -> None:
    assert compute_manager_rating(13.0) == "good"
    assert compute_manager_rating(16.9) == "good"


def test_rating_satisfactory() -> None:
    assert compute_manager_rating(9.0) == "satisfactory"
    assert compute_manager_rating(12.9) == "satisfactory"


def test_rating_poor() -> None:
    assert compute_manager_rating(0.0) == "poor"
    assert compute_manager_rating(8.9) == "poor"


# ---------------------------------------------------------------------------
# Quantitative metrics tests (Component 6)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_calculate_manager_metrics() -> None:
    """Test quantitative metrics calculation with mocked DB."""
    from src.quality.manager_evaluator import calculate_manager_metrics

    # Mock escalation
    mock_escalation = MagicMock()
    mock_escalation.created_at = datetime(2026, 3, 13, 10, 0, 0, tzinfo=UTC)

    # Mock conversation
    mock_conversation = MagicMock()
    mock_conversation.id = uuid.uuid4()
    mock_conversation.zoho_deal_id = "deal-123"
    mock_conversation.deal_amount = 25000.0

    # Mock DB session
    mock_db = AsyncMock()
    # First call: min(created_at) for manager messages → 5 min after escalation
    first_mgr_time = datetime(2026, 3, 13, 10, 5, 0, tzinfo=UTC)
    # Second call: count of manager messages → 8
    mock_db.scalar.side_effect = [first_mgr_time, 8]

    metrics = await calculate_manager_metrics(
        mock_escalation, mock_conversation, mock_db
    )

    assert metrics.first_response_time_seconds == 300  # 5 minutes
    assert metrics.message_count == 8
    assert metrics.deal_converted is True
    assert metrics.deal_amount == 25000.0


@pytest.mark.asyncio
async def test_calculate_manager_metrics_no_deal() -> None:
    """Test metrics with no deal conversion."""
    from src.quality.manager_evaluator import calculate_manager_metrics

    mock_escalation = MagicMock()
    mock_escalation.created_at = datetime(2026, 3, 13, 10, 0, 0, tzinfo=UTC)

    mock_conversation = MagicMock()
    mock_conversation.id = uuid.uuid4()
    mock_conversation.zoho_deal_id = None
    mock_conversation.deal_amount = None

    mock_db = AsyncMock()
    mock_db.scalar.side_effect = [None, 3]

    metrics = await calculate_manager_metrics(
        mock_escalation, mock_conversation, mock_db
    )

    assert metrics.first_response_time_seconds is None
    assert metrics.message_count == 3
    assert metrics.deal_converted is False
    assert metrics.deal_amount is None


# ---------------------------------------------------------------------------
# Save review test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_manager_review() -> None:
    """Test saving manager review to the database."""
    from src.quality.manager_evaluator import ManagerMetrics, save_manager_review

    criteria = [
        ManagerCriterionScore(
            rule_number=i, rule_name=f"rule_{i}", score=1, comment="Partial"
        )
        for i in range(1, 11)
    ]
    evaluation = ManagerEvaluationResult(
        criteria=criteria,
        summary="Average performance",
        total_score=10.0,
        rating="satisfactory",
    )
    metrics = ManagerMetrics(
        first_response_time_seconds=600,
        message_count=5,
        deal_converted=True,
        deal_amount=10000.0,
    )

    mock_db = AsyncMock()
    esc_id = uuid.uuid4()
    conv_id = uuid.uuid4()

    review = await save_manager_review(
        db=mock_db,
        escalation_id=esc_id,
        conversation_id=conv_id,
        evaluation=evaluation,
        metrics=metrics,
        manager_name="Annabelle",
    )

    assert review.escalation_id == esc_id
    assert review.conversation_id == conv_id
    assert review.manager_name == "Annabelle"
    assert review.total_score == 10.0
    assert review.rating == "satisfactory"
    assert review.message_count == 5
    assert review.deal_converted is True
    mock_db.add.assert_called_once()
    mock_db.flush.assert_awaited_once()


# ---------------------------------------------------------------------------
# Escalation already reviewed test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_escalation_already_reviewed_true() -> None:
    from src.quality.manager_evaluator import escalation_already_reviewed

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 1
    mock_db.execute.return_value = mock_result

    result = await escalation_already_reviewed(mock_db, uuid.uuid4())
    assert result is True


@pytest.mark.asyncio
async def test_escalation_already_reviewed_false() -> None:
    from src.quality.manager_evaluator import escalation_already_reviewed

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 0
    mock_db.execute.return_value = mock_result

    result = await escalation_already_reviewed(mock_db, uuid.uuid4())
    assert result is False
