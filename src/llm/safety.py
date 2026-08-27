"""Central safety policy for PydanticAI LLM calls."""

from __future__ import annotations

import asyncio
import logging
import math
from collections.abc import Mapping
from dataclasses import dataclass
from html import escape
from typing import Any, Literal, cast, overload

import httpx
from openai import AsyncStream
from openai.types.chat import ChatCompletion, ChatCompletionChunk
from pydantic_ai import ModelSettings, UsageLimits
from pydantic_ai.exceptions import (
    ModelAPIError,
    ModelHTTPError,
    UnexpectedModelBehavior,
)
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models import ModelRequestParameters
from pydantic_ai.models.openai import (
    OpenAIChatModel,
    OpenAIChatModelSettings,
)

from src.core.config import settings

logger = logging.getLogger(__name__)

LLMScope = Literal["core", "non_core"]

PATH_CORE_CHAT = "core_chat"
PATH_CORE_FOLLOWUP = "core_followup"
PATH_QUALITY_FINAL = "quality_final"
PATH_QUALITY_RED_FLAGS = "quality_red_flags"
PATH_QUALITY_MANAGER = "quality_manager"
PATH_CONVERSATION_SUMMARY = "conversation_summary"
PATH_FACT_EXTRACTION = "fact_extraction"
PATH_VOICE_TRANSCRIPTION = "voice_transcription"
PATH_RESPONSE_ADAPTER = "response_adapter"
PATH_RESPONSE_REPAIR_JUDGE = "response_repair_judge"
PATH_AUTO_FAQ_TRANSLATE = "auto_faq_translate"
PATH_AUTO_FAQ_CANDIDATE = "auto_faq_candidate"
OPENROUTER_PROVIDER_NAME = "openrouter"
LLM_USAGE_TELEMETRY_ATTR = "__treejar_llm_usage_telemetry__"
_OPENROUTER_CACHE_CONTROL_SUPPORTED_MODEL_PREFIXES = ("anthropic/",)
_OPENROUTER_REASONING_DISABLED_MODEL_IDS = frozenset({"deepseek/deepseek-v4-flash"})
_OPENROUTER_LOW_REASONING_EFFORT_CORE_MODEL_IDS = frozenset({"z-ai/glm-5.3-flash"})
_OPENROUTER_RETRYABLE_ERROR_TYPES = frozenset(
    {
        "rate_limit_exceeded",
        "provider_overloaded",
        "provider_unavailable",
        "timeout",
        "server",
    }
)
_OPENROUTER_RETRY_COUNT_ATTR = "treejar_openrouter_error_retries"
_OPENROUTER_RETRY_COST_ATTR = "treejar_openrouter_retry_cost_usd"
_OPENROUTER_RETRY_TYPE_ATTR = "treejar_openrouter_error_type"


class LLMBudgetBlocked(RuntimeError):
    """Raised when configured budget controls block a non-core LLM path."""


class OpenRouterCompletionError(ModelAPIError):
    """Terminal in-band OpenRouter error after provider-boundary handling."""


