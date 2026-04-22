"""Tests for manager evaluation cron job (Component 7).

Verifies:
- Job finds unreviewed escalations and evaluates them
- Job skips when no pending escalations
- Job handles errors gracefully
- Worker has manager evaluation registered
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.schemas.common import EscalationStatus


def _manager_quality_ctx(
    redis: AsyncMock | None = None,
    *,
    mode: str = "scheduled",
    transcript_mode: str = "summary",
    max_calls_per_run: int = 10,
    max_calls_per_day: int = 20,
) -> dict[str, object]:
    redis = redis or AsyncMock()
    redis.incr = AsyncMock(return_value=1)
    redis.expire = AsyncMock()
    redis.decr = AsyncMock()
    ctx: dict[str, object] = {
        "redis": redis,
        "ai_quality_controls": {
            "bot_qa": {"mode": "disabled"},
            "manager_qa": {
                "mode": mode,
                "transcript_mode": transcript_mode,
                "daily_budget_cents": 100,
                "max_calls_per_run": max_calls_per_run,
                "max_calls_per_day": max_calls_per_day,
                **(
                    {"full_transcript_warning_override": True}
                    if transcript_mode == "full"
                    else {}
                ),
            },
            "red_flags": {"mode": "disabled"},
        },
    }
    return ctx


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

    await evaluate_escalated_conversations(_manager_quality_ctx())

    mock_get_unreviewed.assert_awaited_once()


@pytest.mark.asyncio
async def test_job_disabled_mode_returns_before_pending_query() -> None:
    """Disabled manager-QA scope must perform no pending query or LLM work."""
    from src.quality.manager_job import evaluate_escalated_conversations

    get_unreviewed = AsyncMock(side_effect=AssertionError("unexpected pending query"))
    evaluate_mock = AsyncMock(side_effect=AssertionError("unexpected LLM call"))

    with (
        patch(
            "src.quality.manager_job.get_unreviewed_resolved_escalations",
            new=get_unreviewed,
        ),
        patch(
            "src.quality.manager_job.evaluate_manager_conversation", new=evaluate_mock
        ),
    ):
        await evaluate_escalated_conversations(_manager_quality_ctx(mode="disabled"))

    get_unreviewed.assert_not_awaited()
    evaluate_mock.assert_not_awaited()


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
    mock_redis = AsyncMock()
    mock_redis.set = AsyncMock(return_value=True)
    mock_redis.delete = AsyncMock()

    with patch(
        "src.services.inbound_channels.settings.telegram_allowed_inbound_phone",
        "+971551220665",
    ):
        await evaluate_escalated_conversations(_manager_quality_ctx(mock_redis))

    mock_save_review.assert_awaited_once()
    mock_send_telegram.assert_not_awaited()


@pytest.mark.asyncio
@patch("src.quality.manager_job.async_session_factory")
@patch("src.quality.manager_job.save_manager_review", new_callable=AsyncMock)
@patch("src.quality.manager_job.evaluate_manager_conversation", new_callable=AsyncMock)
@patch("src.quality.manager_job.escalation_already_reviewed", new_callable=AsyncMock)
@patch(
    "src.quality.manager_job.get_unreviewed_resolved_escalations",
    new_callable=AsyncMock,
)
@patch(
    "src.services.inbound_channels.should_send_telegram_alert_for_conversation_with_db",
    new_callable=AsyncMock,
)
@patch("src.services.notifications.send_telegram_message", new_callable=AsyncMock)
async def test_job_formats_low_score_telegram_alert_in_russian(
    mock_send_telegram: AsyncMock,
    mock_should_send: AsyncMock,
    mock_get_unreviewed: AsyncMock,
    mock_already_reviewed: AsyncMock,
    mock_evaluate: AsyncMock,
    mock_save_review: AsyncMock,
    mock_session_factory: MagicMock,
) -> None:
    from src.quality.manager_job import evaluate_escalated_conversations

    esc_id = "esc-456"
    mock_get_unreviewed.return_value = [esc_id]
    mock_already_reviewed.return_value = False
    mock_should_send.return_value = True
    mock_evaluate.return_value = (
        SimpleNamespace(total_score=4.2, rating="poor", summary="Слабая передача"),
        SimpleNamespace(),
    )

    escalation = SimpleNamespace(
        id=esc_id,
        conversation_id="conv-456",
        assigned_to=None,
        status=EscalationStatus.RESOLVED.value,
        conversation=SimpleNamespace(
            metadata_={"inbound_channel_phone": "+971551220665"}
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
    mock_redis = AsyncMock()
    mock_redis.set = AsyncMock(return_value=True)
    mock_redis.delete = AsyncMock()

    await evaluate_escalated_conversations(_manager_quality_ctx(mock_redis))

    mock_save_review.assert_awaited_once()
    mock_send_telegram.assert_awaited_once()
    message = mock_send_telegram.await_args.args[0]
    assert "Низкая оценка менеджера" in message
    assert "Менеджер" in message
    assert "не указан" in message
    assert "плохо" in message
    assert "Кратко" in message


@pytest.mark.asyncio
@patch("src.quality.manager_job.async_session_factory")
@patch(
    "src.quality.manager_job.record_llm_attempt_error",
    new_callable=AsyncMock,
)
@patch(
    "src.quality.manager_job.record_llm_attempt_success",
    new_callable=AsyncMock,
)
@patch("src.quality.manager_job.save_manager_review", new_callable=AsyncMock)
@patch("src.quality.manager_job.evaluate_manager_conversation", new_callable=AsyncMock)
@patch("src.quality.manager_job.escalation_already_reviewed", new_callable=AsyncMock)
@patch(
    "src.quality.manager_job.get_unreviewed_resolved_escalations",
    new_callable=AsyncMock,
)
@patch("src.quality.manager_job.release_llm_attempt_lock", new_callable=AsyncMock)
async def test_job_rolls_back_on_commit_failure_without_recording_attempt_error(
    mock_release_lock: AsyncMock,
    mock_get_unreviewed: AsyncMock,
    mock_already_reviewed: AsyncMock,
    mock_evaluate: AsyncMock,
    mock_save_review: AsyncMock,
    mock_record_success: AsyncMock,
    mock_record_error: AsyncMock,
    mock_session_factory: MagicMock,
) -> None:
    from src.quality.manager_job import evaluate_escalated_conversations

    esc_id = "esc-789"
    mock_get_unreviewed.return_value = [esc_id]
    mock_already_reviewed.return_value = False
    mock_evaluate.return_value = (
        SimpleNamespace(total_score=9.5, rating="good", summary="Solid handoff"),
        SimpleNamespace(),
    )

    escalation = SimpleNamespace(
        id=esc_id,
        conversation_id="conv-789",
        assigned_to="Manager",
        status=EscalationStatus.RESOLVED.value,
        created_at=datetime(2026, 4, 21, 9, 0, tzinfo=UTC),
        conversation=SimpleNamespace(metadata_={}),
    )
    exec_result = MagicMock()
    exec_result.scalar_one.return_value = escalation

    first_db = AsyncMock()
    second_db = AsyncMock()
    second_db.execute = AsyncMock(return_value=exec_result)

    commit_calls = 0

    async def commit_side_effect() -> None:
        nonlocal commit_calls
        commit_calls += 1
        if commit_calls == 3:
            raise RuntimeError("commit failed")

    second_db.commit.side_effect = commit_side_effect

    first_cm = AsyncMock()
    first_cm.__aenter__.return_value = first_db
    first_cm.__aexit__.return_value = False

    second_cm = AsyncMock()
    second_cm.__aenter__.return_value = second_db
    second_cm.__aexit__.return_value = False

    mock_session_factory.side_effect = [first_cm, second_cm]
    mock_redis = AsyncMock()
    mock_redis.set = AsyncMock(return_value=True)
    mock_redis.delete = AsyncMock()

    await evaluate_escalated_conversations(_manager_quality_ctx(mock_redis))

    mock_save_review.assert_awaited_once()
    mock_record_success.assert_awaited_once()
    mock_record_error.assert_not_awaited()
    second_db.rollback.assert_awaited_once()
    assert second_db.commit.await_count == 3


@pytest.mark.asyncio
@patch("src.quality.manager_job.async_session_factory")
@patch(
    "src.quality.manager_job.record_llm_attempt_error",
    new_callable=AsyncMock,
)
@patch(
    "src.quality.manager_job.record_llm_attempt_success",
    new_callable=AsyncMock,
)
@patch("src.quality.manager_job.save_manager_review", new_callable=AsyncMock)
@patch("src.quality.manager_job.evaluate_manager_conversation", new_callable=AsyncMock)
@patch("src.quality.manager_job.escalation_already_reviewed", new_callable=AsyncMock)
@patch(
    "src.quality.manager_job.get_unreviewed_resolved_escalations",
    new_callable=AsyncMock,
)
@patch("src.quality.manager_job.release_llm_attempt_lock", new_callable=AsyncMock)
async def test_job_save_manager_review_failure_does_not_record_attempt_error(
    mock_release_lock: AsyncMock,
    mock_get_unreviewed: AsyncMock,
    mock_already_reviewed: AsyncMock,
    mock_evaluate: AsyncMock,
    mock_save_review: AsyncMock,
    mock_record_success: AsyncMock,
    mock_record_error: AsyncMock,
    mock_session_factory: MagicMock,
) -> None:
    from src.quality.manager_job import evaluate_escalated_conversations

    esc_id = "esc-791"
    mock_get_unreviewed.return_value = [esc_id]
    mock_already_reviewed.return_value = False
    mock_evaluate.return_value = (
        SimpleNamespace(total_score=9.5, rating="good", summary="Solid handoff"),
        SimpleNamespace(),
    )
    mock_save_review.side_effect = RuntimeError("save failed")

    escalation = SimpleNamespace(
        id=esc_id,
        conversation_id="conv-791",
        assigned_to="Manager",
        status=EscalationStatus.RESOLVED.value,
        created_at=datetime(2026, 4, 21, 9, 0, tzinfo=UTC),
        conversation=SimpleNamespace(metadata_={}),
    )
    exec_result = MagicMock()
    exec_result.scalar_one.return_value = escalation

    first_db = AsyncMock()
    second_db = AsyncMock()
    second_db.execute = AsyncMock(return_value=exec_result)
    second_db.scalar = AsyncMock(return_value=None)
    second_db.commit = AsyncMock()
    second_db.rollback = AsyncMock()

    first_cm = AsyncMock()
    first_cm.__aenter__.return_value = first_db
    first_cm.__aexit__.return_value = False

    second_cm = AsyncMock()
    second_cm.__aenter__.return_value = second_db
    second_cm.__aexit__.return_value = False

    mock_session_factory.side_effect = [first_cm, second_cm]
    mock_redis = AsyncMock()
    mock_redis.set = AsyncMock(return_value=True)
    mock_redis.delete = AsyncMock()

    await evaluate_escalated_conversations(_manager_quality_ctx(mock_redis))

    mock_save_review.assert_awaited_once()
    mock_record_success.assert_awaited_once()
    mock_record_error.assert_not_awaited()
    second_db.rollback.assert_awaited_once()
    assert second_db.commit.await_count == 2


@pytest.mark.asyncio
@patch("src.quality.manager_job.async_session_factory")
@patch("src.quality.manager_job.save_manager_review", new_callable=AsyncMock)
@patch("src.quality.manager_job.record_llm_attempt_success", new_callable=AsyncMock)
@patch("src.quality.manager_job.evaluate_manager_conversation", new_callable=AsyncMock)
@patch("src.quality.manager_job.escalation_already_reviewed", new_callable=AsyncMock)
@patch(
    "src.quality.manager_job.get_unreviewed_resolved_escalations",
    new_callable=AsyncMock,
)
@patch("src.quality.manager_job.release_llm_attempt_lock", new_callable=AsyncMock)
async def test_job_attempt_key_uses_latest_manager_activity(
    mock_release_lock: AsyncMock,
    mock_get_unreviewed: AsyncMock,
    mock_already_reviewed: AsyncMock,
    mock_evaluate: AsyncMock,
    mock_save_review: AsyncMock,
    mock_record_success: AsyncMock,
    mock_session_factory: MagicMock,
) -> None:
    from src.quality.manager_job import (
        _attempt_input_hash,
        evaluate_escalated_conversations,
    )

    esc_id = "esc-792"
    mock_get_unreviewed.return_value = [esc_id]
    mock_already_reviewed.return_value = False
    mock_evaluate.return_value = (
        SimpleNamespace(total_score=9.5, rating="good", summary="Solid handoff"),
        SimpleNamespace(),
    )

    activity_at = datetime(2026, 4, 21, 11, 15, tzinfo=UTC)
    escalation = SimpleNamespace(
        id=esc_id,
        conversation_id="conv-792",
        assigned_to="Manager",
        status=EscalationStatus.RESOLVED.value,
        created_at=datetime(2026, 4, 21, 9, 0, tzinfo=UTC),
        updated_at=datetime(2026, 4, 21, 9, 30, tzinfo=UTC),
        conversation=SimpleNamespace(metadata_={}),
    )
    exec_result = MagicMock()
    exec_result.scalar_one.return_value = escalation

    first_db = AsyncMock()
    second_db = AsyncMock()
    second_db.execute = AsyncMock(return_value=exec_result)
    second_db.scalar = AsyncMock(return_value=activity_at)

    lease = SimpleNamespace(
        attempt=SimpleNamespace(status="pending", attempt_count=1),
        lock_key="llm_attempt:lock:test",
        lock_token="token",
        backoff_key="llm_attempt:backoff:test",
    )
    begin_attempt = AsyncMock(return_value=lease)

    first_cm = AsyncMock()
    first_cm.__aenter__.return_value = first_db
    first_cm.__aexit__.return_value = False

    second_cm = AsyncMock()
    second_cm.__aenter__.return_value = second_db
    second_cm.__aexit__.return_value = False

    mock_session_factory.side_effect = [first_cm, second_cm]
    mock_redis = AsyncMock()
    mock_redis.set = AsyncMock(return_value=True)
    mock_redis.delete = AsyncMock()

    with patch("src.quality.manager_job.begin_llm_attempt", new=begin_attempt):
        await evaluate_escalated_conversations(_manager_quality_ctx(mock_redis))

    assert begin_attempt.await_args.kwargs["entity_updated_at"] == activity_at
    from src.quality.config import AIQualityTranscriptMode

    assert begin_attempt.await_args.kwargs["input_hash"] == _attempt_input_hash(
        escalation,
        activity_at,
        transcript_mode=AIQualityTranscriptMode.SUMMARY,
    )


@pytest.mark.asyncio
@patch("src.quality.manager_job.async_session_factory")
@patch("src.quality.manager_job.save_manager_review", new_callable=AsyncMock)
@patch("src.quality.manager_job.record_llm_attempt_success", new_callable=AsyncMock)
@patch("src.quality.manager_job.evaluate_manager_conversation", new_callable=AsyncMock)
@patch("src.quality.manager_job.escalation_already_reviewed", new_callable=AsyncMock)
@patch(
    "src.quality.manager_job.get_unreviewed_resolved_escalations",
    new_callable=AsyncMock,
)
@patch("src.quality.manager_job.release_llm_attempt_lock", new_callable=AsyncMock)
async def test_manager_job_passes_transcript_mode_to_evaluator(
    mock_release_lock: AsyncMock,
    mock_get_unreviewed: AsyncMock,
    mock_already_reviewed: AsyncMock,
    mock_evaluate: AsyncMock,
    mock_save_review: AsyncMock,
    mock_record_success: AsyncMock,
    mock_session_factory: MagicMock,
) -> None:
    from src.quality.manager_job import evaluate_escalated_conversations

    esc_id = "esc-793"
    mock_get_unreviewed.return_value = [esc_id]
    mock_already_reviewed.return_value = False
    mock_evaluate.return_value = (
        SimpleNamespace(total_score=9.5, rating="good", summary="Solid handoff"),
        SimpleNamespace(),
    )

    escalation = SimpleNamespace(
        id=esc_id,
        conversation_id="conv-793",
        assigned_to="Manager",
        status=EscalationStatus.RESOLVED.value,
        created_at=datetime(2026, 4, 21, 9, 0, tzinfo=UTC),
        updated_at=datetime(2026, 4, 21, 9, 30, tzinfo=UTC),
        conversation=SimpleNamespace(metadata_={}),
    )
    exec_result = MagicMock()
    exec_result.scalar_one.return_value = escalation

    first_db = AsyncMock()
    second_db = AsyncMock()
    second_db.execute = AsyncMock(return_value=exec_result)
    second_db.scalar = AsyncMock(return_value=escalation.updated_at)

    lease = SimpleNamespace(
        attempt=SimpleNamespace(status="pending", attempt_count=1),
        lock_key="llm_attempt:lock:test",
        lock_token="token",
        backoff_key="llm_attempt:backoff:test",
    )
    begin_attempt = AsyncMock(return_value=lease)

    first_cm = AsyncMock()
    first_cm.__aenter__.return_value = first_db
    first_cm.__aexit__.return_value = False

    second_cm = AsyncMock()
    second_cm.__aenter__.return_value = second_db
    second_cm.__aexit__.return_value = False

    mock_session_factory.side_effect = [first_cm, second_cm]
    mock_redis = AsyncMock()
    mock_redis.set = AsyncMock(return_value=True)
    mock_redis.delete = AsyncMock()

    with patch("src.quality.manager_job.begin_llm_attempt", new=begin_attempt):
        await evaluate_escalated_conversations(
            _manager_quality_ctx(mock_redis, transcript_mode="full")
        )

    mock_evaluate.assert_awaited_once()
    assert mock_evaluate.await_args.kwargs["transcript_mode"].value == "full"


def test_manager_attempt_hashes_include_transcript_mode_and_summary_prompt_version() -> (
    None
):
    from src.quality.config import AIQualityTranscriptMode
    from src.quality.manager_job import _attempt_input_hash, _settings_hash

    escalation = SimpleNamespace(
        id="esc-794",
        conversation_id="conv-794",
        assigned_to="Manager",
        status=EscalationStatus.RESOLVED.value,
    )
    activity_at = datetime(2026, 4, 21, 11, 15, tzinfo=UTC)

    assert _attempt_input_hash(
        escalation,
        activity_at,
        transcript_mode=AIQualityTranscriptMode.SUMMARY,
    ) != _attempt_input_hash(
        escalation,
        activity_at,
        transcript_mode=AIQualityTranscriptMode.FULL,
    )
    assert _settings_hash(
        "fast-model",
        transcript_mode=AIQualityTranscriptMode.SUMMARY,
    ) != _settings_hash(
        "fast-model",
        transcript_mode=AIQualityTranscriptMode.FULL,
    )
