"""tj-ierv.2: AI Quality Controls criteria, budget, retry and manual wiring."""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from src.llm.safety import LLMUsageTelemetry, attach_llm_usage_telemetry
from src.quality.config import (
    DEFAULT_SCOPE_CRITERIA,
    AIQualityControlsConfig,
    AIQualityControlsUpdate,
    AIQualityScope,
    ai_quality_call_cost_cents,
    ai_quality_evaluator_kwargs,
    evaluate_ai_quality_run_gate,
    get_ai_quality_usage_today,
    merge_ai_quality_controls_update,
    parse_ai_quality_controls,
    record_ai_quality_spend_from_ctx,
    reserve_ai_quality_daily_call,
)


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, int] = {}

    async def get(self, key: str) -> str | None:
        value = self.values.get(key)
        return None if value is None else str(value)

    async def incr(self, key: str) -> int:
        self.values[key] = self.values.get(key, 0) + 1
        return self.values[key]

    async def hget(self, key: str, field: str) -> str | None:
        return await self.get(f"{key}#{field}")

    async def hincrby(self, key: str, field: str, amount: int) -> int:
        composite = f"{key}#{field}"
        self.values[composite] = self.values.get(composite, 0) + amount
        return self.values[composite]

    async def decr(self, key: str) -> int:
        self.values[key] = self.values.get(key, 0) - 1
        return self.values[key]

    async def expire(self, key: str, ttl: int) -> bool:
        return True


def _manual_config(**scope_overrides: Any) -> AIQualityControlsConfig:
    scope = {"mode": "manual", **scope_overrides}
    return parse_ai_quality_controls(
        {"bot_qa": scope, "manager_qa": scope, "red_flags": scope}
    )


def _usage(cost: float | None) -> LLMUsageTelemetry:
    return LLMUsageTelemetry(
        path="quality_final", model="m", provider="openrouter", cost=cost
    )


# --------------------------------------------------------------------------
# Criteria defaults
# --------------------------------------------------------------------------


def test_default_config_exposes_criteria_for_every_scope() -> None:
    config = AIQualityControlsConfig()

    assert config.bot_qa.criteria == DEFAULT_SCOPE_CRITERIA[AIQualityScope.BOT_QA]
    assert set(config.manager_qa.criteria) == {
        "response_speed_sla",
        "handover_context_usage",
        "professional_tone",
        "commercial_terms_accuracy",
        "closing_and_crm_hygiene",
    }
    assert set(config.red_flags.criteria) == {
        "missing_identity",
        "hard_deflection",
        "unverified_commitment",
        "ignored_question",
        "bad_tone",
    }
    assert all(config.bot_qa.criteria.values())


def test_stored_empty_criteria_are_backfilled_and_overrides_preserved() -> None:
    config = parse_ai_quality_controls(
        {
            "bot_qa": {"criteria": {}},
            "red_flags": {"criteria": {"bad_tone": False, "custom_flag": True}},
        }
    )

    assert config.bot_qa.criteria == DEFAULT_SCOPE_CRITERIA[AIQualityScope.BOT_QA]
    assert config.red_flags.criteria["bad_tone"] is False
    assert config.red_flags.criteria["custom_flag"] is True
    assert config.red_flags.criteria["missing_identity"] is True


def test_patch_can_switch_a_criterion_off() -> None:
    merged = merge_ai_quality_controls_update(
        AIQualityControlsConfig(),
        AIQualityControlsUpdate.model_validate(
            {"bot_qa": {"criteria": {"tone_and_language": False}}}
        ),
    )

    assert merged.bot_qa.criteria["tone_and_language"] is False
    assert merged.bot_qa.criteria["greeting_and_identity"] is True


def test_gate_carries_criteria_retry_alert_and_budget() -> None:
    config = _manual_config(
        daily_budget_cents=250,
        alert_on_failure=False,
        retry={"max_attempts": 1, "backoff_seconds": 5},
        criteria={"tone_and_language": False},
    )
    gate = evaluate_ai_quality_run_gate(
        config, scope=AIQualityScope.BOT_QA, trigger="manual"
    )

    assert gate.allowed
    assert gate.daily_budget_cents == 250
    assert gate.criteria["tone_and_language"] is False
    kwargs = ai_quality_evaluator_kwargs(gate)
    assert kwargs == {
        "criteria": gate.criteria,
        "max_attempts": 1,
        "alert_on_failure": False,
        "retry_backoff_seconds": 5.0,
    }


# --------------------------------------------------------------------------
# Budget and call quota
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_daily_call_quota_and_budget_are_enforced() -> None:
    redis = FakeRedis()
    config = _manual_config(max_calls_per_run=1, max_calls_per_day=2)
    gate = evaluate_ai_quality_run_gate(
        config, scope=AIQualityScope.BOT_QA, trigger="manual"
    )
    ctx = {"redis": redis}

    assert await reserve_ai_quality_daily_call(ctx, gate) is None
    assert await reserve_ai_quality_daily_call(ctx, gate) is None
    assert (
        await reserve_ai_quality_daily_call(ctx, gate) == "daily_call_quota_exhausted"
    )

    budget_gate = gate.model_copy(
        update={"daily_budget_cents": 3, "max_calls_per_day": 50}
    )
    output = attach_llm_usage_telemetry(MagicMock(), _usage(0.035))
    recorded = await record_ai_quality_spend_from_ctx(ctx, budget_gate, output)
    assert recorded == pytest.approx(3.5)
    assert (
        await reserve_ai_quality_daily_call(ctx, budget_gate)
        == "daily_budget_exhausted"
    )