class OpenRouterTelemetryChatModel(OpenAIChatModel):
    """Preserve OpenRouter's provider-reported cost on the model response."""

    @overload
    async def _completions_create(
        self,
        messages: list[ModelMessage],
        stream: Literal[True],
        model_settings: OpenAIChatModelSettings,
        model_request_parameters: ModelRequestParameters,
    ) -> AsyncStream[ChatCompletionChunk]: ...

    @overload
    async def _completions_create(
        self,
        messages: list[ModelMessage],
        stream: Literal[False],
        model_settings: OpenAIChatModelSettings,
        model_request_parameters: ModelRequestParameters,
    ) -> ChatCompletion: ...

    async def _completions_create(
        self,
        messages: list[ModelMessage],
        stream: bool,
        model_settings: OpenAIChatModelSettings,
        model_request_parameters: ModelRequestParameters,
    ) -> ChatCompletion | AsyncStream[ChatCompletionChunk]:
        if stream:
            return await super()._completions_create(
                messages,
                True,
                model_settings,
                model_request_parameters,
            )

        response = await super()._completions_create(
            messages,
            False,
            model_settings,
            model_request_parameters,
        )
        if not _openrouter_completion_failed(response):
            return response

        error_type = _openrouter_completion_error_type(response)
        retrying = error_type in _OPENROUTER_RETRYABLE_ERROR_TYPES
        logger.warning(
            "openrouter.finish_reason_error",
            extra={
                "model": self.model_name,
                "error_type": error_type or "unknown",
                "retrying": retrying,
            },
        )
        if not retrying:
            raise _openrouter_completion_error(self.model_name, error_type)

        retry_response = await super()._completions_create(
            messages,
            False,
            model_settings,
            model_request_parameters,
        )
        if _openrouter_completion_failed(retry_response):
            retry_error_type = _openrouter_completion_error_type(retry_response)
            raise _openrouter_completion_error(self.model_name, retry_error_type)

        setattr(retry_response, _OPENROUTER_RETRY_COUNT_ATTR, 1)
        setattr(retry_response, _OPENROUTER_RETRY_TYPE_ATTR, error_type)
        retry_cost = _usage_number(
            getattr(response, "usage", None),
            "cost",
            "cost_usd",
        )
        valid_retry_cost = _valid_cost(retry_cost)
        if valid_retry_cost is not None:
            setattr(
                retry_response,
                _OPENROUTER_RETRY_COST_ATTR,
                valid_retry_cost,
            )
        return retry_response

    def _process_provider_details(self, response: Any) -> dict[str, Any]:
        details = super()._process_provider_details(response)
        cost = _usage_number(getattr(response, "usage", None), "cost", "cost_usd")
        retry_cost = _usage_number(response, _OPENROUTER_RETRY_COST_ATTR)
        valid_costs = [
            valid
            for value in (cost, retry_cost)
            if (valid := _valid_cost(value)) is not None
        ]
        if valid_costs:
            response_cost = sum(valid_costs)
            details["usage_cost_usd"] = response_cost
            prior_cost = self.provider_cost_snapshot() or 0.0
            self._treejar_provider_cost_usd = prior_cost + response_cost

        retry_count = _usage_number(response, _OPENROUTER_RETRY_COUNT_ATTR)
        if isinstance(retry_count, int) and retry_count > 0:
            details["openrouter_error_retries"] = retry_count
            error_type = getattr(response, _OPENROUTER_RETRY_TYPE_ATTR, None)
            if isinstance(error_type, str) and error_type:
                details["openrouter_error_type"] = error_type
        return details

    def provider_cost_snapshot(self) -> float | None:
        """Return cost reported by provider responses processed in this run."""
        return _valid_cost(getattr(self, "_treejar_provider_cost_usd", None))


@dataclass(frozen=True, slots=True)
class LLMPathPolicy:
    path: str
    scope: LLMScope
    max_tokens: int
    timeout_seconds: float
    output_tokens_limit: int | None = None
    total_tokens_limit: int | None = None
    request_limit: int | None = None
    max_attempts: int = 1
    notify_on_failure: bool = True
    notify_on_budget_block: bool = True
    # None leaves the provider default in place. A path that scores rather than
    # writes should pin this: sampling noise in a judge is measurement error,
    # and it is indistinguishable from the code movement the judge is there to
    # detect.
    temperature: float | None = None
    # None leaves the provider default. Set it False where the path has a small
    # token budget and a structured answer: on a reasoning model the thinking
    # is drawn from the same `max_tokens`, so it can starve the output the
    # schema requires and the call fails with nothing to show for the spend.
    # This belongs to the path rather than the model id -- the same vendor can
    # be worth thinking on one job and not another.
    #
    # It is a request, not a guarantee. Asking `z-ai/glm-5.2` to stop thinking
    # was measured on 2026-08-12 and it does not: `enabled: false`,
    # `effort: low` and `max_tokens: 256` all left completion at ~1430 tokens.
    # Where thinking cannot be declined it has to be afforded, so a path that
    # sets this must still budget as though it were ignored.
    reasoning_enabled: bool | None = None


