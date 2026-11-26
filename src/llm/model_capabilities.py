"""Lightweight central catalog of OpenRouter model IDs and capabilities.

Keep this module strictly stdlib-only so ``src.core.config`` and ``src.main`` can
validate model IDs at startup without importing ``pydantic_ai`` or ``openai``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ReasoningEffort = Literal["none", "low", "medium"]


@dataclass(frozen=True, slots=True)
class ModelCapabilities:
    """Provider/runtime capability flags for a model family."""

    supports_prompt_cache_control: bool = False
    reasoning_disabled: bool = False
    core_reasoning_effort: ReasoningEffort | None = None
    core_chat_only_reasoning_effort: ReasoningEffort | None = None
    bounded_non_core_helper: bool = False


MODEL_CAPABILITIES: dict[str, ModelCapabilities] = {
    "anthropic/claude-sonnet-5.5": ModelCapabilities(
        supports_prompt_cache_control=True,
    ),
    "anthropic/claude-haiku-5.5": ModelCapabilities(
        supports_prompt_cache_control=True,
    ),
    "deepseek/deepseek-v4-flash": ModelCapabilities(
        reasoning_disabled=True,
    ),
    "z-ai/glm-5.3-flash": ModelCapabilities(
        core_reasoning_effort="low",
    ),
    "z-ai/glm-5.2": ModelCapabilities(),
    "openai/gpt-6-luna": ModelCapabilities(
        core_reasoning_effort="medium",
        bounded_non_core_helper=True,
    ),
    "openai/gpt-6.1-sol": ModelCapabilities(
        core_chat_only_reasoning_effort="medium",
    ),
    "openai/gpt-6.1-terra": ModelCapabilities(
        bounded_non_core_helper=True,
    ),
    "openai/gpt-4o-mini-transcribe": ModelCapabilities(),
}

_VENDOR_PREFIX_CAPABILITIES: tuple[tuple[str, ModelCapabilities], ...] = (
    (
        "anthropic/",
        ModelCapabilities(supports_prompt_cache_control=True),
    ),
)

_DEFAULT_MODEL_CAPABILITIES = ModelCapabilities()


def _normalize_model_name(model_name: str | None) -> str:
    return (model_name or "").strip().lower()


def _matches_model_prefix(normalized: str, prefix: str) -> bool:
    return (
        normalized == prefix
        or normalized.startswith(f"{prefix}-")
        or normalized.startswith(f"{prefix}:")
    )


def resolve_model_capabilities(model_name: str | None) -> ModelCapabilities:
    """Resolve model capabilities via exact, dated/variant suffix, or vendor prefix."""
    normalized = _normalize_model_name(model_name)
    if not normalized:
        return _DEFAULT_MODEL_CAPABILITIES

    for prefix, capabilities in MODEL_CAPABILITIES.items():
        if _matches_model_prefix(normalized, prefix):
            return capabilities

    for vendor_prefix, capabilities in _VENDOR_PREFIX_CAPABILITIES:
        if normalized.startswith(vendor_prefix):
            return capabilities

    return _DEFAULT_MODEL_CAPABILITIES


def is_known_model_id(model_name: str) -> bool:
    """Return True if ``model_name`` matches an approved catalog ID or variant."""
    normalized = _normalize_model_name(model_name)
    if not normalized:
        return False
    return any(
        _matches_model_prefix(normalized, prefix) for prefix in MODEL_CAPABILITIES
    )


def validate_openrouter_model_id(value: str, *, allow_empty: bool = False) -> str:
    """Validate and normalize an OpenRouter ``vendor/model`` identifier."""
    if not isinstance(value, str):
        raise ValueError("OpenRouter model ID must be a string")
    cleaned = value.strip()
    if not cleaned:
        if allow_empty:
            return ""
        raise ValueError("OpenRouter model ID must not be empty")
    if any(ch.isspace() for ch in cleaned):
        raise ValueError(
            f"Invalid OpenRouter model ID {value!r}: whitespace is not allowed"
        )
    if "/" not in cleaned:
        raise ValueError(
            f"Invalid OpenRouter model ID {value!r}: expected 'vendor/model' format"
        )
    segments = cleaned.split("/")
    if any(not segment for segment in segments):
        raise ValueError(
            f"Invalid OpenRouter model ID {value!r}: empty segment in 'vendor/model'"
        )
    return cleaned
