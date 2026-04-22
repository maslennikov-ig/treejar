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


def test_manager_evaluator_prompt_requires_russian_human_readable_output() -> None:
    """Manager judge prompt must require Russian output for human-readable fields."""
    from src.quality.manager_evaluator import MANAGER_EVALUATION_PROMPT

    assert "русском" in MANAGER_EVALUATION_PROMPT.lower()
    assert "summary" in MANAGER_EVALUATION_PROMPT
    assert "comment" in MANAGER_EVALUATION_PROMPT.lower()


@pytest.mark.asyncio
async def test_evaluate_manager_conversation_passes_expected_llm_safety_kwargs() -> (
    None
):
    from src.core.config import settings
    from src.quality.manager_evaluator import evaluate_manager_conversation

    escalation_id = uuid.uuid4()
    conversation_id = uuid.uuid4()
    created_at = datetime(2026, 4, 21, 10, 0, 0, tzinfo=UTC)

    escalation = MagicMock()
    escalation.id = escalation_id
    escalation.conversation_id = conversation_id
    escalation.created_at = created_at
    escalation.reason = "Customer asked for a manager"
    escalation.notes = None
    escalation.assigned_to = "Annabelle"

    conversation = MagicMock()
    conversation.id = conversation_id
    conversation.zoho_deal_id = None
    conversation.deal_amount = None

    message = MagicMock()
    message.id = uuid.uuid4()
    message.role = "manager"
    message.content = "I can help with this quotation."
    message.created_at = datetime(2026, 4, 21, 10, 5, 0, tzinfo=UTC)

    esc_result = MagicMock()
    esc_result.scalar_one_or_none.return_value = escalation
    conv_result = MagicMock()
    conv_result.scalar_one_or_none.return_value = conversation
    msg_scalars = MagicMock()
    msg_scalars.all.return_value = [message]
    msg_result = MagicMock()
    msg_result.scalars.return_value = msg_scalars
    all_msg_scalars = MagicMock()
    all_msg_scalars.all.return_value = [message]
    all_msg_result = MagicMock()
    all_msg_result.scalars.return_value = all_msg_scalars

    db = AsyncMock()
    db.execute.side_effect = [esc_result, conv_result, msg_result, all_msg_result]
    db.scalar.side_effect = [None, 1]

    criteria = [
        ManagerCriterionScore(
            rule_number=i,
            rule_name=f"rule_{i}",
            score=1,
            comment="ok",
        )
        for i in range(1, 11)
    ]
    run_result = MagicMock()
    run_result.output = ManagerEvaluationResult(
        criteria=criteria,
        summary="Кратко: ok",
        total_score=10.0,
        rating="satisfactory",
    )

    from unittest.mock import patch

    with patch("src.quality.manager_evaluator.manager_judge_agent") as mock_agent:
        mock_agent.run = AsyncMock(return_value=run_result)
        await evaluate_manager_conversation(escalation_id, db)

    call_kwargs = mock_agent.run.call_args.kwargs
    assert call_kwargs["model"].model_name == settings.openrouter_model_fast
    assert call_kwargs["model_settings"]["max_tokens"] == 2000
    assert call_kwargs["usage_limits"].request_limit == 1
    assert call_kwargs["usage_limits"].output_tokens_limit == 2000
    assert call_kwargs["usage_limits"].total_tokens_limit == 8000