_POLICIES: dict[str, LLMPathPolicy] = {
    PATH_CORE_CHAT: LLMPathPolicy(
        path=PATH_CORE_CHAT,
        scope="core",
        max_tokens=2200,
        timeout_seconds=90.0,
    ),
    PATH_CORE_FOLLOWUP: LLMPathPolicy(
        path=PATH_CORE_FOLLOWUP,
        scope="core",
        max_tokens=500,
        timeout_seconds=45.0,
    ),
    PATH_QUALITY_FINAL: LLMPathPolicy(
        path=PATH_QUALITY_FINAL,
        # A full evaluation is fifteen criteria, each with a Russian comment and
        # quoted evidence, plus a summary, strengths, weaknesses and
        # recommendations. That does not fit in 2500 output tokens: the JSON was
        # cut mid-string, `retries=0` made it terminal, and the manager got a
        # Telegram alert instead of a quality review. Three of the ten
        # acceptance conversations died this way on 2026-08-07.
        scope="non_core",
        max_tokens=8000,
        timeout_seconds=60.0,
        output_tokens_limit=8000,
        total_tokens_limit=24000,
        request_limit=1,
        max_attempts=2,
        # The harness's own judge in scripts/e2e_acceptance/evaluators.py has
        # always refused anything but 0; the deployed one ran at the provider
        # default and carried +/- 3.3 at one pass for it. Free lever, and it
        # changes the instrument, so it lands before the re-baseline.
        temperature=0.0,
    ),
    PATH_QUALITY_RED_FLAGS: LLMPathPolicy(
        path=PATH_QUALITY_RED_FLAGS,
        scope="non_core",
        max_tokens=900,
        timeout_seconds=45.0,
        output_tokens_limit=900,
        total_tokens_limit=4000,
        request_limit=1,
        max_attempts=2,
    ),
    PATH_QUALITY_MANAGER: LLMPathPolicy(
        path=PATH_QUALITY_MANAGER,
        scope="non_core",
        max_tokens=2000,
        timeout_seconds=60.0,
        output_tokens_limit=2000,
        total_tokens_limit=8000,
        request_limit=1,
        max_attempts=2,
    ),
    PATH_CONVERSATION_SUMMARY: LLMPathPolicy(
        path=PATH_CONVERSATION_SUMMARY,
        scope="non_core",
        max_tokens=900,
        timeout_seconds=45.0,
        output_tokens_limit=900,
        total_tokens_limit=5000,
        request_limit=1,
        max_attempts=2,
    ),
    PATH_FACT_EXTRACTION: LLMPathPolicy(
        path=PATH_FACT_EXTRACTION,
        scope="non_core",
        max_tokens=700,
        timeout_seconds=30.0,
        output_tokens_limit=700,
        total_tokens_limit=3000,
        request_limit=1,
        max_attempts=1,
    ),
    PATH_VOICE_TRANSCRIPTION: LLMPathPolicy(
        path=PATH_VOICE_TRANSCRIPTION,
        scope="non_core",
        max_tokens=700,
        timeout_seconds=45.0,
        output_tokens_limit=700,
        total_tokens_limit=4000,
        request_limit=1,
        max_attempts=1,
    ),
    PATH_RESPONSE_ADAPTER: LLMPathPolicy(
        path=PATH_RESPONSE_ADAPTER,
        scope="non_core",
        max_tokens=700,
        timeout_seconds=30.0,
        output_tokens_limit=700,
        total_tokens_limit=3000,
        request_limit=1,
        max_attempts=2,
    ),
    PATH_RESPONSE_REPAIR_JUDGE: LLMPathPolicy(
        path=PATH_RESPONSE_REPAIR_JUDGE,
        scope="non_core",
        # Measured, not estimated. Replaying the exact request that failed on
        # 2026-08-11 twelve times against GLM 5.2 showed a complete answer cost
        # 720-1494 completion tokens: about 300 were the JSON the schema wants
        # and the rest was reasoning that vendor billed for and never returned.
        # 800 could not hold it at all. Every failure was the output schema
        # rejecting a truncated answer, never the provider. The path now runs
        # DeepSeek Flash, which spends about 270, but the ceiling stays where a
        # reasoning model would still fit: it is only spent when it is used, and
        # starving this call is the one failure mode we have already paid for.
        max_tokens=2000,
        # Halved on 2026-08-11 when the repair path gained a second attempt.
        # The customer waits for this on their own turn, so the budget is the
        # whole repair, not one call: 2 x 20s is under the 45s one attempt was
        # already allowed. `max_attempts` stays 1 because the retry lives in
        # `review_flagged_reply`, where the paid-call cap can count each try.
        timeout_seconds=20.0,
        output_tokens_limit=2000,
        total_tokens_limit=6000,
        request_limit=1,
        max_attempts=1,
        temperature=0.0,
        reasoning_enabled=False,
    ),
    PATH_AUTO_FAQ_TRANSLATE: LLMPathPolicy(
        path=PATH_AUTO_FAQ_TRANSLATE,
        scope="non_core",
        max_tokens=700,
        timeout_seconds=30.0,
        output_tokens_limit=700,
        total_tokens_limit=3000,
        request_limit=1,
        max_attempts=2,
        notify_on_failure=False,
    ),
    PATH_AUTO_FAQ_CANDIDATE: LLMPathPolicy(
        path=PATH_AUTO_FAQ_CANDIDATE,
        scope="non_core",
        max_tokens=900,
        timeout_seconds=30.0,
        output_tokens_limit=900,
        total_tokens_limit=3500,
        request_limit=1,
        max_attempts=2,
        notify_on_failure=False,
    ),
}

