"""Tests for rolling quality job behavior."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


def _make_evaluation_result(score: float = 30.0):
    from src.quality.schemas import CriterionScore, EvaluationResult

    criteria = [
        CriterionScore(rule_number=i, rule_name=f"Rule {i}", score=2, comment="ok")
        for i in range(1, 16)
    ]
    return EvaluationResult(
        criteria=criteria,
        summary="Updated review",
        total_score=score,
        rating="excellent",
    )


@pytest.mark.asyncio
async def test_evaluate_recent_conversations_quality_creates_review_for_recent_candidates() -> (
    None
):
    """Rolling job should evaluate recent assistant conversations and store reviews."""
    from src.quality.job import evaluate_recent_conversations_quality

    conv_id = uuid4()
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.rollback = AsyncMock()

    mock_session_ctx = AsyncMock()
    mock_session_ctx.__aenter__.return_value = mock_db
    mock_session_ctx.__aexit__.return_value = False

    mock_result = _make_evaluation_result()
    mock_evaluate = AsyncMock(return_value=mock_result)

    with (
        patch("src.quality.job.async_session_factory", return_value=mock_session_ctx),
        patch(
            "src.quality.job.get_recent_conversation_ids_with_assistant_activity",
            new=AsyncMock(return_value=[conv_id]),
        ),
        patch("src.quality.job.evaluate_conversation", new=mock_evaluate),
        patch("src.quality.job.save_review", new=AsyncMock()),
    ):
        await evaluate_recent_conversations_quality({})

    mock_evaluate.assert_awaited_once_with(conv_id, mock_db)
    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_evaluate_recent_conversations_quality_skips_when_no_recent_candidates() -> (
    None
):
    """Rolling job should exit cleanly when no assistant activity exists."""
    from src.quality.job import evaluate_recent_conversations_quality

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.rollback = AsyncMock()

    mock_session_ctx = AsyncMock()
    mock_session_ctx.__aenter__.return_value = mock_db
    mock_session_ctx.__aexit__.return_value = False

    mock_evaluate = AsyncMock()

    with (
        patch("src.quality.job.async_session_factory", return_value=mock_session_ctx),
        patch(
            "src.quality.job.get_recent_conversation_ids_with_assistant_activity",
            new=AsyncMock(return_value=[]),
        ),
        patch("src.quality.job.evaluate_conversation", new=mock_evaluate),
    ):
        await evaluate_recent_conversations_quality({})

    mock_evaluate.assert_not_awaited()
    mock_db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_save_review_updates_existing_review_when_present() -> None:
    """save_review should update an existing quality review instead of inserting."""
    from src.quality.service import save_review

    conv_id = uuid4()
    existing_review = MagicMock()
    existing_review.conversation_id = conv_id
    existing_review.total_score = 12.0
    existing_review.max_score = 30
    existing_review.criteria = []
    existing_review.rating = "poor"
    existing_review.summary = "Old summary"
    existing_review.reviewer = "ai"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_review

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()

    result = await save_review(mock_db, conv_id, _make_evaluation_result())

    assert result is existing_review
    assert existing_review.total_score == 30.0
    assert existing_review.rating == "excellent"
    assert existing_review.summary == "Updated review"
    mock_db.add.assert_not_called()
    mock_db.flush.assert_awaited_once()
