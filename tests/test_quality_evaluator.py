"""Tests for quality evaluator module.

TDD: Tests written first, then implementation.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


# =============================================================================
# Task 1: Schema tests
# =============================================================================


def test_criterion_score_valid() -> None:
    from src.quality.schemas import CriterionScore

    cs = CriterionScore(rule_number=1, rule_name="Greeting", score=2, comment="Great")
    assert cs.score == 2
    assert cs.rule_number == 1
    assert cs.comment == "Great"


def test_criterion_score_invalid_score_too_high() -> None:
    from pydantic import ValidationError

    from src.quality.schemas import CriterionScore

    with pytest.raises(ValidationError):
        CriterionScore(rule_number=1, rule_name="x", score=3, comment="x")  # score > 2


def test_criterion_score_invalid_rule_number() -> None:
    from pydantic import ValidationError

    from src.quality.schemas import CriterionScore

    with pytest.raises(ValidationError):
        CriterionScore(rule_number=16, rule_name="x", score=1, comment="x")  # > 15


def test_evaluation_result_valid() -> None:
    from src.quality.schemas import CriterionScore, EvaluationResult

    criteria = [
        CriterionScore(rule_number=i, rule_name=f"Rule {i}", score=2, comment="ok")
        for i in range(1, 16)
    ]
    result = EvaluationResult(
        criteria=criteria,
        summary="Excellent dialogue",
        total_score=30.0,
        rating="excellent",
    )
    assert result.total_score == 30.0
    assert len(result.criteria) == 15
    assert result.rating == "excellent"


def test_compute_rating_excellent() -> None:
    from src.quality.schemas import compute_rating

    assert compute_rating(28) == "excellent"
    assert compute_rating(26) == "excellent"
    assert compute_rating(30) == "excellent"


def test_compute_rating_good() -> None:
    from src.quality.schemas import compute_rating

    assert compute_rating(25) == "good"
    assert compute_rating(20) == "good"


def test_compute_rating_satisfactory() -> None:
    from src.quality.schemas import compute_rating

    assert compute_rating(19) == "satisfactory"
    assert compute_rating(14) == "satisfactory"


def test_compute_rating_poor() -> None:
    from src.quality.schemas import compute_rating

    assert compute_rating(13) == "poor"
    assert compute_rating(0) == "poor"


# =============================================================================
# Task 2: Evaluator tests
# =============================================================================


def test_evaluator_prompt_contains_all_rules() -> None:
    """The EVALUATION_PROMPT must mention all 15 rule numbers."""
    from src.quality.evaluator import EVALUATION_PROMPT

    for i in range(1, 16):
        assert str(i) in EVALUATION_PROMPT, f"Rule {i} missing from evaluator prompt"


@pytest.mark.asyncio
async def test_evaluate_conversation_with_mock_agent() -> None:
    """evaluate_conversation should call judge_agent and return EvaluationResult."""
    from src.quality.evaluator import evaluate_conversation
    from src.quality.schemas import CriterionScore, EvaluationResult

    mock_criteria = [
        CriterionScore(rule_number=i, rule_name=f"Rule {i}", score=2, comment="ok")
        for i in range(1, 16)
    ]
    mock_evaluation = EvaluationResult(
        criteria=mock_criteria,
        summary="Great dialogue",
        total_score=30.0,
        rating="excellent",
    )

    mock_run_result = MagicMock()
    mock_run_result.output = mock_evaluation

    # Mock DB session
    mock_db = AsyncMock()
    mock_msg1 = MagicMock()
    mock_msg1.role = "user"
    mock_msg1.content = "Hello"
    mock_msg2 = MagicMock()
    mock_msg2.role = "assistant"
    mock_msg2.content = "Hi! I am Siyyad from Treejar."

    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [mock_msg1, mock_msg2]
    mock_execute_result = MagicMock()
    mock_execute_result.scalars.return_value = mock_scalars
    mock_db.execute = AsyncMock(return_value=mock_execute_result)

    conv_id = uuid4()

    with patch("src.quality.evaluator.judge_agent") as mock_agent:
        mock_agent.run = AsyncMock(return_value=mock_run_result)
        result = await evaluate_conversation(conv_id, mock_db)

    assert result.total_score == 30.0
    assert result.rating == "excellent"
    assert len(result.criteria) == 15
    mock_agent.run.assert_called_once()
    call_args = mock_agent.run.call_args
    # Verify the prompt contains the dialogue
    assert "Hello" in call_args[0][0]
    assert "Siyyad" in call_args[0][0]


@pytest.mark.asyncio
async def test_evaluate_conversation_raises_on_no_messages() -> None:
    """evaluate_conversation should raise ValueError if conversation has no messages."""
    from src.quality.evaluator import evaluate_conversation

    mock_db = AsyncMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []  # no messages
    mock_execute_result = MagicMock()
    mock_execute_result.scalars.return_value = mock_scalars
    mock_db.execute = AsyncMock(return_value=mock_execute_result)

    conv_id = uuid4()

    with pytest.raises(ValueError, match="No messages found"):
        await evaluate_conversation(conv_id, mock_db)