_RETRYABLE_ERRORS = (
    TimeoutError,
    httpx.HTTPError,
    ModelAPIError,
    ModelHTTPError,
    UnexpectedModelBehavior,
)


def policy_for_path(path: str) -> LLMPathPolicy:
    try:
        return _POLICIES[path]
    except KeyError as exc:
        raise ValueError(f"Unknown LLM path safety policy: {path}") from exc


@dataclass(frozen=True, slots=True)
class LLMUsageTelemetry:
    """Normalized usage fields from PydanticAI/OpenRouter run results."""

    path: str
    model: str
    provider: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    reasoning_tokens: int | None = None
    cached_tokens: int | None = None
    cache_write_tokens: int | None = None
    cost: float | None = None
    total_tokens: int | None = None
    requests: int | None = None

    def as_log_extra(self) -> dict[str, int | float | str | None]:
        return {
            "path": self.path,
            "model": self.model,
            "provider": self.provider,
            "input_tokens": self.prompt_tokens,
            "prompt_tokens": self.prompt_tokens,
            "output_tokens": self.completion_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "requests": self.requests,
            "reasoning_tokens": self.reasoning_tokens,
            "cached_tokens": self.cached_tokens,
            "cache_write_tokens": self.cache_write_tokens,
            "cost": self.cost,
        }

    def as_attempt_kwargs(self) -> dict[str, Any]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "reasoning_tokens": self.reasoning_tokens,
            "cached_tokens": self.cached_tokens,
            "cache_write_tokens": self.cache_write_tokens,
            "cost_usd": self.cost,
        }


def model_name_for_path(path: str, override: str | None = None) -> str:
    """Return the default OpenRouter model for an LLM path.

    GLM/main remains the default only for core client-facing paths. Non-core
    background and helper paths default to the fast model unless an explicit
    caller/admin override is supplied.
    """
    if override:
        return override
    policy = policy_for_path(path)
    if policy.scope == "core":
        return settings.openrouter_model_main
    return settings.openrouter_model_fast


