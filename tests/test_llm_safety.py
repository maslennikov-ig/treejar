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
        ("quality_final", 8000),
        ("quality_red_flags", 900),
        ("quality_manager", 2000),
        ("conversation_summary", 900),
        ("fact_extraction", 700),
        ("voice_transcription", 700),
        ("response_adapter", 700),
        ("auto_faq_translate", 700),
        ("auto_faq_candidate", 900),
    ],
)
def test_llm_path_policy_sets_expected_provider_max_tokens(
    path: str,
    expected_max_tokens: int,
) -> None:
    from src.llm.safety import model_settings_for_path

    assert model_settings_for_path(path)["max_tokens"] == expected_max_tokens


def test_default_model_routing_uses_glm52_for_core_and_v4_flash_for_helpers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.core.config import settings
    from src.llm.safety import (
        PATH_AUTO_FAQ_CANDIDATE,
        PATH_AUTO_FAQ_TRANSLATE,
        PATH_CONVERSATION_SUMMARY,
        PATH_CORE_CHAT,
        PATH_CORE_FOLLOWUP,
        PATH_FACT_EXTRACTION,
        PATH_QUALITY_FINAL,
        PATH_QUALITY_MANAGER,
        PATH_QUALITY_RED_FLAGS,
        PATH_RESPONSE_ADAPTER,
        is_glm5_model_name,
        model_name_for_path,
    )

    monkeypatch.setattr(settings, "openrouter_model_main", "z-ai/glm-5.2")
    monkeypatch.setattr(
        settings,
        "openrouter_model_fast",
        "deepseek/deepseek-v4-flash",
    )

    assert is_glm5_model_name(model_name_for_path(PATH_CORE_CHAT))
    assert is_glm5_model_name(model_name_for_path(PATH_CORE_FOLLOWUP))
    for path in (
        PATH_QUALITY_FINAL,
        PATH_QUALITY_RED_FLAGS,
        PATH_QUALITY_MANAGER,
        PATH_CONVERSATION_SUMMARY,
        PATH_FACT_EXTRACTION,
        PATH_RESPONSE_ADAPTER,
        PATH_AUTO_FAQ_TRANSLATE,
        PATH_AUTO_FAQ_CANDIDATE,
    ):
        assert model_name_for_path(path) == "deepseek/deepseek-v4-flash"
        assert not is_glm5_model_name(model_name_for_path(path))


def test_v4_flash_disables_reasoning_without_affecting_other_models_or_providers() -> (
    None
):
    from src.llm.safety import PATH_QUALITY_FINAL, model_settings_for_path

    v4_flash = model_settings_for_path(
        PATH_QUALITY_FINAL,
        model_name="deepseek/deepseek-v4-flash",
    )
    assert v4_flash["extra_body"]["reasoning"] == {"enabled": False}

    glm = model_settings_for_path(
        PATH_QUALITY_FINAL,
        model_name="z-ai/glm-5.2",
    )
    assert "reasoning" not in glm["extra_body"]

    other_provider = model_settings_for_path(
        PATH_QUALITY_FINAL,
        model_name="deepseek/deepseek-v4-flash",
        provider="other",
    )
    assert "extra_body" not in other_provider


def test_fact_extraction_route_uses_central_v4_flash_safety_settings() -> None:
    from src.llm.safety import PATH_FACT_EXTRACTION, model_settings_for_path

    model_settings = model_settings_for_path(
        PATH_FACT_EXTRACTION,
        model_name="deepseek/deepseek-v4-flash",
    )

    assert model_settings["max_tokens"] == 700
    assert model_settings["timeout"] == 30.0
    assert model_settings["extra_body"]["reasoning"] == {"enabled": False}


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


def test_voice_transcription_policy_is_non_core_and_bounded() -> None:
    from src.llm.safety import (
        PATH_VOICE_TRANSCRIPTION,
        policy_for_path,
        usage_limits_for_path,
    )

    policy = policy_for_path(PATH_VOICE_TRANSCRIPTION)
    limits = usage_limits_for_path(PATH_VOICE_TRANSCRIPTION)

    assert policy.scope == "non_core"
    assert policy.max_tokens == 700
    assert policy.timeout_seconds == 45.0
    assert limits is not None
    assert limits.request_limit == 1
    assert limits.output_tokens_limit == 700
    assert limits.total_tokens_limit == 4000


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