@pytest.mark.asyncio
async def test_manager_summary_mode_focuses_post_escalation_with_prior_context() -> (
    None
):
    from src.quality.manager_evaluator import evaluate_manager_conversation

    escalation_id = uuid.uuid4()
    conversation_id = uuid.uuid4()
    created_at = datetime(2026, 4, 21, 10, 0, 0, tzinfo=UTC)

    escalation = MagicMock()
    escalation.id = escalation_id
    escalation.conversation_id = conversation_id
    escalation.created_at = created_at
    escalation.reason = "Customer asked for manager"
    escalation.notes = "Need exact stock confirmation"
    escalation.assigned_to = "Annabelle"

    conversation = MagicMock()
    conversation.id = conversation_id
    conversation.zoho_deal_id = None
    conversation.deal_amount = None

    prior = MagicMock()
    prior.id = uuid.uuid4()
    prior.role = "user"
    prior.content = "PRIOR_MANAGER_CONTEXT_MARKER: customer needs 12 desks."
    prior.created_at = datetime(2026, 4, 21, 9, 45, 0, tzinfo=UTC)

    manager = MagicMock()
    manager.id = uuid.uuid4()
    manager.role = "manager"
    manager.content = "POST_ESCALATION_MANAGER_CONTEXT_MARKER: I confirm stock."
    manager.created_at = datetime(2026, 4, 21, 10, 5, 0, tzinfo=UTC)

    customer = MagicMock()
    customer.id = uuid.uuid4()
    customer.role = "user"
    customer.content = "POST_ESCALATION_USER_CONTEXT_MARKER: please send quotation."
    customer.created_at = datetime(2026, 4, 21, 10, 7, 0, tzinfo=UTC)

    esc_result = MagicMock()
    esc_result.scalar_one_or_none.return_value = escalation
    conv_result = MagicMock()
    conv_result.scalar_one_or_none.return_value = conversation
    post_scalars = MagicMock()
    post_scalars.all.return_value = [manager, customer]
    post_result = MagicMock()
    post_result.scalars.return_value = post_scalars
    all_scalars = MagicMock()
    all_scalars.all.return_value = [prior, manager, customer]
    all_result = MagicMock()
    all_result.scalars.return_value = all_scalars

    db = AsyncMock()
    db.execute.side_effect = [esc_result, conv_result, post_result, all_result]
    db.scalar.side_effect = [manager.created_at, 1]

    criteria = [
        ManagerCriterionScore(
            rule_number=i,
            rule_name=f"rule_{i}",
            score=1,
            comment="ok",
        )
        for i in range(1, 11)
    ]
    run_result = MagicMock()
    run_result.output = ManagerEvaluationResult(
        criteria=criteria,
        summary="Кратко: ok",
        total_score=10.0,
        rating="satisfactory",
    )

    from unittest.mock import patch

    with patch("src.quality.manager_evaluator.manager_judge_agent") as mock_agent:
        mock_agent.run = AsyncMock(return_value=run_result)
        await evaluate_manager_conversation(escalation_id, db)

    prompt = mock_agent.run.await_args.args[0]
    assert "<BOUNDED_REVIEW_CONTEXT" in prompt
    assert "PRIOR_MANAGER_CONTEXT_MARKER" in prompt
    assert "POST_ESCALATION_MANAGER_CONTEXT_MARKER" in prompt
    assert "POST_ESCALATION_USER_CONTEXT_MARKER" in prompt
    assert "Customer asked for manager" in prompt


@pytest.mark.asyncio
async def test_disabled_manager_transcript_mode_skips_provider_call() -> None:
    from src.quality.config import AIQualityTranscriptMode
    from src.quality.manager_evaluator import evaluate_manager_conversation

    escalation_id = uuid.uuid4()
    conversation_id = uuid.uuid4()
    created_at = datetime(2026, 4, 21, 10, 0, 0, tzinfo=UTC)

    escalation = MagicMock()
    escalation.id = escalation_id
    escalation.conversation_id = conversation_id
    escalation.created_at = created_at
    escalation.reason = "Customer asked for manager"
    escalation.notes = None
    escalation.assigned_to = "Annabelle"

    conversation = MagicMock()
    conversation.id = conversation_id
    conversation.zoho_deal_id = None
    conversation.deal_amount = None

    message = MagicMock()
    message.id = uuid.uuid4()
    message.role = "manager"
    message.content = "MANAGER_DISABLED_NO_LLM"
    message.created_at = datetime(2026, 4, 21, 10, 5, 0, tzinfo=UTC)

    esc_result = MagicMock()
    esc_result.scalar_one_or_none.return_value = escalation
    conv_result = MagicMock()
    conv_result.scalar_one_or_none.return_value = conversation
    msg_scalars = MagicMock()
    msg_scalars.all.return_value = [message]
    msg_result = MagicMock()
    msg_result.scalars.return_value = msg_scalars
    all_msg_scalars = MagicMock()
    all_msg_scalars.all.return_value = [message]
    all_msg_result = MagicMock()
    all_msg_result.scalars.return_value = all_msg_scalars

    db = AsyncMock()
    db.execute.side_effect = [esc_result, conv_result, msg_result, all_msg_result]
    db.scalar.side_effect = [message.created_at, 1]

    from unittest.mock import patch

    with patch("src.quality.manager_evaluator.manager_judge_agent") as mock_agent:
        mock_agent.run = AsyncMock(side_effect=AssertionError("unexpected LLM call"))
        evaluation, metrics = await evaluate_manager_conversation(
            escalation_id,
            db,
            transcript_mode=AIQualityTranscriptMode.DISABLED,
        )

    mock_agent.run.assert_not_awaited()
    assert evaluation.total_score == 0.0
    assert evaluation.rating == "poor"
    assert "Недостаточно данных" in evaluation.summary
    assert metrics.message_count == 1


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