@pytest.mark.asyncio
async def test_reserve_without_redis_fails_closed_unless_manual() -> None:
    gate = evaluate_ai_quality_run_gate(
        _manual_config(), scope=AIQualityScope.BOT_QA, trigger="manual"
    )

    class NoRedisCtx(dict[str, Any]):
        pass

    import src.quality.config as config_module

    original = config_module.get_redis_client
    config_module.get_redis_client = lambda: None  # type: ignore[assignment]
    try:
        assert await reserve_ai_quality_daily_call(NoRedisCtx(), gate) == (
            "quota_redis_unavailable"
        )
        assert (
            await reserve_ai_quality_daily_call(
                NoRedisCtx(), gate, fail_open_without_redis=True
            )
            is None
        )
    finally:
        config_module.get_redis_client = original  # type: ignore[assignment]


def test_call_cost_uses_telemetry_estimate_or_zero() -> None:
    assert ai_quality_call_cost_cents(object()) == 0.0
    estimated = attach_llm_usage_telemetry(MagicMock(), _usage(None))
    assert ai_quality_call_cost_cents(estimated) == pytest.approx(2.0)
    exact = attach_llm_usage_telemetry(MagicMock(), _usage(0.0114))
    assert ai_quality_call_cost_cents(exact) == pytest.approx(1.14)


@pytest.mark.asyncio
async def test_usage_today_reports_calls_and_spend() -> None:
    redis = FakeRedis()
    config = _manual_config(max_calls_per_day=5, daily_budget_cents=100)
    gate = evaluate_ai_quality_run_gate(
        config, scope=AIQualityScope.MANAGER_QA, trigger="manual"
    )
    await reserve_ai_quality_daily_call({"redis": redis}, gate)
    await record_ai_quality_spend_from_ctx(
        {"redis": redis},
        gate,
        attach_llm_usage_telemetry(MagicMock(), _usage(0.01)),
    )

    usage = await get_ai_quality_usage_today(config, redis=redis)

    assert usage["manager_qa"].calls_today == 1
    assert usage["manager_qa"].spend_cents_today == pytest.approx(1.0)
    assert usage["manager_qa"].daily_budget_cents == 100
    assert usage["bot_qa"].calls_today == 0


# --------------------------------------------------------------------------
# Evaluators honour criteria
# --------------------------------------------------------------------------


def test_manager_total_is_rescaled_without_disabled_criteria() -> None:
    from src.quality.manager_evaluator import manager_total_score
    from src.quality.manager_schemas import ManagerCriterionScore

    criteria = [
        ManagerCriterionScore(rule_number=n, rule_name=f"r{n}", score=2, comment="")
        for n in range(1, 11)
    ]
    criteria[0] = ManagerCriterionScore(
        rule_number=1, rule_name="r1", score=0, comment=""
    )

    assert manager_total_score(criteria) == 18.0
    assert manager_total_score(criteria, frozenset({1})) == 20.0


@pytest.mark.asyncio
async def test_red_flag_evaluator_skips_llm_when_all_codes_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.quality import evaluator

    run_agent = AsyncMock()
    monkeypatch.setattr(evaluator, "run_agent_with_safety", run_agent)

    result = await evaluator.evaluate_red_flags(
        uuid.uuid4(),
        MagicMock(),
        criteria=dict.fromkeys(DEFAULT_SCOPE_CRITERIA[AIQualityScope.RED_FLAGS], False),
    )

    assert result.flags == []
    assert result.recommended_action == evaluator.ALL_REDFLAGS_DISABLED_ACTION
    run_agent.assert_not_awaited()


@pytest.mark.asyncio
async def test_red_flag_evaluator_filters_disabled_codes_and_passes_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.quality import evaluator
    from src.quality.schemas import RedFlagEvaluationResult

    message = MagicMock(role="assistant", content="Hi", created_at=None)
    monkeypatch.setattr(evaluator, "_load_messages", AsyncMock(return_value=[message]))
    monkeypatch.setattr(evaluator, "_load_summary_text", AsyncMock(return_value=None))
    context = MagicMock(insufficient_evidence=False, prompt="DIALOGUE")
    monkeypatch.setattr(
        evaluator, "build_review_transcript_context", lambda *a, **k: context
    )
    output = RedFlagEvaluationResult.model_validate(
        {
            "flags": [
                {"code": "bad_tone", "title": "t", "explanation": "e"},
                {"code": "ignored_question", "title": "t", "explanation": "e"},
            ],
            "recommended_action": "Follow up",
        }
    )
    run_result = MagicMock(output=output)
    run_result.usage.return_value = None
    run_agent = AsyncMock(return_value=run_result)
    monkeypatch.setattr(evaluator, "run_agent_with_safety", run_agent)

    result = await evaluator.evaluate_red_flags(
        uuid.uuid4(),
        MagicMock(),
        criteria={"bad_tone": False},
        max_attempts=1,
        alert_on_failure=False,
        retry_backoff_seconds=3.0,
    )

    assert [flag.code for flag in result.flags] == ["ignored_question"]
    kwargs = run_agent.await_args.kwargs
    assert kwargs["max_attempts_override"] == 1
    assert kwargs["notify_on_failure_override"] is False
    assert kwargs["retry_backoff_seconds"] == 3.0
    assert "bad_tone" in run_agent.await_args.args[2]


