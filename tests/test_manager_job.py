"""Tests for manager evaluation cron job (Component 7).

Verifies:
- Job finds unreviewed escalations and evaluates them
- Job skips when no pending escalations
- Job handles errors gracefully
- Worker has manager evaluation registered
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.schemas.common import EscalationStatus


@pytest.mark.asyncio
@patch("src.quality.manager_job.async_session_factory")
@patch("src.quality.manager_job.get_unreviewed_resolved_escalations")
async def test_job_skips_when_no_pending(
    mock_get_unreviewed: AsyncMock,
    mock_session_factory: AsyncMock,
) -> None:
    """Job returns early when no unreviewed escalations found."""
    from src.quality.manager_job import evaluate_escalated_conversations

    mock_db = AsyncMock()
    mock_session_factory.return_value.__aenter__.return_value = mock_db
    mock_get_unreviewed.return_value = []

    await evaluate_escalated_conversations({})

    mock_get_unreviewed.assert_awaited_once()


def test_worker_has_manager_evaluation_registered() -> None:
    """Worker should have evaluate_escalated_conversations in functions and cron."""
    from src.worker import WorkerSettings

    func_names = [getattr(f, "__name__", "") for f in WorkerSettings.functions]
    assert "evaluate_escalated_conversations" in func_names

    cron_func_names = [
        getattr(j.coroutine, "__name__", getattr(j.coroutine, "__qualname__", ""))
        for j in WorkerSettings.cron_jobs
    ]
    assert "evaluate_escalated_conversations" in cron_func_names


@pytest.mark.asyncio
@patch("src.quality.manager_job.async_session_factory")
@patch("src.quality.manager_job.save_manager_review", new_callable=AsyncMock)
@patch("src.quality.manager_job.evaluate_manager_conversation", new_callable=AsyncMock)
@patch("src.quality.manager_job.escalation_already_reviewed", new_callable=AsyncMock)
@patch(
    "src.quality.manager_job.get_unreviewed_resolved_escalations",
    new_callable=AsyncMock,
)
@patch("src.services.notifications.send_telegram_message", new_callable=AsyncMock)
async def test_job_skips_low_score_telegram_alert_for_other_inbound_phone(
    mock_send_telegram: AsyncMock,
    mock_get_unreviewed: AsyncMock,
    mock_already_reviewed: AsyncMock,
    mock_evaluate: AsyncMock,
    mock_save_review: AsyncMock,
    mock_session_factory: MagicMock,
) -> None:
    from src.quality.manager_job import evaluate_escalated_conversations

    esc_id = "esc-123"
    mock_get_unreviewed.return_value = [esc_id]
    mock_already_reviewed.return_value = False
    mock_evaluate.return_value = (
        SimpleNamespace(total_score=4.2, rating="poor", summary="Bad handoff"),
        SimpleNamespace(),
    )

    escalation = SimpleNamespace(
        id=esc_id,
        conversation_id="conv-123",
        assigned_to="Manager",
        status=EscalationStatus.RESOLVED.value,
        conversation=SimpleNamespace(
            metadata_={"inbound_channel_phone": "+971509999999"}
        ),
    )
    exec_result = MagicMock()
    exec_result.scalar_one.return_value = escalation

    first_db = AsyncMock()
    second_db = AsyncMock()
    second_db.execute = AsyncMock(return_value=exec_result)

    first_cm = AsyncMock()
    first_cm.__aenter__.return_value = first_db
    first_cm.__aexit__.return_value = False

    second_cm = AsyncMock()
    second_cm.__aenter__.return_value = second_db
    second_cm.__aexit__.return_value = False

    mock_session_factory.side_effect = [first_cm, second_cm]

    with patch(
        "src.services.inbound_channels.settings.telegram_allowed_inbound_phone",
        "+971551220665",
    ):
        await evaluate_escalated_conversations({})

    mock_save_review.assert_awaited_once()
    mock_send_telegram.assert_not_awaited()