def test_openrouter_chat_model_preserves_provider_reported_cost() -> None:
    from openai.types.chat import ChatCompletion
    from pydantic_ai.providers.openrouter import OpenRouterProvider

    from src.llm.safety import OpenRouterTelemetryChatModel

    model = OpenRouterTelemetryChatModel(
        "z-ai/glm-5.2",
        provider=OpenRouterProvider(api_key="test-key"),
    )
    response = ChatCompletion.model_validate(
        {
            "id": "generation-test",
            "choices": [
                {
                    "finish_reason": "stop",
                    "index": 0,
                    "message": {"content": "ok", "role": "assistant"},
                }
            ],
            "created": 1,
            "model": "z-ai/glm-5.2",
            "object": "chat.completion",
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
                "cost": 0.00125,
            },
        }
    )

    details = model._process_provider_details(response)

    assert details["usage_cost_usd"] == 0.00125
    assert model.provider_cost_snapshot() == 0.00125
    result = SimpleNamespace(
        usage=lambda: SimpleNamespace(input_tokens=10, output_tokens=5),
        new_messages=lambda: [
            SimpleNamespace(provider_details=details),
            SimpleNamespace(provider_details={"usage_cost_usd": 0.0005}),
        ],
    )
    from src.llm.safety import extract_llm_usage_telemetry

    telemetry = extract_llm_usage_telemetry(
        path="core_chat",
        model_name="z-ai/glm-5.2",
        result=result,
    )
    assert telemetry.cost == 0.00175


@pytest.mark.asyncio
async def test_openrouter_chat_model_retries_temporary_finish_error_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from openai.types.chat import ChatCompletion
    from openai.types.chat.chat_completion import Choice
    from openai.types.chat.chat_completion_message import ChatCompletionMessage
    from openai.types.completion_usage import CompletionUsage
    from pydantic_ai.models import ModelRequestParameters
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.openrouter import OpenRouterProvider

    from src.llm.safety import OpenRouterTelemetryChatModel

    error_choice = Choice.model_construct(
        finish_reason="error",
        index=0,
        message=ChatCompletionMessage.model_construct(
            role="assistant",
            content="",
        ),
    )
    error_choice.__pydantic_extra__ = {
        "error": {
            "code": 503,
            "message": "provider overloaded",
            "metadata": {"error_type": "provider_overloaded"},
        }
    }
    error_response = ChatCompletion.model_construct(
        id="generation-error",
        choices=[error_choice],
        created=1,
        model="z-ai/glm-5.2",
        object="chat.completion",
        usage=CompletionUsage.model_validate(
            {
                "prompt_tokens": 10,
                "completion_tokens": 0,
                "total_tokens": 10,
                "cost": 0.001,
            }
        ),
    )
    success_response = ChatCompletion.model_validate(
        {
            "id": "generation-success",
            "choices": [
                {
                    "finish_reason": "stop",
                    "index": 0,
                    "message": {"content": "ok", "role": "assistant"},
                }
            ],
            "created": 2,
            "model": "z-ai/glm-5.2",
            "object": "chat.completion",
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 2,
                "total_tokens": 12,
                "cost": 0.002,
            },
        }
    )
    responses = iter((error_response, success_response))
    calls = 0

    async def fake_create(*args: object, **kwargs: object) -> ChatCompletion:
        nonlocal calls
        calls += 1
        return next(responses)

    monkeypatch.setattr(OpenAIChatModel, "_completions_create", fake_create)
    model = OpenRouterTelemetryChatModel(
        "z-ai/glm-5.2",
        provider=OpenRouterProvider(api_key="test-key"),
    )

    response = await model._completions_create(
        [],
        False,
        {},
        ModelRequestParameters(),
    )

    assert response is success_response
    assert calls == 2
    details = model._process_provider_details(response)
    assert details["openrouter_error_retries"] == 1
    assert details["openrouter_error_type"] == "provider_overloaded"
    assert details["usage_cost_usd"] == pytest.approx(0.003)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error_type",
    ["invalid_request", "provider_unavailable"],
)
async def test_openrouter_chat_model_never_hides_unrecoverable_finish_error(
    monkeypatch: pytest.MonkeyPatch,
    error_type: str,
) -> None:
    from openai.types.chat import ChatCompletion
    from openai.types.chat.chat_completion import Choice
    from openai.types.chat.chat_completion_message import ChatCompletionMessage
    from pydantic_ai.exceptions import ModelAPIError
    from pydantic_ai.models import ModelRequestParameters
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.openrouter import OpenRouterProvider

    from src.llm.safety import (
        OpenRouterTelemetryChatModel,
        run_agent_with_safety,
    )

    choice = Choice.model_construct(
        finish_reason="error",
        index=0,
        message=ChatCompletionMessage.model_construct(
            role="assistant",
            content="",
        ),
    )
    choice.__pydantic_extra__ = {
        "error": {
            "code": 502,
            "message": "provider failure",
            "metadata": {"error_type": error_type},
        }
    }
    error_response = ChatCompletion.model_construct(
        id="generation-error",
        choices=[choice],
        created=1,
        model="z-ai/glm-5.2",
        object="chat.completion",
    )
    calls = 0

    async def fake_create(*args: object, **kwargs: object) -> ChatCompletion:
        nonlocal calls
        calls += 1
        return error_response

    monkeypatch.setattr(OpenAIChatModel, "_completions_create", fake_create)
    model = OpenRouterTelemetryChatModel(
        "z-ai/glm-5.2",
        provider=OpenRouterProvider(api_key="test-key"),
    )
    agent_calls = 0

    class FailingAgent:
        async def run(self, user_prompt: object, **kwargs: object) -> object:
            nonlocal agent_calls
            del user_prompt, kwargs
            agent_calls += 1
            return await model._completions_create(
                [],
                False,
                {},
                ModelRequestParameters(),
            )

    with pytest.raises(ModelAPIError, match=error_type):
        await run_agent_with_safety(
            FailingAgent(),
            "response_adapter",
            "test prompt",
            model_name="z-ai/glm-5.2",
            notify_on_failure_override=False,
        )

    expected_calls = 1 if error_type == "invalid_request" else 2
    assert calls == expected_calls
    assert agent_calls == 1


