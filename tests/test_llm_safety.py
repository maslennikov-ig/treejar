from __future__ import annotations

import os
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest


class _FakeRunResult:
    output = "ok"

    def usage(self) -> SimpleNamespace:
        return SimpleNamespace(input_tokens=10, output_tokens=5)


@pytest.mark.parametrize(
    ("path", "expected_max_tokens"),
    [
        ("core_chat", 2200),
        ("core_followup", 500),
        ("quality_final", 2500),
        ("quality_red_flags", 900),
        ("quality_manager", 2000),
        ("conversation_summary", 900),
        ("response_adapter", 700),
        ("auto_faq_translate", 700),
    ],
)
def test_llm_path_policy_sets_expected_provider_max_tokens(
    path: str,
    expected_max_tokens: int,
) -> None:
    from src.llm.safety import model_settings_for_path

    assert model_settings_for_path(path)["max_tokens"] == expected_max_tokens


def test_default_model_routing_keeps_glm5_only_for_core_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.core.config import settings
    from src.llm.safety import (
        PATH_AUTO_FAQ_TRANSLATE,
        PATH_CONVERSATION_SUMMARY,
        PATH_CORE_CHAT,
        PATH_CORE_FOLLOWUP,
        PATH_QUALITY_FINAL,
        PATH_QUALITY_MANAGER,
        PATH_QUALITY_RED_FLAGS,
        PATH_RESPONSE_ADAPTER,
        is_glm5_model_name,
        model_name_for_path,
    )

    monkeypatch.setattr(settings, "openrouter_model_main", "z-ai/glm-5-20260211")
    monkeypatch.setattr(settings, "openrouter_model_fast", "xiaomi/mimo-v2-flash")

    assert is_glm5_model_name(model_name_for_path(PATH_CORE_CHAT))
    assert is_glm5_model_name(model_name_for_path(PATH_CORE_FOLLOWUP))
    for path in (
        PATH_QUALITY_FINAL,
        PATH_QUALITY_RED_FLAGS,
        PATH_QUALITY_MANAGER,
        PATH_CONVERSATION_SUMMARY,
        PATH_RESPONSE_ADAPTER,
        PATH_AUTO_FAQ_TRANSLATE,
    ):
        assert model_name_for_path(path) == "xiaomi/mimo-v2-flash"
        assert not is_glm5_model_name(model_name_for_path(path))


def test_openrouter_cache_control_requires_enabled_supported_model() -> None:
    from src.llm.safety import PATH_QUALITY_FINAL, model_settings_for_path

    supported = model_settings_for_path(
        PATH_QUALITY_FINAL,
        model_name="anthropic/claude-sonnet-4.6",
        cache_telemetry_enabled=True,
    )
    assert supported["extra_body"]["usage"] == {"include": True}
    assert supported["extra_body"]["cache_control"] == {"type": "ephemeral"}

    disabled = model_settings_for_path(
        PATH_QUALITY_FINAL,
        model_name="anthropic/claude-sonnet-4.6",
        cache_telemetry_enabled=False,
    )
    assert "extra_body" not in disabled

    unsupported = model_settings_for_path(
        PATH_QUALITY_FINAL,
        model_name="z-ai/glm-5-20260211",
        cache_telemetry_enabled=True,
    )
    assert unsupported["extra_body"]["usage"] == {"include": True}
    assert "cache_control" not in unsupported["extra_body"]


def test_ai_quality_config_import_does_not_require_openrouter_api_key() -> None:
    """Admin config imports must not instantiate OpenRouter providers."""
    env = os.environ.copy()
    env.pop("OPENROUTER_API_KEY", None)

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from src.quality.config import AIQualityControlsConfig;"
                "print(AIQualityControlsConfig().bot_qa.model)"
            ),
        ],
        check=False,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip()


def test_usage_extraction_handles_openrouter_cache_reasoning_and_cost() -> None:
    from src.llm.safety import extract_llm_usage_telemetry

    result = SimpleNamespace(
        usage=lambda: SimpleNamespace(
            prompt_tokens=100,
            completion_tokens=25,
            total_tokens=125,
            prompt_tokens_details={
                "cached_tokens": 60,
                "cache_write_tokens": 40,
            },
            completion_tokens_details={"reasoning_tokens": 7},
            cost=0.0123,
        )
    )

    usage = extract_llm_usage_telemetry(
        path="quality_final",
        model_name="anthropic/claude-sonnet-4.6",
        result=result,
    )

    assert usage.prompt_tokens == 100
    assert usage.completion_tokens == 25
    assert usage.cached_tokens == 60
    assert usage.cache_write_tokens == 40
    assert usage.reasoning_tokens == 7
    assert usage.cost == 0.0123
    assert usage.provider == "openrouter"


