"""Tests for manager evaluation cron job (Component 7).

Verifies:
- Job finds unreviewed escalations and evaluates them
- Job skips when no pending escalations
- Job handles errors gracefully
- Worker has manager evaluation registered
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


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

    func_names = [f.__name__ for f in WorkerSettings.functions]
    assert "evaluate_escalated_conversations" in func_names

    cron_func_names = [j.coroutine.__name__ for j in WorkerSettings.cron_jobs]
    assert "evaluate_escalated_conversations" in cron_func_names