@pytest.mark.asyncio
async def test_run_agent_with_safety_passes_non_core_settings_and_limits() -> None:
    from src.llm.safety import get_llm_usage_telemetry, run_agent_with_safety

    result = SimpleNamespace(
        output="ok",
        usage=lambda: SimpleNamespace(
            input_tokens=10,
            output_tokens=5,
            cost=0.00125,
        ),
    )
    agent = SimpleNamespace(run=AsyncMock(return_value=result))

    returned = await run_agent_with_safety(
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
    telemetry = get_llm_usage_telemetry(returned)
    assert telemetry is not None
    assert telemetry.cost == 0.00125


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
async def test_auto_faq_translate_final_failure_does_not_notify(
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
            "auto_faq_translate",
            "prompt",
            model_name="fast-model",
        )

    assert agent.run.await_count == 2
    notify.assert_not_awaited()


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


def test_a_full_evaluation_fits_inside_the_quality_final_ceiling() -> None:
    """The ceiling that truncated three of ten acceptance evaluations.

    A full review is fifteen criteria, each with a Russian comment and quoted
    evidence, plus summary, strengths, weaknesses and recommendations. The
    largest one observed on 2026-08-07 was 10307 characters of mostly Cyrillic;
    at roughly two characters per token that is over 5000 output tokens. The old
    ceiling of 2500 cut the JSON mid-string, and `retries=0` turned that into a
    Telegram alert instead of a quality review.
    """
    from src.llm.safety import PATH_QUALITY_FINAL, policy_for_path

    policy = policy_for_path(PATH_QUALITY_FINAL)

    assert policy.max_tokens >= 6000
    assert policy.output_tokens_limit == policy.max_tokens
    assert policy.total_tokens_limit >= 3 * policy.max_tokens


def test_the_quality_evaluators_do_not_narrow_their_own_path_limits() -> None:
    """Raising a policy must be enough to raise the effective limit.

    Both evaluators used to repeat their path's token limits verbatim at the
    call site, and `_merge_usage_limits` takes the minimum of the two. Raising
    the policy alone therefore changed nothing, which is what made the
    truncation look unfixable. The numbers now live in one place.
    """
    import pathlib

    for module in ("src/quality/evaluator.py", "src/quality/manager_evaluator.py"):
        source = pathlib.Path(module).read_text(encoding="utf-8")
        assert "UsageLimits(" not in source, module


def test_omitting_usage_limits_yields_exactly_the_path_policy() -> None:
    """Which is why the call sites can drop them rather than restate them."""
    from src.llm.safety import (
        PATH_QUALITY_FINAL,
        _merge_usage_limits,
        policy_for_path,
    )

    policy = policy_for_path(PATH_QUALITY_FINAL)
    merged = _merge_usage_limits(PATH_QUALITY_FINAL, None)

    assert merged is not None
    assert merged.output_tokens_limit == policy.output_tokens_limit
    assert merged.total_tokens_limit == policy.total_tokens_limit
    assert merged.request_limit == policy.request_limit