def test_usage_extraction_preserves_zero_cache_values() -> None:
    from src.llm.safety import extract_llm_usage_telemetry

    result = SimpleNamespace(
        usage=lambda: {
            "prompt_tokens": 10,
            "completion_tokens": 2,
            "prompt_tokens_details": {
                "cached_tokens": 0,
                "cache_write_tokens": 0,
            },
            "completion_tokens_details": {"reasoning_tokens": 0},
            "cost": 0,
        }
    )

    usage = extract_llm_usage_telemetry(
        path="quality_red_flags",
        model_name="test/model",
        result=result,
    )

    assert usage.cached_tokens == 0
    assert usage.cache_write_tokens == 0
    assert usage.reasoning_tokens == 0
    assert usage.cost == 0.0


@pytest.mark.asyncio
async def test_run_agent_with_safety_passes_non_core_settings_and_limits() -> None:
    from src.llm.safety import run_agent_with_safety

    agent = SimpleNamespace(run=AsyncMock(return_value=_FakeRunResult()))

    await run_agent_with_safety(
        agent,
        "quality_red_flags",
        "prompt",
        model_name="fast-model",
    )

    kwargs = agent.run.await_args.kwargs
    assert kwargs["model_settings"]["max_tokens"] == 900
    assert kwargs["usage_limits"].request_limit == 1
    assert kwargs["usage_limits"].output_tokens_limit == 900
    assert kwargs["usage_limits"].total_tokens_limit == 4000


@pytest.mark.asyncio
async def test_run_agent_with_safety_retries_non_core_once_total() -> None:
    from src.llm.safety import run_agent_with_safety

    agent = SimpleNamespace(
        run=AsyncMock(
            side_effect=[
                httpx.ConnectError("temporary provider failure"),
                _FakeRunResult(),
            ]
        )
    )

    result = await run_agent_with_safety(
        agent,
        "response_adapter",
        "prompt",
        model_name="fast-model",
    )

    assert result.output == "ok"
    assert agent.run.await_count == 2


@pytest.mark.asyncio
async def test_run_agent_with_safety_final_failure_notifies_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.llm import safety

    notify = AsyncMock()
    monkeypatch.setattr(safety, "notify_llm_safety_event", notify)
    agent = SimpleNamespace(
        run=AsyncMock(side_effect=httpx.ConnectError("provider unavailable"))
    )

    with pytest.raises(httpx.ConnectError):
        await safety.run_agent_with_safety(
            agent,
            "conversation_summary",
            "prompt",
            model_name="fast-model",
        )

    assert agent.run.await_count == 2
    notify.assert_awaited_once()
    assert notify.await_args.kwargs["event"] == "final_failure"


@pytest.mark.asyncio
async def test_budget_block_prevents_non_core_provider_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.core.config import settings
    from src.llm import safety

    monkeypatch.setattr(settings, "llm_non_core_budget_blocked", True)
    notify = AsyncMock()
    monkeypatch.setattr(safety, "notify_llm_safety_event", notify)
    agent = SimpleNamespace(run=AsyncMock(return_value=_FakeRunResult()))

    with pytest.raises(safety.LLMBudgetBlocked):
        await safety.run_agent_with_safety(
            agent,
            "quality_final",
            "prompt",
            model_name="main-model",
        )

    agent.run.assert_not_awaited()
    notify.assert_awaited_once()
    assert notify.await_args.kwargs["event"] == "budget_blocked"


@pytest.mark.asyncio
async def test_core_path_does_not_get_outer_retry_or_budget_block(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.core.config import settings
    from src.llm import safety

    monkeypatch.setattr(settings, "llm_non_core_budget_blocked", True)
    notify = AsyncMock()
    monkeypatch.setattr(safety, "notify_llm_safety_event", notify)
    agent = SimpleNamespace(run=AsyncMock(side_effect=RuntimeError("core failure")))

    with pytest.raises(RuntimeError, match="core failure"):
        await safety.run_agent_with_safety(
            agent,
            "core_chat",
            "prompt",
            model_name="main-model",
        )

    assert agent.run.await_count == 1
    kwargs = agent.run.await_args.kwargs
    assert kwargs["model_settings"]["max_tokens"] == 2200
    assert "usage_limits" not in kwargs
    notify.assert_awaited_once()
