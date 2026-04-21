"""Central safety policy for PydanticAI LLM calls."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from html import escape
from typing import Any, Literal, cast

import httpx
from pydantic_ai import ModelSettings, UsageLimits
from pydantic_ai.exceptions import (
    ModelAPIError,
    ModelHTTPError,
    UnexpectedModelBehavior,
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
PATH_RESPONSE_ADAPTER = "response_adapter"
PATH_AUTO_FAQ_TRANSLATE = "auto_faq_translate"


class LLMBudgetBlocked(RuntimeError):
    """Raised when configured budget controls block a non-core LLM path."""


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
        scope="non_core",
        max_tokens=2500,
        timeout_seconds=60.0,
        output_tokens_limit=2500,
        total_tokens_limit=10000,
        request_limit=1,
        max_attempts=2,
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
    PATH_AUTO_FAQ_TRANSLATE: LLMPathPolicy(
        path=PATH_AUTO_FAQ_TRANSLATE,
        scope="non_core",
        max_tokens=700,
        timeout_seconds=30.0,
        output_tokens_limit=700,
        total_tokens_limit=3000,
        request_limit=1,
        max_attempts=2,
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


def model_settings_for_path(path: str) -> ModelSettings:
    policy = policy_for_path(path)
    return ModelSettings(max_tokens=policy.max_tokens, timeout=policy.timeout_seconds)


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


def _usage_number(container: Any, *keys: str) -> int | float | None:
    if container is None:
        return None
    if isinstance(container, Mapping):
        for key in keys:
            value = container.get(key)
            if isinstance(value, int | float):
                return value
        return None
    for key in keys:
        value = getattr(container, key, None)
        if isinstance(value, int | float):
            return value
    return None


def _nested_usage_number(container: Any, *path: str) -> int | float | None:
    current = container
    for key in path:
        if current is None:
            return None
        if isinstance(current, Mapping):
            current = current.get(key)
        else:
            current = getattr(current, key, None)
    return current if isinstance(current, int | float) else None


def _usage_log_shape(
    *,
    path: str,
    model_name: str,
    result: Any,
) -> dict[str, int | float | str | None]:
    try:
        usage = result.usage()
    except Exception:
        usage = None

    prompt_details = getattr(usage, "prompt_tokens_details", None)
    completion_details = getattr(usage, "completion_tokens_details", None)

    return {
        "path": path,
        "model": model_name,
        "input_tokens": _usage_number(usage, "input_tokens", "prompt_tokens"),
        "output_tokens": _usage_number(usage, "output_tokens", "completion_tokens"),
        "total_tokens": _usage_number(usage, "total_tokens"),
        "requests": _usage_number(usage, "requests"),
        "cached_tokens": _usage_number(prompt_details, "cached_tokens")
        or _nested_usage_number(usage, "details", "cached_tokens"),
        "cache_write_tokens": _usage_number(prompt_details, "cache_write_tokens")
        or _nested_usage_number(usage, "details", "cache_write_tokens"),
        "reasoning_tokens": _usage_number(completion_details, "reasoning_tokens")
        or _nested_usage_number(usage, "details", "reasoning_tokens"),
        "cost": _usage_number(usage, "cost"),
    }


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
    return isinstance(error, _RETRYABLE_ERRORS)


async def run_agent_with_safety(
    agent: Any,
    path: str,
    user_prompt: Any = None,
    *,
    model_name: str,
    **kwargs: Any,
) -> Any:
    """Run a PydanticAI agent through the repo LLM safety policy."""
    policy = policy_for_path(path)
    run_kwargs = dict(kwargs)
    run_kwargs["model_settings"] = _merge_model_settings(
        path, run_kwargs.get("model_settings")
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

    attempts = max(policy.max_attempts, 1)
    last_error: BaseException | None = None
    for attempt_number in range(1, attempts + 1):
        try:
            result = await asyncio.wait_for(
                agent.run(user_prompt, **run_kwargs),
                timeout=policy.timeout_seconds,
            )
            logger.info(
                "llm.safety.usage",
                extra=_usage_log_shape(
                    path=policy.path,
                    model_name=model_name,
                    result=result,
                ),
            )
            return result
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
            if policy.notify_on_failure:
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