# --------------------------------------------------------------------------
# Manual triggers use the configured settings
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_manual_bot_review_passes_gate_settings_to_evaluator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.services import admin_crm

    config = _manual_config(
        transcript_mode="disabled",
        cache_telemetry_enabled=False,
        criteria={"tone_and_language": False},
        alert_on_failure=False,
    )
    monkeypatch.setattr(
        admin_crm, "get_ai_quality_controls_config", AsyncMock(return_value=config)
    )
    monkeypatch.setattr(
        admin_crm, "conversation_already_reviewed", AsyncMock(return_value=False)
    )
    reserve = AsyncMock(return_value=None)
    monkeypatch.setattr(admin_crm, "reserve_ai_quality_daily_call", reserve)
    spend = AsyncMock(return_value=0.0)
    monkeypatch.setattr(admin_crm, "record_ai_quality_spend_from_ctx", spend)
    evaluation = MagicMock()
    evaluate = AsyncMock(return_value=evaluation)
    monkeypatch.setattr(admin_crm, "evaluate_conversation", evaluate)
    review = MagicMock(id=uuid.uuid4(), rating="good")
    monkeypatch.setattr(admin_crm, "save_review", AsyncMock(return_value=review))
    monkeypatch.setattr(admin_crm, "log_admin_action", AsyncMock())
    db = MagicMock()
    db.commit = AsyncMock()

    result = await admin_crm.run_admin_bot_quality_review(
        db, conversation_id=uuid.uuid4(), request=None
    )

    assert result.ok
    kwargs = evaluate.await_args.kwargs
    assert kwargs["model_name"] == config.bot_qa.model
    assert kwargs["transcript_mode"] == "disabled"
    assert kwargs["cache_telemetry_enabled"] is False
    assert kwargs["criteria"]["tone_and_language"] is False
    assert kwargs["alert_on_failure"] is False
    assert kwargs["max_attempts"] == config.bot_qa.retry.max_attempts
    reserve.assert_awaited_once()
    assert spend.await_args.args[2] is evaluation


@pytest.mark.asyncio
async def test_manual_review_blocked_by_daily_budget_returns_409(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.services import admin_crm

    monkeypatch.setattr(
        admin_crm,
        "get_ai_quality_controls_config",
        AsyncMock(return_value=_manual_config()),
    )
    monkeypatch.setattr(
        admin_crm, "conversation_already_reviewed", AsyncMock(return_value=False)
    )
    monkeypatch.setattr(
        admin_crm,
        "reserve_ai_quality_daily_call",
        AsyncMock(return_value="daily_budget_exhausted"),
    )
    evaluate = AsyncMock()
    monkeypatch.setattr(admin_crm, "evaluate_conversation", evaluate)

    with pytest.raises(HTTPException) as exc_info:
        await admin_crm.run_admin_bot_quality_review(
            MagicMock(), conversation_id=uuid.uuid4(), request=None
        )

    assert exc_info.value.status_code == 409
    assert "daily_budget_exhausted" in str(exc_info.value.detail)
    evaluate.assert_not_awaited()


@pytest.mark.asyncio
async def test_admin_manager_review_endpoint_uses_gate_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.api.v1 import admin

    config = _manual_config(model="deepseek/deepseek-v4-flash")
    gate = evaluate_ai_quality_run_gate(
        config, scope=AIQualityScope.MANAGER_QA, trigger="manual"
    )
    monkeypatch.setattr(
        admin, "require_admin_ai_quality_manual_gate", AsyncMock(return_value=gate)
    )
    captured: dict[str, Any] = {}

    async def fake_evaluate(escalation_id: uuid.UUID, db: Any, **kwargs: Any) -> str:
        captured.update(kwargs)
        return "review"

    monkeypatch.setattr(admin, "evaluate_escalation_with_settings", fake_evaluate)

    result = await admin.evaluate_admin_manager_review(uuid.uuid4(), MagicMock())

    assert result == "review"
    assert captured["evaluator_kwargs"]["model_name"] == "deepseek/deepseek-v4-flash"
    assert "criteria" in captured["evaluator_kwargs"]
    assert callable(captured["before_llm_call"])
    assert callable(captured["after_llm_call"])