def is_glm5_model_name(model_name: str) -> bool:
    normalized = model_name.lower()
    return "glm-5" in normalized or "glm5" in normalized


def openrouter_supports_prompt_cache_control(model_name: str) -> bool:
    normalized = model_name.strip().lower()
    return normalized.startswith(_OPENROUTER_CACHE_CONTROL_SUPPORTED_MODEL_PREFIXES)


def _openrouter_core_reasoning_effort(
    policy: LLMPathPolicy,
    model_name: str | None,
) -> Literal["low"] | None:
    if (
        policy.scope == "core"
        and model_name is not None
        and model_name.strip().lower()
        in _OPENROUTER_LOW_REASONING_EFFORT_CORE_MODEL_IDS
    ):
        return "low"
    return None


def _openrouter_extra_body(
    *,
    model_name: str | None,
    cache_telemetry_enabled: bool,
    reasoning_enabled: bool | None = None,
    reasoning_effort: Literal["low"] | None = None,
) -> dict[str, Any]:
    extra_body: dict[str, Any] = {}
    if cache_telemetry_enabled:
        extra_body["usage"] = {"include": True}
        if model_name and openrouter_supports_prompt_cache_control(model_name):
            extra_body["cache_control"] = {"type": "ephemeral"}
    if reasoning_enabled is False or (
        model_name
        and model_name.strip().lower() in _OPENROUTER_REASONING_DISABLED_MODEL_IDS
    ):
        extra_body["reasoning"] = {"enabled": False}
    elif reasoning_effort is not None:
        extra_body["reasoning"] = {"effort": reasoning_effort}
    return extra_body


def _merge_extra_body(
    current: object,
    generated: Mapping[str, Any],
    *,
    model_name: str | None,
    cache_telemetry_enabled: bool,
) -> dict[str, Any] | None:
    merged: dict[str, Any] = dict(current) if isinstance(current, Mapping) else {}
    if generated:
        merged.update(generated)

    if (
        not cache_telemetry_enabled
        or model_name is None
        or not openrouter_supports_prompt_cache_control(model_name)
    ):
        merged.pop("cache_control", None)

    return merged or None


def model_settings_for_path(
    path: str,
    *,
    model_name: str | None = None,
    provider: str = OPENROUTER_PROVIDER_NAME,
    cache_telemetry_enabled: bool = True,
) -> ModelSettings:
    policy = policy_for_path(path)
    settings_payload: dict[str, Any] = {
        "max_tokens": policy.max_tokens,
        "timeout": policy.timeout_seconds,
    }
    if policy.temperature is not None:
        settings_payload["temperature"] = policy.temperature
    if provider == OPENROUTER_PROVIDER_NAME and model_name is not None:
        extra_body = _openrouter_extra_body(
            model_name=model_name,
            cache_telemetry_enabled=cache_telemetry_enabled,
            reasoning_enabled=policy.reasoning_enabled,
            reasoning_effort=_openrouter_core_reasoning_effort(policy, model_name),
        )
        if extra_body:
            settings_payload["extra_body"] = extra_body
    return cast("ModelSettings", settings_payload)


def usage_limits_for_path(path: str) -> UsageLimits | None:
    policy = policy_for_path(path)
    if policy.scope == "core":
        return None
    return UsageLimits(
        request_limit=policy.request_limit,
        output_tokens_limit=policy.output_tokens_limit,
        total_tokens_limit=policy.total_tokens_limit,
    )


def _minimum_limit(current: int | None, policy_value: int | None) -> int | None:
    if policy_value is None:
        return current
    if current is None:
        return policy_value
    return min(current, policy_value)


