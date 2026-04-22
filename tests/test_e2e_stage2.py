"""E2E integration tests for Stage 2 modules.

Covers:
  - Quality evaluation flow (evaluate_conversation → save_review)
  - Telegram escalation notification delivery
  - Report generation and Telegram send
  - Referral code lifecycle (generate → apply → apply again → already_used)

All tests are unit-level (mock-based), following the pattern from test_e2e_tools.py.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

# =============================================================================
# 1. Quality evaluation flow E2E
# =============================================================================


@pytest.mark.asyncio
async def test_quality_evaluation_e2e_pipeline() -> None:
    """evaluate_conversation() → EvaluationResult with 15 criteria → save_review called."""
    from src.quality.evaluator import evaluate_conversation
    from src.quality.schemas import CriterionScore, EvaluationResult

    # All 15 criteria: score 2 each → total 30, rating "excellent"
    mock_criteria = [
        CriterionScore(rule_number=i, rule_name=f"Rule {i}", score=2, comment="ok")
        for i in range(1, 16)
    ]
    mock_evaluation = EvaluationResult(
        criteria=mock_criteria,
        summary="Excellent dialogue.",
        total_score=30.0,
        rating="excellent",
    )
    mock_run_result = MagicMock()
    mock_run_result.output = mock_evaluation

    # DB with 2 messages
    mock_msg_user = MagicMock()
    mock_msg_user.role = "user"
    mock_msg_user.content = "Hello, I need office chairs."
    mock_msg_assistant = MagicMock()
    mock_msg_assistant.role = "assistant"
    mock_msg_assistant.content = "Hi! I'm Siyyad from Treejar. How can I help?"

    mock_db = AsyncMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [mock_msg_user, mock_msg_assistant]
    mock_execute_result = MagicMock()
    mock_execute_result.scalars.return_value = mock_scalars
    mock_db.execute = AsyncMock(return_value=mock_execute_result)

    conv_id = uuid4()

    with patch("src.quality.evaluator.judge_agent") as mock_agent:
        mock_agent.run = AsyncMock(return_value=mock_run_result)
        result = await evaluate_conversation(conv_id, mock_db, sales_stage="feedback")

    # Verify scores are recomputed deterministically
    assert result.total_score == 30.0, f"Expected 30.0, got {result.total_score}"
    assert result.rating == "excellent", f"Expected 'excellent', got {result.rating}"
    assert len(result.criteria) == 15
    mock_agent.run.assert_called_once()

    # Verify prompt wraps content in the bounded untrusted-context wrapper
    prompt = mock_agent.run.call_args[0][0]
    assert "<BOUNDED_REVIEW_CONTEXT" in prompt
    assert "</BOUNDED_REVIEW_CONTEXT>" in prompt
    assert "Siyyad" in prompt


# =============================================================================
# 2. Telegram escalation notification E2E
# =============================================================================


@pytest.mark.asyncio
async def test_telegram_escalation_notification_delivered() -> None:
    """notify_escalation() → TelegramClient.send_message() called with masked phone."""
    from src.services.notifications import notify_escalation

    mock_client = MagicMock()
    mock_client.send_message = AsyncMock()

    conv_id = uuid4()
    phone = "+971501234567"

    with patch(
        "src.services.notifications._get_telegram_client", return_value=mock_client
    ):
        await notify_escalation(
            phone=phone, conversation_id=conv_id, reason="Customer requested human"
        )

    mock_client.send_message.assert_called_once()
    html_message: str = mock_client.send_message.call_args[0][0]

    # Message must contain alert header and full phone (managers need to call back)
    assert "Эскалация" in html_message, "Expected 'Эскалация' in message"
    assert "+971501234567" in html_message, (
        f"Phone should be shown in full for managers, got: {html_message}"
    )
    assert "запрошен менеджер" in html_message


# =============================================================================
# 3. Report generation and Telegram send E2E
# =============================================================================


@pytest.mark.asyncio
async def test_report_generation_and_send() -> None:
    """format_report_text() produces valid HTML; send_telegram_message sends it."""
    from src.services.notifications import send_telegram_message
    from src.services.reports import ReportData, format_report_text

    now = datetime.now(tz=UTC)
    report_data = ReportData(
        period_start=now - timedelta(days=7),
        period_end=now,
        total_conversations=50,
        conversations_per_day=7.1,
        unique_customers=42,
        total_deals=6,
        conversion_rate=12.0,
        avg_deal_value=8500.0,
        avg_quality_score=22.4,
        escalation_count=3,
        escalation_reasons={"Customer not convinced": 2, "Order > 10K AED": 1},
        top_products=[
            {"name": "Executive Chair", "sku": "CH-001", "mentions": 8},
        ],
    )

    # Step 1: format report text and check structure
    text = format_report_text(report_data)
    assert "Недельный отчёт" in text, "Report text must contain 'Недельный отчёт'"
    assert "50" in text, "Report text must contain total_conversations (50)"
    assert "Диалоги" in text
    assert "Executive Chair" in text

    # Step 2: send_telegram_message should call client.send_message
    mock_client = MagicMock()
    mock_client.send_message = AsyncMock()

    with patch(
        "src.services.notifications._get_telegram_client", return_value=mock_client
    ):
        await send_telegram_message(text)

    mock_client.send_message.assert_called_once_with(text)


# =============================================================================
# 4. Referral lifecycle E2E
# =============================================================================


@pytest.mark.asyncio
async def test_referral_lifecycle_generate_apply_idempotent() -> None:
    """Full lifecycle: generate code → apply → second apply → already_used."""
    from src.models.referral import Referral
    from src.services.referrals import apply_code, generate_code

    # --- Phase 1: Generate code ---
    mock_db_gen = AsyncMock()
    mock_db_gen.add = MagicMock()
    mock_db_gen.flush = AsyncMock()

    result_gen = await generate_code(mock_db_gen, "+971501234567")
    assert result_gen.success is True
    assert result_gen.code is not None
    assert result_gen.code.startswith("NOOR-")
    generated_code = result_gen.code

    # --- Phase 2: First application (valid) ---
    mock_referral = MagicMock(spec=Referral)
    mock_referral.code = generated_code
    mock_referral.referrer_phone = "+971501234567"
    mock_referral.referee_discount_percent = 10.0
    mock_referral.status = "active"
    mock_referral.expires_at = datetime.now(tz=UTC) + timedelta(days=30)

    mock_db_apply1 = AsyncMock()
    mock_execute_result1 = MagicMock()
    mock_execute_result1.scalar_one_or_none.return_value = mock_referral
    mock_db_apply1.execute = AsyncMock(return_value=mock_execute_result1)
    mock_db_apply1.flush = AsyncMock()

    result_apply1 = await apply_code(mock_db_apply1, generated_code, "+971509876543")
    assert result_apply1.success is True
    assert result_apply1.discount_percent == 10.0
    # Referral status must be set to "used" after first application
    assert mock_referral.status == "used"

    # --- Phase 3: Second application (already used) ---
    mock_referral_used = MagicMock(spec=Referral)
    mock_referral_used.code = generated_code
    mock_referral_used.referrer_phone = "+971501234567"
    mock_referral_used.status = "used"  # Already marked as used
    mock_referral_used.expires_at = datetime.now(tz=UTC) + timedelta(days=30)

    mock_db_apply2 = AsyncMock()
    mock_execute_result2 = MagicMock()
    mock_execute_result2.scalar_one_or_none.return_value = mock_referral_used
    mock_db_apply2.execute = AsyncMock(return_value=mock_execute_result2)

    result_apply2 = await apply_code(mock_db_apply2, generated_code, "+971500000001")
    assert result_apply2.success is False, (
        "Second application of a used code should fail"
    )
    assert result_apply2.message is not None and len(result_apply2.message) > 0
