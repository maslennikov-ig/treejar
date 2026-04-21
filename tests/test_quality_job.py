"""Tests for quality background jobs."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


def _ai_quality_ctx(
    redis: AsyncMock,
    *,
    crm_client: AsyncMock | None = None,
    bot_mode: str = "scheduled",
    red_flags_mode: str = "scheduled",
    red_flags_model: str | None = None,
    max_calls_per_run: int = 10,
    max_calls_per_day: int = 20,
) -> dict[str, object]:
    redis.incr = AsyncMock(return_value=1)
    redis.expire = AsyncMock()
    redis.decr = AsyncMock()
    red_flags_config: dict[str, object] = {
        "mode": red_flags_mode,
        "daily_budget_cents": 100,
        "max_calls_per_run": max_calls_per_run,
        "max_calls_per_day": max_calls_per_day,
    }
    if red_flags_model is not None:
        red_flags_config["model"] = red_flags_model

    ctx: dict[str, object] = {
        "redis": redis,
        "ai_quality_controls": {
            "bot_qa": {
                "mode": bot_mode,
                "daily_budget_cents": 100,
                "max_calls_per_run": max_calls_per_run,
                "max_calls_per_day": max_calls_per_day,
            },
            "manager_qa": {"mode": "disabled"},
            "red_flags": red_flags_config,
        },
    }
    if crm_client is not None:
        ctx["crm_client"] = crm_client
    return ctx


def _make_evaluation_result(score: float = 30.0):
    from src.quality.schemas import BlockScore, CriterionScore, EvaluationResult

    criteria = [
        CriterionScore(
            rule_number=i,
            rule_name=f"Rule {i}",
            score=2,
            comment="ok",
            applicable=True,
        )
        for i in range(1, 16)
    ]
    return EvaluationResult(
        criteria=criteria,
        summary="Что сделано хорошо:\n- Сильное начало\n\nЧто ухудшило диалог:\n- н/д",
        total_score=score,
        rating="excellent",
        strengths=["Strong opening"],
        weaknesses=["No major issues"],
        recommendations=["Keep the same structure"],
        next_best_action="Send the requested quotation.",
        block_scores=[
            BlockScore(
                block_name="Opening & Trust", weight=6.0, points=6.0, applicable_rules=4
            ),
            BlockScore(
                block_name="Relationship & Discovery",
                weight=9.0,
                points=9.0,
                applicable_rules=5,
            ),
            BlockScore(
                block_name="Consultative Solution",
                weight=9.0,
                points=9.0,
                applicable_rules=3,
            ),
            BlockScore(
                block_name="Conversion & Next Step",
                weight=6.0,
                points=6.0,
                applicable_rules=3,
            ),
        ],
    )


def _make_red_flag_result(flag_codes: list[str]):
    from src.quality.schemas import RedFlagEvaluationResult, RedFlagItem

    flags = [
        RedFlagItem(
            code=code,
            title=code.replace("_", " ").title(),
            explanation=f"{code} explanation",
            evidence=[f"{code} evidence 1", f"{code} evidence 2"],
        )
        for code in flag_codes
    ]
    return RedFlagEvaluationResult(
        flags=flags,
        recommended_action="Review the conversation before the customer disengages.",
    )


def _make_candidate(
    *,
    status: str = "active",
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
    activity_at: datetime | None = None,
    sales_stage: str = "greeting",
    phone: str = "+971501234567",
    customer_name: str | None = "Acme",
    metadata_: dict[str, str] | None = None,
):
    return SimpleNamespace(
        conversation_id=uuid4(),
        status=status,
        created_at=created_at or datetime.now(tz=UTC) - timedelta(hours=1),
        updated_at=updated_at or datetime.now(tz=UTC),
        activity_at=activity_at,
        sales_stage=sales_stage,
        phone=phone,
        customer_name=customer_name,
        metadata_=(
            {"inbound_channel_phone": "+971551220665"}
            if metadata_ is None
            else metadata_
        ),
    )


def _make_session_ctx(mock_db: AsyncMock) -> AsyncMock:
    mock_session_ctx = AsyncMock()
    mock_session_ctx.__aenter__.return_value = mock_db
    mock_session_ctx.__aexit__.return_value = False
    return mock_session_ctx


def _make_attempt_lease() -> SimpleNamespace:
    return SimpleNamespace(
        attempt=SimpleNamespace(status="pending", attempt_count=1),
        lock_key="llm_attempt:lock:test",
        lock_token="token",
        backoff_key="llm_attempt:backoff:test",
    )


def _make_terminal_success_attempt(result_json: dict[str, object]) -> SimpleNamespace:
    return SimpleNamespace(status="success", result_json=result_json)


def test_ai_quality_manual_mode_blocks_scheduled_runs_but_allows_manual() -> None:
    """Manual mode should disable cron automation without disabling operator runs."""
    from src.quality.config import (
        AIQualityControlsConfig,
        AIQualityScope,
        evaluate_ai_quality_run_gate,
    )

    config = AIQualityControlsConfig.model_validate({"bot_qa": {"mode": "manual"}})

    scheduled = evaluate_ai_quality_run_gate(
        config,
        scope=AIQualityScope.BOT_QA,
        trigger="scheduled",
    )
    manual = evaluate_ai_quality_run_gate(
        config,
        scope=AIQualityScope.BOT_QA,
        trigger="manual",
    )

    assert scheduled.allowed is False
    assert scheduled.reason == "manual_only"
    assert manual.allowed is True


@pytest.mark.asyncio
async def test_ai_quality_daily_sample_reserves_one_scheduled_run_per_day() -> None:
    """Daily sample mode should not execute on every cron tick."""
    from src.quality.config import (
        AIQualityControlsConfig,
        AIQualityScope,
        evaluate_ai_quality_run_gate,
        reserve_ai_quality_daily_sample_from_ctx,
    )

    config = AIQualityControlsConfig.model_validate(
        {"red_flags": {"mode": "daily_sample"}}
    )
    gate = evaluate_ai_quality_run_gate(
        config,
        scope=AIQualityScope.RED_FLAGS,
        trigger="scheduled",
    )
    redis = AsyncMock()
    redis.set = AsyncMock(side_effect=[True, False])

    first = await reserve_ai_quality_daily_sample_from_ctx({"redis": redis}, gate)
    second = await reserve_ai_quality_daily_sample_from_ctx({"redis": redis}, gate)

    assert first.allowed is True
    assert second.allowed is False
    assert second.reason == "daily_sample_already_run"
    assert redis.set.await_args_list[0].kwargs["nx"] is True
    assert redis.set.await_args_list[0].kwargs["ex"] > 0


@pytest.mark.asyncio
async def test_ai_quality_invalid_ctx_config_falls_back_to_safe_defaults() -> None:
    """Malformed injected config must disable QA work instead of crashing jobs."""
    from src.quality.config import (
        AIQualityScope,
        get_ai_quality_run_gate_from_ctx,
    )

    gate = await get_ai_quality_run_gate_from_ctx(
        {"ai_quality_controls": {"bot_qa": {"model": "z-ai/glm-5"}}},
        scope=AIQualityScope.BOT_QA,
        trigger="scheduled",
    )

    assert gate.allowed is False
    assert gate.reason == "disabled"


@pytest.mark.asyncio
async def test_ai_quality_daily_call_quota_blocks_after_daily_max() -> None:
    """max_calls_per_day should be enforced across repeated cron runs."""
    from src.quality.config import (
        AIQualityControlsConfig,
        AIQualityScope,
        consume_ai_quality_daily_call_from_ctx,
        evaluate_ai_quality_run_gate,
    )

    config = AIQualityControlsConfig.model_validate(
        {"bot_qa": {"mode": "scheduled", "max_calls_per_day": 1}}
    )
    gate = evaluate_ai_quality_run_gate(
        config,
        scope=AIQualityScope.BOT_QA,
        trigger="scheduled",
    )
    redis = AsyncMock()
    redis.incr = AsyncMock(side_effect=[1, 2])
    redis.expire = AsyncMock()
    redis.decr = AsyncMock()

    assert await consume_ai_quality_daily_call_from_ctx({"redis": redis}, gate) is True
    assert await consume_ai_quality_daily_call_from_ctx({"redis": redis}, gate) is False
    redis.expire.assert_awaited_once()
    redis.decr.assert_awaited_once()


@pytest.mark.asyncio
async def test_red_flag_disabled_mode_returns_before_candidate_fetch() -> None:
    """Disabled red-flag scope must perform no candidate scan or LLM work."""
    from src.quality.job import evaluate_realtime_red_flags

    mock_redis = AsyncMock()
    fetch_mock = AsyncMock(side_effect=AssertionError("unexpected candidate fetch"))
    evaluate_mock = AsyncMock(side_effect=AssertionError("unexpected LLM call"))

    with (
        patch(
            "src.quality.job.get_recent_assistant_conversation_candidates",
            new=fetch_mock,
        ),
        patch("src.quality.job.evaluate_red_flags", new=evaluate_mock),
    ):
        await evaluate_realtime_red_flags(
            _ai_quality_ctx(mock_redis, red_flags_mode="disabled")
        )

    fetch_mock.assert_not_awaited()
    evaluate_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_final_review_disabled_mode_returns_before_candidate_fetch() -> None:
    """Disabled bot-QA scope must perform no candidate scan or LLM work."""
    from src.quality.job import evaluate_mature_conversations_quality

    mock_redis = AsyncMock()
    fetch_mock = AsyncMock(side_effect=AssertionError("unexpected candidate fetch"))
    evaluate_mock = AsyncMock(side_effect=AssertionError("unexpected LLM call"))

    with (
        patch(
            "src.quality.job.get_recent_updated_conversation_candidates", new=fetch_mock
        ),
        patch("src.quality.job.evaluate_conversation", new=evaluate_mock),
    ):
        await evaluate_mature_conversations_quality(
            _ai_quality_ctx(mock_redis, bot_mode="disabled")
        )

    fetch_mock.assert_not_awaited()
    evaluate_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_red_flag_job_respects_max_calls_per_run() -> None:
    """Scheduled red-flag scope should cap LLM calls per job run."""
    from src.quality.job import evaluate_realtime_red_flags

    candidates = [_make_candidate(), _make_candidate(), _make_candidate()]
    query_db = AsyncMock()
    worker_db = AsyncMock()
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.setex = AsyncMock()
    evaluate_mock = AsyncMock(return_value=_make_red_flag_result([]))

    with (
        patch(
            "src.quality.job.async_session_factory",
            side_effect=[_make_session_ctx(query_db), _make_session_ctx(worker_db)],
        ),
        patch(
            "src.quality.job.get_recent_assistant_conversation_candidates",
            new=AsyncMock(return_value=candidates),
        ),
        patch("src.quality.job.evaluate_red_flags", new=evaluate_mock),
        patch("src.quality.job.record_llm_attempt_no_action", new=AsyncMock()),
        patch("src.quality.job.release_llm_attempt_lock", new=AsyncMock()),
    ):
        await evaluate_realtime_red_flags(
            _ai_quality_ctx(
                mock_redis,
                red_flags_model="test/red-flag-model",
                max_calls_per_run=1,
            )
        )

    evaluate_mock.assert_awaited_once()
    assert evaluate_mock.await_args.kwargs["model_name"] == "test/red-flag-model"


@pytest.mark.asyncio
async def test_red_flag_warning_fires_only_when_flags_exist() -> None:
    """Realtime warning job should notify only for actual red flags."""
    from src.quality.job import evaluate_realtime_red_flags

    candidate_a = _make_candidate()
    candidate_b = _make_candidate(sales_stage="qualifying")
    query_db = AsyncMock()
    worker_db_a = AsyncMock()
    worker_db_b = AsyncMock()
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(side_effect=[None, None])
    mock_redis.setex = AsyncMock()
    mock_notify = AsyncMock()

    with (
        patch(
            "src.quality.job.async_session_factory",
            side_effect=[
                _make_session_ctx(query_db),
                _make_session_ctx(worker_db_a),
                _make_session_ctx(worker_db_b),
            ],
        ),
        patch(
            "src.quality.job.get_recent_assistant_conversation_candidates",
            new=AsyncMock(return_value=[candidate_a, candidate_b]),
        ),
        patch(
            "src.quality.job.evaluate_red_flags",
            new=AsyncMock(
                side_effect=[
                    _make_red_flag_result([]),
                    _make_red_flag_result(["missing_identity"]),
                ]
            ),
        ),
        patch("src.services.notifications.notify_red_flag_warning", new=mock_notify),
    ):
        await evaluate_realtime_red_flags(_ai_quality_ctx(mock_redis))

    mock_notify.assert_awaited_once()
    mock_redis.setex.assert_awaited_once()
    assert mock_redis.setex.await_args.args[0].startswith("quality:redflag:")


@pytest.mark.asyncio
async def test_red_flag_terminal_success_replays_notification_without_llm_call() -> (
    None
):
    """Terminal red-flag success should replay delivery from cached result JSON."""
    from src.quality.job import evaluate_realtime_red_flags

    candidate = _make_candidate()
    query_db = AsyncMock()
    worker_db = AsyncMock()
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.setex = AsyncMock()
    mock_crm = AsyncMock()
    mock_notify = AsyncMock()
    begin_attempt = AsyncMock(return_value=None)
    terminal_attempt = _make_terminal_success_attempt(
        {
            "flags": [
                {
                    "code": "missing_identity",
                    "title": "Missing identity",
                    "explanation": "missing_identity explanation",
                    "evidence": ["evidence"],
                }
            ],
            "recommended_action": "Check the dialog.",
        }
    )

    with (
        patch(
            "src.quality.job.async_session_factory",
            side_effect=[_make_session_ctx(query_db), _make_session_ctx(worker_db)],
        ),
        patch(
            "src.quality.job.get_recent_assistant_conversation_candidates",
            new=AsyncMock(return_value=[candidate]),
        ),
        patch("src.quality.job.begin_llm_attempt", new=begin_attempt),
        patch(
            "src.quality.job._load_quality_attempt",
            new=AsyncMock(return_value=terminal_attempt),
        ),
        patch(
            "src.quality.job.should_send_telegram_alert_for_conversation_with_db",
            new=AsyncMock(return_value=True),
        ),
        patch("src.services.notifications.notify_red_flag_warning", new=mock_notify),
        patch(
            "src.quality.job.evaluate_red_flags",
            new=AsyncMock(side_effect=AssertionError("unexpected LLM call")),
        ),
    ):
        await evaluate_realtime_red_flags(
            _ai_quality_ctx(mock_redis, crm_client=mock_crm)
        )

    begin_attempt.assert_awaited_once()
    mock_notify.assert_awaited_once()
    assert mock_redis.setex.await_count == 1
    query_db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_red_flag_no_flags_records_no_action_attempt() -> None:
    """No-flag red-flag scans should persist no_action to avoid cron rescans."""
    from src.quality.job import evaluate_realtime_red_flags

    candidate = _make_candidate()
    query_db = AsyncMock()
    worker_db = AsyncMock()
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.setex = AsyncMock()
    lease = _make_attempt_lease()
    record_no_action = AsyncMock()

    with (
        patch(
            "src.quality.job.async_session_factory",
            side_effect=[_make_session_ctx(query_db), _make_session_ctx(worker_db)],
        ),
        patch(
            "src.quality.job.get_recent_assistant_conversation_candidates",
            new=AsyncMock(return_value=[candidate]),
        ),
        patch(
            "src.quality.job.begin_llm_attempt",
            new=AsyncMock(return_value=lease),
        ),
        patch("src.quality.job.record_llm_attempt_no_action", new=record_no_action),
        patch("src.quality.job.release_llm_attempt_lock", new=AsyncMock()),
        patch(
            "src.quality.job.evaluate_red_flags",
            new=AsyncMock(return_value=_make_red_flag_result([])),
        ),
    ):
        await evaluate_realtime_red_flags(_ai_quality_ctx(mock_redis))

    record_no_action.assert_awaited_once()
    assert record_no_action.await_args.kwargs["result_json"]["flags"] == []
    worker_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_final_review_budget_block_records_attempt_error() -> None:
    """Budget blocks from the safety layer should be written as attempt state."""
    from src.llm.safety import LLMBudgetBlocked
    from src.quality.job import evaluate_mature_conversations_quality

    candidate = _make_candidate(status="closed", updated_at=datetime.now(tz=UTC))
    query_db = AsyncMock()
    worker_db = AsyncMock()
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.setex = AsyncMock()
    lease = _make_attempt_lease()
    record_error = AsyncMock()
    budget_error = LLMBudgetBlocked("budget exhausted")

    with (
        patch(
            "src.quality.job.async_session_factory",
            side_effect=[_make_session_ctx(query_db), _make_session_ctx(worker_db)],
        ),
        patch(
            "src.quality.job.get_recent_updated_conversation_candidates",
            new=AsyncMock(return_value=[candidate]),
        ),
        patch(
            "src.quality.job.begin_llm_attempt",
            new=AsyncMock(return_value=lease),
        ),
        patch("src.quality.job.record_llm_attempt_error", new=record_error),
        patch("src.quality.job.release_llm_attempt_lock", new=AsyncMock()),
        patch(
            "src.quality.job.evaluate_conversation",
            new=AsyncMock(side_effect=budget_error),
        ),
        patch("src.quality.job.save_review", new=AsyncMock()),
    ):
        await evaluate_mature_conversations_quality(_ai_quality_ctx(mock_redis))

    record_error.assert_awaited_once()
    assert record_error.await_args.args[2] is budget_error
    worker_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_final_review_save_failure_does_not_record_attempt_error() -> None:
    """save_review failures should stay out of the failed_final attempt bucket."""
    from src.quality.job import evaluate_mature_conversations_quality

    candidate = _make_candidate(status="closed", updated_at=datetime.now(tz=UTC))
    query_db = AsyncMock()
    worker_db = AsyncMock()
    worker_db.rollback = AsyncMock()
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.setex = AsyncMock()
    lease = _make_attempt_lease()
    record_error = AsyncMock()
    record_success = AsyncMock()

    with (
        patch(
            "src.quality.job.async_session_factory",
            side_effect=[_make_session_ctx(query_db), _make_session_ctx(worker_db)],
        ),
        patch(
            "src.quality.job.get_recent_updated_conversation_candidates",
            new=AsyncMock(return_value=[candidate]),
        ),
        patch("src.quality.job.begin_llm_attempt", new=AsyncMock(return_value=lease)),
        patch("src.quality.job.record_llm_attempt_success", new=record_success),
        patch("src.quality.job.record_llm_attempt_error", new=record_error),
        patch("src.quality.job.release_llm_attempt_lock", new=AsyncMock()),
        patch(
            "src.quality.job.evaluate_conversation",
            new=AsyncMock(return_value=_make_evaluation_result(score=18.0)),
        ),
        patch(
            "src.quality.job.save_review",
            new=AsyncMock(side_effect=RuntimeError("save failed")),
        ),
    ):
        await evaluate_mature_conversations_quality(_ai_quality_ctx(mock_redis))

    worker_db.rollback.assert_awaited_once()
    record_error.assert_not_awaited()
    record_success.assert_awaited_once()


@pytest.mark.asyncio
async def test_final_review_replays_terminal_success_from_result_json() -> None:
    """Terminal final-review success should replay review materialization and delivery."""
    from src.quality.job import evaluate_mature_conversations_quality

    candidate = _make_candidate(status="closed", updated_at=datetime.now(tz=UTC))
    query_db = AsyncMock()
    worker_db = AsyncMock()
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.setex = AsyncMock()
    mock_crm = AsyncMock()
    mock_notify = AsyncMock()
    terminal_attempt = _make_terminal_success_attempt(
        _make_evaluation_result(score=18.0).model_dump(mode="json")
    )

    with (
        patch(
            "src.quality.job.async_session_factory",
            side_effect=[_make_session_ctx(query_db), _make_session_ctx(worker_db)],
        ),
        patch(
            "src.quality.job.get_recent_updated_conversation_candidates",
            new=AsyncMock(return_value=[candidate]),
        ),
        patch(
            "src.quality.job.begin_llm_attempt",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "src.quality.job._load_quality_attempt",
            new=AsyncMock(return_value=terminal_attempt),
        ),
        patch(
            "src.quality.job.get_review_for_conversation",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "src.quality.job.should_send_telegram_alert_for_conversation_with_db",
            new=AsyncMock(return_value=True),
        ),
        patch("src.quality.job.save_review", new=AsyncMock()),
        patch(
            "src.services.notifications.notify_final_quality_review",
            new=mock_notify,
        ),
        patch(
            "src.quality.job.evaluate_conversation",
            new=AsyncMock(side_effect=AssertionError("unexpected LLM call")),
        ),
    ):
        await evaluate_mature_conversations_quality(
            _ai_quality_ctx(mock_redis, crm_client=mock_crm)
        )

    mock_notify.assert_awaited_once()
    query_db.commit.assert_not_awaited()
    assert mock_redis.setex.await_count == 1


@pytest.mark.asyncio
async def test_red_flag_attempt_key_uses_latest_assistant_activity() -> None:
    """Red-flag no_action should not suppress later assistant turns."""
    from src.quality.job import evaluate_realtime_red_flags

    conversation_updated_at = datetime(2026, 4, 21, 9, 0, tzinfo=UTC)
    latest_assistant_at = datetime(2026, 4, 21, 10, 30, tzinfo=UTC)
    candidate = _make_candidate(
        updated_at=conversation_updated_at,
        activity_at=latest_assistant_at,
    )
    query_db = AsyncMock()
    worker_db = AsyncMock()
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.setex = AsyncMock()
    lease = _make_attempt_lease()
    begin_attempt = AsyncMock(return_value=lease)

    with (
        patch(
            "src.quality.job.async_session_factory",
            side_effect=[_make_session_ctx(query_db), _make_session_ctx(worker_db)],
        ),
        patch(
            "src.quality.job.get_recent_assistant_conversation_candidates",
            new=AsyncMock(return_value=[candidate]),
        ),
        patch("src.quality.job.begin_llm_attempt", new=begin_attempt),
        patch("src.quality.job.record_llm_attempt_no_action", new=AsyncMock()),
        patch("src.quality.job.release_llm_attempt_lock", new=AsyncMock()),
        patch(
            "src.quality.job.evaluate_red_flags",
            new=AsyncMock(return_value=_make_red_flag_result([])),
        ),
    ):
        await evaluate_realtime_red_flags(_ai_quality_ctx(mock_redis))

    assert begin_attempt.await_args.kwargs["entity_updated_at"] == latest_assistant_at


@pytest.mark.asyncio
async def test_final_review_attempt_key_uses_latest_transcript_activity() -> None:
    """Final review should key off the latest transcript activity, not parent updated_at."""
    from src.quality.job import evaluate_mature_conversations_quality

    parent_updated_at = datetime(2026, 4, 21, 9, 0, tzinfo=UTC)
    transcript_activity_at = datetime(2026, 4, 21, 11, 15, tzinfo=UTC)
    candidate = _make_candidate(
        status="closed",
        updated_at=parent_updated_at,
        activity_at=transcript_activity_at,
    )
    query_db = AsyncMock()
    worker_db = AsyncMock()
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.setex = AsyncMock()
    lease = _make_attempt_lease()
    begin_attempt = AsyncMock(return_value=lease)

    with (
        patch(
            "src.quality.job.async_session_factory",
            side_effect=[_make_session_ctx(query_db), _make_session_ctx(worker_db)],
        ),
        patch(
            "src.quality.job.get_recent_updated_conversation_candidates",
            new=AsyncMock(return_value=[candidate]),
        ),
        patch("src.quality.job.begin_llm_attempt", new=begin_attempt),
        patch("src.quality.job.release_llm_attempt_lock", new=AsyncMock()),
        patch(
            "src.quality.job.evaluate_conversation",
            new=AsyncMock(return_value=_make_evaluation_result(score=18.0)),
        ),
        patch("src.quality.job.save_review", new=AsyncMock()),
        patch(
            "src.quality.job.should_send_telegram_alert_for_conversation_with_db",
            new=AsyncMock(return_value=False),
        ),
    ):
        await evaluate_mature_conversations_quality(_ai_quality_ctx(mock_redis))

    assert (
        begin_attempt.await_args.kwargs["entity_updated_at"] == transcript_activity_at
    )


@pytest.mark.asyncio
async def test_red_flag_warning_passes_identity_context_without_crm_lookup() -> None:
    """Realtime warning should thread identity fields and prefer conversation name."""
    from src.quality.job import evaluate_realtime_red_flags

    created_at = datetime(2026, 4, 9, 9, 0, tzinfo=UTC)
    updated_at = datetime(2026, 4, 9, 10, 0, tzinfo=UTC)
    candidate = _make_candidate(
        created_at=created_at,
        updated_at=updated_at,
        customer_name="Acme",
    )
    query_db = AsyncMock()
    worker_db = AsyncMock()
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.setex = AsyncMock()
    mock_notify = AsyncMock()
    mock_crm = AsyncMock()

    with (
        patch(
            "src.quality.job.async_session_factory",
            side_effect=[_make_session_ctx(query_db), _make_session_ctx(worker_db)],
        ),
        patch(
            "src.quality.job.get_recent_assistant_conversation_candidates",
            new=AsyncMock(return_value=[candidate]),
        ),
        patch(
            "src.quality.job.evaluate_red_flags",
            new=AsyncMock(return_value=_make_red_flag_result(["missing_identity"])),
        ),
        patch("src.services.notifications.notify_red_flag_warning", new=mock_notify),
    ):
        await evaluate_realtime_red_flags(
            _ai_quality_ctx(mock_redis, crm_client=mock_crm)
        )

    mock_notify.assert_awaited_once()
    kwargs = mock_notify.await_args.kwargs
    assert kwargs["customer_name"] == "Acme"
    assert kwargs["inbound_channel_phone"] == "+971551220665"
    assert kwargs["conversation_created_at"] == created_at
    assert kwargs["last_activity_at"] == updated_at
    mock_crm.find_contact_by_phone.assert_not_awaited()


@pytest.mark.asyncio
async def test_same_red_flag_signature_does_not_repeat() -> None:
    """Realtime warning job should suppress duplicate signatures."""
    from src.quality.job import evaluate_realtime_red_flags

    candidate = _make_candidate()
    query_db = AsyncMock()
    worker_db = AsyncMock()
    mock_redis = AsyncMock()
    marker = {
        "signature": "same-signature",
        "updated_at": candidate.updated_at.isoformat(),
    }
    mock_redis.get = AsyncMock(return_value=json.dumps(marker))
    mock_redis.setex = AsyncMock()
    mock_notify = AsyncMock()

    with (
        patch(
            "src.quality.job.async_session_factory",
            side_effect=[_make_session_ctx(query_db), _make_session_ctx(worker_db)],
        ),
        patch(
            "src.quality.job.get_recent_assistant_conversation_candidates",
            new=AsyncMock(return_value=[candidate]),
        ),
        patch(
            "src.quality.job.evaluate_red_flags",
            new=AsyncMock(return_value=_make_red_flag_result(["missing_identity"])),
        ),
        patch(
            "src.quality.job._build_red_flag_signature",
            return_value="same-signature",
        ),
        patch("src.services.notifications.notify_red_flag_warning", new=mock_notify),
    ):
        await evaluate_realtime_red_flags(_ai_quality_ctx(mock_redis))

    mock_notify.assert_not_awaited()
    mock_redis.setex.assert_not_awaited()


@pytest.mark.asyncio
async def test_changed_red_flag_signature_realerts() -> None:
    """Realtime warning job should re-alert when the flag signature changes."""
    from src.quality.job import evaluate_realtime_red_flags

    candidate = _make_candidate()
    query_db = AsyncMock()
    worker_db = AsyncMock()
    mock_redis = AsyncMock()
    marker = {
        "signature": "old-signature",
        "updated_at": candidate.updated_at.isoformat(),
    }
    mock_redis.get = AsyncMock(return_value=json.dumps(marker))
    mock_redis.setex = AsyncMock()
    mock_notify = AsyncMock()

    with (
        patch(
            "src.quality.job.async_session_factory",
            side_effect=[_make_session_ctx(query_db), _make_session_ctx(worker_db)],
        ),
        patch(
            "src.quality.job.get_recent_assistant_conversation_candidates",
            new=AsyncMock(return_value=[candidate]),
        ),
        patch(
            "src.quality.job.evaluate_red_flags",
            new=AsyncMock(
                return_value=_make_red_flag_result(
                    ["missing_identity", "ignored_question"]
                )
            ),
        ),
        patch(
            "src.quality.job._build_red_flag_signature",
            return_value="new-signature",
        ),
        patch("src.services.notifications.notify_red_flag_warning", new=mock_notify),
    ):
        await evaluate_realtime_red_flags(_ai_quality_ctx(mock_redis))

    mock_notify.assert_awaited_once()
    mock_redis.setex.assert_awaited_once()


@pytest.mark.asyncio
async def test_red_flag_warning_skips_telegram_for_blocked_inbound_phone() -> None:
    """Realtime warning job should stay fail-closed outside the allowed inbound."""
    from src.quality.job import evaluate_realtime_red_flags

    candidate = _make_candidate(metadata_={"inbound_channel_phone": "+971509999999"})
    query_db = AsyncMock()
    worker_db = AsyncMock()
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.setex = AsyncMock()
    mock_notify = AsyncMock()

    with (
        patch(
            "src.quality.job.async_session_factory",
            side_effect=[_make_session_ctx(query_db), _make_session_ctx(worker_db)],
        ),
        patch(
            "src.quality.job.get_recent_assistant_conversation_candidates",
            new=AsyncMock(return_value=[candidate]),
        ),
        patch(
            "src.quality.job.evaluate_red_flags",
            new=AsyncMock(return_value=_make_red_flag_result(["missing_identity"])),
        ),
        patch("src.services.notifications.notify_red_flag_warning", new=mock_notify),
        patch(
            "src.services.inbound_channels.settings.telegram_allowed_inbound_phone",
            "+971551220665",
        ),
    ):
        await evaluate_realtime_red_flags(_ai_quality_ctx(mock_redis))

    mock_notify.assert_not_awaited()
    mock_redis.setex.assert_awaited_once()


@pytest.mark.asyncio
async def test_red_flag_warning_paginates_full_candidate_set() -> None:
    """Realtime warning job should keep reading candidate pages beyond the first batch."""
    from src.quality.job import evaluate_realtime_red_flags

    candidate_a = _make_candidate()
    candidate_b = _make_candidate()
    candidate_c = _make_candidate()
    query_db = AsyncMock()
    worker_db_a = AsyncMock()
    worker_db_b = AsyncMock()
    worker_db_c = AsyncMock()
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(side_effect=[None, None, None])
    mock_redis.setex = AsyncMock()
    mock_notify = AsyncMock()
    fetch_mock = AsyncMock(return_value=[candidate_a, candidate_b])
    fetch_mock.side_effect = [[candidate_a, candidate_b], [candidate_c]]

    with (
        patch("src.quality.job._QUERY_BATCH_SIZE", 2),
        patch(
            "src.quality.job.async_session_factory",
            side_effect=[
                _make_session_ctx(query_db),
                _make_session_ctx(worker_db_a),
                _make_session_ctx(worker_db_b),
                _make_session_ctx(worker_db_c),
            ],
        ),
        patch(
            "src.quality.job.get_recent_assistant_conversation_candidates",
            new=fetch_mock,
        ),
        patch(
            "src.quality.job.evaluate_red_flags",
            new=AsyncMock(return_value=_make_red_flag_result(["missing_identity"])),
        ),
        patch("src.services.notifications.notify_red_flag_warning", new=mock_notify),
    ):
        await evaluate_realtime_red_flags(_ai_quality_ctx(mock_redis))

    assert fetch_mock.await_count == 2
    assert fetch_mock.await_args_list[0].kwargs["offset"] == 0
    assert fetch_mock.await_args_list[1].kwargs["offset"] == 2
    assert mock_notify.await_count == 3


@pytest.mark.asyncio
async def test_final_review_triggers_on_closed() -> None:
    """Final review job should send a review for closed conversations."""
    from src.quality.job import evaluate_mature_conversations_quality

    candidate = _make_candidate(status="closed", updated_at=datetime.now(tz=UTC))
    query_db = AsyncMock()
    worker_db = AsyncMock()
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.setex = AsyncMock()
    mock_notify = AsyncMock()
    mock_save = AsyncMock()

    with (
        patch(
            "src.quality.job.async_session_factory",
            side_effect=[_make_session_ctx(query_db), _make_session_ctx(worker_db)],
        ),
        patch(
            "src.quality.job.get_recent_updated_conversation_candidates",
            new=AsyncMock(return_value=[candidate]),
        ),
        patch(
            "src.quality.job.evaluate_conversation",
            new=AsyncMock(return_value=_make_evaluation_result(score=18.0)),
        ),
        patch("src.quality.job.save_review", new=mock_save),
        patch(
            "src.services.notifications.notify_final_quality_review", new=mock_notify
        ),
    ):
        await evaluate_mature_conversations_quality(_ai_quality_ctx(mock_redis))

    mock_save.assert_awaited_once()
    mock_notify.assert_awaited_once()
    assert mock_notify.await_args.kwargs["trigger"] == "closed"
    assert worker_db.commit.await_count == 3


@pytest.mark.asyncio
async def test_final_review_fetches_customer_name_from_crm_and_caches_it() -> None:
    """Final review should enrich customer name from Zoho when conversation/cache miss."""
    from src.quality.job import evaluate_mature_conversations_quality

    created_at = datetime(2026, 4, 9, 9, 0, tzinfo=UTC)
    updated_at = datetime(2026, 4, 9, 13, 5, tzinfo=UTC)
    candidate = _make_candidate(
        status="closed",
        created_at=created_at,
        updated_at=updated_at,
        customer_name=None,
    )
    query_db = AsyncMock()
    worker_db = AsyncMock()
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(side_effect=[None, None])
    mock_redis.set = AsyncMock()
    mock_redis.setex = AsyncMock()
    mock_notify = AsyncMock()
    mock_crm = AsyncMock()
    mock_crm.find_contact_by_phone = AsyncMock(
        return_value={
            "First_Name": "Aisha",
            "Last_Name": "Khan",
            "Segment": "B2B",
        }
    )

    with (
        patch(
            "src.quality.job.async_session_factory",
            side_effect=[_make_session_ctx(query_db), _make_session_ctx(worker_db)],
        ),
        patch(
            "src.quality.job.get_recent_updated_conversation_candidates",
            new=AsyncMock(return_value=[candidate]),
        ),
        patch(
            "src.quality.job.evaluate_conversation",
            new=AsyncMock(return_value=_make_evaluation_result(score=18.0)),
        ),
        patch("src.quality.job.save_review", new=AsyncMock()),
        patch(
            "src.services.notifications.notify_final_quality_review", new=mock_notify
        ),
    ):
        await evaluate_mature_conversations_quality(
            _ai_quality_ctx(mock_redis, crm_client=mock_crm)
        )

    mock_notify.assert_awaited_once()
    kwargs = mock_notify.await_args.kwargs
    assert kwargs["customer_name"] == "Aisha Khan"
    assert kwargs["inbound_channel_phone"] == "+971551220665"
    assert kwargs["conversation_created_at"] == created_at
    assert kwargs["last_activity_at"] == updated_at
    mock_crm.find_contact_by_phone.assert_awaited_once_with("+971501234567")
    assert mock_redis.set.await_count == 2


@pytest.mark.asyncio
async def test_final_review_persists_marker_when_identity_enrichment_fails() -> None:
    """Transient cache/CRM failures should degrade to placeholder and keep marker."""
    from src.quality.job import evaluate_mature_conversations_quality

    candidate = _make_candidate(
        status="closed",
        updated_at=datetime.now(tz=UTC) - timedelta(hours=4),
        customer_name="Valued Customer",
    )
    query_db = AsyncMock()
    worker_db = AsyncMock()
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(side_effect=[None, RuntimeError("redis down")])
    mock_redis.setex = AsyncMock()
    mock_notify = AsyncMock()
    mock_crm = AsyncMock()
    mock_crm.find_contact_by_phone = AsyncMock(side_effect=RuntimeError("crm down"))

    with (
        patch(
            "src.quality.job.async_session_factory",
            side_effect=[_make_session_ctx(query_db), _make_session_ctx(worker_db)],
        ),
        patch(
            "src.quality.job.get_recent_updated_conversation_candidates",
            new=AsyncMock(return_value=[candidate]),
        ),
        patch(
            "src.quality.job.evaluate_conversation",
            new=AsyncMock(return_value=_make_evaluation_result(score=18.0)),
        ),
        patch("src.quality.job.save_review", new=AsyncMock()),
        patch(
            "src.services.notifications.notify_final_quality_review", new=mock_notify
        ),
    ):
        await evaluate_mature_conversations_quality(
            _ai_quality_ctx(mock_redis, crm_client=mock_crm)
        )

    mock_notify.assert_awaited_once()
    assert mock_notify.await_args.kwargs["customer_name"] == "не указано"
    mock_redis.setex.assert_awaited_once()


@pytest.mark.asyncio
async def test_final_review_triggers_on_idle_threshold() -> None:
    """Final review job should send a review after 3 hours of inactivity."""
    from src.quality.job import evaluate_mature_conversations_quality

    candidate = _make_candidate(
        updated_at=datetime.now(tz=UTC) - timedelta(hours=3, minutes=5),
        sales_stage="solution",
    )
    query_db = AsyncMock()
    worker_db = AsyncMock()
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.setex = AsyncMock()
    mock_notify = AsyncMock()

    with (
        patch(
            "src.quality.job.async_session_factory",
            side_effect=[_make_session_ctx(query_db), _make_session_ctx(worker_db)],
        ),
        patch(
            "src.quality.job.get_recent_updated_conversation_candidates",
            new=AsyncMock(return_value=[candidate]),
        ),
        patch("src.quality.job.save_review", new=AsyncMock()),
        patch(
            "src.quality.job.evaluate_conversation",
            new=AsyncMock(return_value=_make_evaluation_result(score=21.0)),
        ),
        patch(
            "src.services.notifications.notify_final_quality_review", new=mock_notify
        ),
    ):
        await evaluate_mature_conversations_quality(_ai_quality_ctx(mock_redis))

    mock_notify.assert_awaited_once()
    assert mock_notify.await_args.kwargs["trigger"] == "idle 3h"


@pytest.mark.asyncio
async def test_final_review_does_not_trigger_before_idle_threshold() -> None:
    """Final review job should skip active conversations before 3 hours of inactivity."""
    from src.quality.job import evaluate_mature_conversations_quality

    candidate = _make_candidate(
        updated_at=datetime.now(tz=UTC) - timedelta(hours=2, minutes=59)
    )
    query_db = AsyncMock()
    mock_redis = AsyncMock()
    mock_notify = AsyncMock()
    mock_evaluate = AsyncMock()

    with (
        patch(
            "src.quality.job.async_session_factory",
            return_value=_make_session_ctx(query_db),
        ),
        patch(
            "src.quality.job.get_recent_updated_conversation_candidates",
            new=AsyncMock(return_value=[candidate]),
        ),
        patch("src.quality.job.evaluate_conversation", new=mock_evaluate),
        patch(
            "src.services.notifications.notify_final_quality_review", new=mock_notify
        ),
    ):
        await evaluate_mature_conversations_quality(_ai_quality_ctx(mock_redis))

    mock_evaluate.assert_not_awaited()
    mock_notify.assert_not_awaited()


@pytest.mark.asyncio
async def test_final_review_paginates_full_candidate_set() -> None:
    """Final review job should keep evaluating pages beyond the first candidate batch."""
    from src.quality.job import evaluate_mature_conversations_quality

    candidate_a = _make_candidate(
        status="closed", updated_at=datetime.now(tz=UTC) - timedelta(hours=4)
    )
    candidate_b = _make_candidate(
        status="closed", updated_at=datetime.now(tz=UTC) - timedelta(hours=5)
    )
    candidate_c = _make_candidate(
        status="closed", updated_at=datetime.now(tz=UTC) - timedelta(hours=6)
    )
    query_db = AsyncMock()
    worker_db_a = AsyncMock()
    worker_db_b = AsyncMock()
    worker_db_c = AsyncMock()
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(side_effect=[None, None, None])
    mock_redis.setex = AsyncMock()
    mock_notify = AsyncMock()
    fetch_mock = AsyncMock(side_effect=[[candidate_a, candidate_b], [candidate_c]])

    with (
        patch("src.quality.job._QUERY_BATCH_SIZE", 2),
        patch(
            "src.quality.job.async_session_factory",
            side_effect=[
                _make_session_ctx(query_db),
                _make_session_ctx(worker_db_a),
                _make_session_ctx(worker_db_b),
                _make_session_ctx(worker_db_c),
            ],
        ),
        patch(
            "src.quality.job.get_recent_updated_conversation_candidates",
            new=fetch_mock,
        ),
        patch(
            "src.quality.job.evaluate_conversation",
            new=AsyncMock(return_value=_make_evaluation_result(score=18.0)),
        ),
        patch("src.quality.job.save_review", new=AsyncMock()),
        patch(
            "src.services.notifications.notify_final_quality_review", new=mock_notify
        ),
    ):
        await evaluate_mature_conversations_quality(_ai_quality_ctx(mock_redis))

    assert fetch_mock.await_count == 2
    assert fetch_mock.await_args_list[0].kwargs["offset"] == 0
    assert fetch_mock.await_args_list[1].kwargs["offset"] == 2
    assert mock_notify.await_count == 3


@pytest.mark.asyncio
async def test_final_review_retriggers_after_new_activity() -> None:
    """Final review job should send a new review when updated_at changed since last review."""
    from src.quality.job import evaluate_mature_conversations_quality

    old_updated_at = datetime.now(tz=UTC) - timedelta(hours=6)
    new_updated_at = datetime.now(tz=UTC) - timedelta(hours=4)
    candidate = _make_candidate(updated_at=new_updated_at, sales_stage="quoting")
    query_db = AsyncMock()
    worker_db = AsyncMock()
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=old_updated_at.isoformat())
    mock_redis.setex = AsyncMock()
    mock_notify = AsyncMock()

    with (
        patch(
            "src.quality.job.async_session_factory",
            side_effect=[_make_session_ctx(query_db), _make_session_ctx(worker_db)],
        ),
        patch(
            "src.quality.job.get_recent_updated_conversation_candidates",
            new=AsyncMock(return_value=[candidate]),
        ),
        patch(
            "src.quality.job.evaluate_conversation",
            new=AsyncMock(return_value=_make_evaluation_result(score=24.0)),
        ),
        patch("src.quality.job.save_review", new=AsyncMock()),
        patch(
            "src.services.notifications.notify_final_quality_review", new=mock_notify
        ),
    ):
        await evaluate_mature_conversations_quality(_ai_quality_ctx(mock_redis))

    mock_notify.assert_awaited_once()
    mock_redis.setex.assert_awaited_once()


@pytest.mark.asyncio
async def test_final_review_skips_telegram_for_missing_inbound_phone() -> None:
    """Final review should persist marker but skip Telegram when inbound is unknown."""
    from src.quality.job import evaluate_mature_conversations_quality

    candidate = _make_candidate(
        status="closed",
        updated_at=datetime.now(tz=UTC) - timedelta(hours=4),
        metadata_={},
    )
    query_db = AsyncMock()
    worker_db = AsyncMock()
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.setex = AsyncMock()
    mock_notify = AsyncMock()
    mock_save = AsyncMock()

    with (
        patch(
            "src.quality.job.async_session_factory",
            side_effect=[_make_session_ctx(query_db), _make_session_ctx(worker_db)],
        ),
        patch(
            "src.quality.job.get_recent_updated_conversation_candidates",
            new=AsyncMock(return_value=[candidate]),
        ),
        patch(
            "src.quality.job.evaluate_conversation",
            new=AsyncMock(return_value=_make_evaluation_result(score=18.0)),
        ),
        patch("src.quality.job.save_review", new=mock_save),
        patch(
            "src.services.notifications.notify_final_quality_review", new=mock_notify
        ),
        patch(
            "src.services.inbound_channels.settings.telegram_allowed_inbound_phone",
            "+971551220665",
        ),
    ):
        await evaluate_mature_conversations_quality(_ai_quality_ctx(mock_redis))

    mock_save.assert_awaited_once()
    mock_notify.assert_not_awaited()
    mock_redis.setex.assert_awaited_once()


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
    assert "Что сделано хорошо" in existing_review.summary
    mock_db.add.assert_not_called()
    mock_db.flush.assert_awaited_once()