def _merge_model_settings(
    path: str,
    current: ModelSettings | Mapping[str, Any] | None,
    *,
    model_name: str | None,
    provider: str,
    cache_telemetry_enabled: bool,
) -> ModelSettings:
    policy = policy_for_path(path)
    merged: dict[str, Any] = dict(current or {})

    current_max_tokens = merged.get("max_tokens")
    if isinstance(current_max_tokens, int):
        merged["max_tokens"] = min(current_max_tokens, policy.max_tokens)
    else:
        merged["max_tokens"] = policy.max_tokens

    current_timeout = merged.get("timeout")
    if current_timeout is None:
        merged["timeout"] = policy.timeout_seconds

    # A pinned temperature is policy, not a default: a caller must not be able
    # to hand the judge back its sampling noise.
    if policy.temperature is not None:
        merged["temperature"] = policy.temperature

    if provider == OPENROUTER_PROVIDER_NAME:
        generated_extra_body = _openrouter_extra_body(
            model_name=model_name,
            cache_telemetry_enabled=cache_telemetry_enabled,
            reasoning_effort=_openrouter_core_reasoning_effort(policy, model_name),
        )
        extra_body = _merge_extra_body(
            merged.get("extra_body"),
            generated_extra_body,
            model_name=model_name,
            cache_telemetry_enabled=cache_telemetry_enabled,
        )
        if extra_body is None:
            merged.pop("extra_body", None)
        else:
            merged["extra_body"] = extra_body

    return cast("ModelSettings", merged)


def _merge_usage_limits(path: str, current: UsageLimits | None) -> UsageLimits | None:
    policy = policy_for_path(path)
    if policy.scope == "core":
        return current

    if current is None:
        return usage_limits_for_path(path)

    return UsageLimits(
        request_limit=_minimum_limit(current.request_limit, policy.request_limit),
        output_tokens_limit=_minimum_limit(
            current.output_tokens_limit,
            policy.output_tokens_limit,
        ),
        total_tokens_limit=_minimum_limit(
            current.total_tokens_limit,
            policy.total_tokens_limit,
        ),
        input_tokens_limit=current.input_tokens_limit,
        tool_calls_limit=current.tool_calls_limit,
        count_tokens_before_request=current.count_tokens_before_request,
    )


def _should_block_for_budget(policy: LLMPathPolicy) -> bool:
    return policy.scope == "non_core" and settings.llm_non_core_budget_blocked


def _usage_value(container: Any, key: str) -> Any:
    if container is None:
        return None
    if isinstance(container, Mapping):
        return container.get(key)
    return getattr(container, key, None)


def _usage_number(container: Any, *keys: str) -> int | float | None:
    for key in keys:
        value = _usage_value(container, key)
        if isinstance(value, int | float):
            return value
    return None


def _valid_cost(value: int | float | None) -> float | None:
    if (
        value is None
        or isinstance(value, bool)
        or not math.isfinite(float(value))
        or float(value) < 0
    ):
        return None
    return float(value)


def _openrouter_completion_failed(response: Any) -> bool:
    choices = getattr(response, "choices", None)
    if not isinstance(choices, list) or not choices:
        return False
    return str(getattr(choices[0], "finish_reason", "")) == "error"


def _openrouter_completion_error_type(response: Any) -> str | None:
    choices = getattr(response, "choices", None)
    if not isinstance(choices, list) or not choices:
        return None
    error = _usage_value(choices[0], "error")
    metadata = _usage_value(error, "metadata")
    error_type = _usage_value(metadata, "error_type")
    return error_type if isinstance(error_type, str) and error_type else None


def _openrouter_completion_error(
    model_name: str,
    error_type: str | None,
) -> OpenRouterCompletionError:
    normalized = error_type or "unknown"
    return OpenRouterCompletionError(
        model_name=model_name,
        message=f"OpenRouter completion failed ({normalized})",
    )


def _nested_usage_number(container: Any, *path: str) -> int | float | None:
    current = container
    for key in path:
        current = _usage_value(current, key)
    return current if isinstance(current, int | float) else None


def _coerce_int(value: int | float | None) -> int | None:
    if value is None:
        return None
    return int(value)


def _coerce_float(value: int | float | None) -> float | None:
    if value is None:
        return None
    return float(value)


def _first_usage_number(*values: int | float | None) -> int | float | None:
    for value in values:
        if value is not None:
            return value
    return None


def _provider_reported_cost(result: Any) -> float | None:
    new_messages = getattr(result, "new_messages", None)
    if not callable(new_messages):
        return None
    try:
        messages = new_messages()
    except Exception:
        return None

    costs: list[float] = []
    for message in messages:
        details = getattr(message, "provider_details", None)
        value = details.get("usage_cost_usd") if isinstance(details, Mapping) else None
        if (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(float(value))
            and float(value) >= 0
        ):
            costs.append(float(value))
    return sum(costs) if costs else None


def extract_llm_usage_telemetry(
    *,
    path: str,
    model_name: str,
    provider: str = OPENROUTER_PROVIDER_NAME,
    result: Any,
) -> LLMUsageTelemetry:
    try:
        usage = result.usage()
    except Exception:
        usage = None

    prompt_details = _usage_value(usage, "prompt_tokens_details")
    completion_details = _usage_value(usage, "completion_tokens_details")

    prompt_tokens = _usage_number(usage, "input_tokens", "prompt_tokens")
    completion_tokens = _usage_number(usage, "output_tokens", "completion_tokens")
    cached_tokens = _first_usage_number(
        _usage_number(prompt_details, "cached_tokens"),
        _nested_usage_number(
            usage, "details", "prompt_tokens_details", "cached_tokens"
        ),
        _nested_usage_number(usage, "details", "cached_tokens"),
    )
    cache_write_tokens = _first_usage_number(
        _usage_number(prompt_details, "cache_write_tokens"),
        _nested_usage_number(
            usage,
            "details",
            "prompt_tokens_details",
            "cache_write_tokens",
        ),
        _nested_usage_number(usage, "details", "cache_write_tokens"),
    )
    reasoning_tokens = _first_usage_number(
        _usage_number(completion_details, "reasoning_tokens"),
        _nested_usage_number(
            usage,
            "details",
            "completion_tokens_details",
            "reasoning_tokens",
        ),
        _nested_usage_number(usage, "details", "reasoning_tokens"),
    )

    return LLMUsageTelemetry(
        path=path,
        model=model_name,
        provider=provider,
        prompt_tokens=_coerce_int(prompt_tokens),
        completion_tokens=_coerce_int(completion_tokens),
        reasoning_tokens=_coerce_int(reasoning_tokens),
        cached_tokens=_coerce_int(cached_tokens),
        cache_write_tokens=_coerce_int(cache_write_tokens),
        cost=_coerce_float(
            _first_usage_number(
                _usage_number(usage, "cost", "cost_usd"),
                _nested_usage_number(usage, "details", "cost"),
                _nested_usage_number(usage, "details", "cost_usd"),
                _provider_reported_cost(result),
            )
        ),
        total_tokens=_coerce_int(_usage_number(usage, "total_tokens")),
        requests=_coerce_int(_usage_number(usage, "requests")),
    )


def attach_llm_usage_telemetry(output: Any, usage: LLMUsageTelemetry) -> Any:
    try:
        setattr(output, LLM_USAGE_TELEMETRY_ATTR, usage)
    except Exception:
        logger.debug("Failed to attach LLM usage telemetry to output", exc_info=True)
    return output


def get_llm_usage_telemetry(output: Any) -> LLMUsageTelemetry | None:
    usage = getattr(output, LLM_USAGE_TELEMETRY_ATTR, None)
    return usage if isinstance(usage, LLMUsageTelemetry) else None


def llm_usage_attempt_kwargs(output: Any) -> dict[str, Any]:
    usage = get_llm_usage_telemetry(output)
    return usage.as_attempt_kwargs() if usage is not None else {}


async def notify_llm_safety_event(
    *,
    event: Literal["budget_blocked", "final_failure"],
    path: str,
    model_name: str,
    error: BaseException | None = None,
) -> None:
    """Narrow admin notification adapter for LLM safety failures."""
    title = {
        "budget_blocked": "LLM budget block",
        "final_failure": "LLM final failure",
    }[event]
    error_text = f"{type(error).__name__}: {error}" if error is not None else "n/a"
    message = (
        f"<b>{escape(title)}</b>\n"
        f"<b>Path:</b> {escape(path)}\n"
        f"<b>Model:</b> {escape(model_name)}\n"
        f"<b>Error:</b> {escape(error_text)}"
    )

    try:
        from src.services.notifications import send_telegram_message

        await send_telegram_message(message)
    except Exception:
        logger.exception("Failed to send LLM safety notification")


async def _notify_safely(
    *,
    event: Literal["budget_blocked", "final_failure"],
    policy: LLMPathPolicy,
    model_name: str,
    error: BaseException | None = None,
) -> None:
    try:
        await notify_llm_safety_event(
            event=event,
            path=policy.path,
            model_name=model_name,
            error=error,
        )
    except Exception:
        logger.exception("LLM safety notification adapter raised")


def _is_retryable_error(error: BaseException) -> bool:
    return not isinstance(error, OpenRouterCompletionError) and isinstance(
        error,
        _RETRYABLE_ERRORS,
    )


async def run_agent_with_safety(
    agent: Any,
    path: str,
    user_prompt: Any = None,
    *,
    model_name: str,
    provider: str = OPENROUTER_PROVIDER_NAME,
    cache_telemetry_enabled: bool = True,
    max_attempts_override: int | None = None,
    notify_on_failure_override: bool | None = None,
    **kwargs: Any,
) -> Any:
    """Run a PydanticAI agent through the repo LLM safety policy."""
    policy = policy_for_path(path)
    run_kwargs = dict(kwargs)
    run_kwargs["model_settings"] = _merge_model_settings(
        path,
        run_kwargs.get("model_settings"),
        model_name=model_name,
        provider=provider,
        cache_telemetry_enabled=cache_telemetry_enabled,
    )

    merged_usage_limits = _merge_usage_limits(path, run_kwargs.get("usage_limits"))
    if merged_usage_limits is None:
        run_kwargs.pop("usage_limits", None)
    else:
        run_kwargs["usage_limits"] = merged_usage_limits

    if _should_block_for_budget(policy):
        error = LLMBudgetBlocked(f"LLM path {policy.path} blocked by budget policy")
        if policy.notify_on_budget_block:
            await _notify_safely(
                event="budget_blocked",
                policy=policy,
                model_name=model_name,
                error=error,
            )
        raise error

    attempts = max(max_attempts_override or policy.max_attempts, 1)
    notify_on_failure = (
        policy.notify_on_failure
        if notify_on_failure_override is None
        else notify_on_failure_override
    )
    last_error: BaseException | None = None
    for attempt_number in range(1, attempts + 1):
        try:
            result = await asyncio.wait_for(
                agent.run(user_prompt, **run_kwargs),
                timeout=policy.timeout_seconds,
            )
            usage = extract_llm_usage_telemetry(
                path=policy.path,
                model_name=model_name,
                provider=provider,
                result=result,
            )
            logger.info(
                "llm.safety.usage",
                extra=usage.as_log_extra(),
            )
            return attach_llm_usage_telemetry(result, usage)
        except Exception as exc:
            last_error = exc
            can_retry = attempt_number < attempts and _is_retryable_error(exc)
            logger.warning(
                "llm.safety.failure",
                extra={
                    "path": policy.path,
                    "model": model_name,
                    "attempt": attempt_number,
                    "max_attempts": attempts,
                    "retrying": can_retry,
                    "error_type": type(exc).__name__,
                },
            )
            if can_retry:
                continue
            if notify_on_failure:
                await _notify_safely(
                    event="final_failure",
                    policy=policy,
                    model_name=model_name,
                    error=exc,
                )
            raise

    if last_error is not None:
        raise last_error
    raise RuntimeError(f"LLM path {policy.path} did not return a result")
