# Code Review: tj-ruue.5 Model Routing and Cache Telemetry

**Date**: 2026-04-22
**Scope**: Worker diff in `codex/tj-ruue-model-routing-cache-telemetry` plus orchestrator follow-up fix
**Files**: 20 | **Verdict**: PASS after fix

## Summary

|              | Critical | High | Medium | Low |
| ------------ | -------- | ---- | ------ | --- |
| Issues       | 0        | 1    | 0      | 0   |
| Improvements | -        | 0    | 0      | 0   |

The model routing change is aligned with the cost-control plan: core chat and
follow-up keep the main model by default, while QA, manager QA, red flags,
summary, response adapter, and Auto-FAQ translation default to the fast model.
OpenRouter usage/cache telemetry is normalized and persisted for QA attempt
success and LLM-backed no-action outcomes.

## Issues

### High

#### 1. AI Quality config import required an OpenRouter API key

- **File**: `src/llm/__init__.py:1`
- **Problem**: The worker changed `src/quality/config.py` to import
  `src.llm.safety` for default QA model routing. Before the review fix,
  importing any `src.llm.*` submodule executed `src/llm/__init__.py`, which
  eagerly imported `src.llm.engine`. That constructed `OpenRouterProvider` at
  import time and raised when `OPENROUTER_API_KEY` was absent.
- **Impact**: Admin/config code could fail during import in offline tests,
  management scripts, or settings-only contexts even though it does not need to
  call an LLM. That also made QA controls harder to inspect while credentials
  are intentionally unavailable.
- **Fix**: Fixed in review follow-up `tj-ruue.5.1`. `src/llm/__init__.py` now
  exposes `LLMResponse` and `process_message` lazily via `__getattr__`, so
  importing `src.llm.safety` no longer imports `src.llm.engine`.
- **Tests**: Added `test_ai_quality_config_import_does_not_require_openrouter_api_key`
  and expanded targeted coverage to include chat import users.

## Positive Patterns

- `src/llm/safety.py` is now the single routing point for core vs non-core model
  defaults.
- Provider-side `max_tokens` remains enforced on all known LLM paths.
- Unsupported GLM/Xiaomi model ids do not receive Anthropic `cache_control`.
- Usage extraction preserves zero-valued cache/reasoning/cost fields.
- Attempt hashes include cache telemetry state, avoiding stale terminal reuse
  when admin-visible request settings change.

## Context7 Notes

- PydanticAI docs document `OpenRouterModelSettings(openrouter_usage={"include": True})`
  for native `OpenRouterModel`, and also support `ModelSettings.extra_body`.
  This codebase currently uses `OpenAIChatModel` with `OpenRouterProvider`, so
  `extra_body` is the compatible path for OpenRouter request extras.
- OpenRouter docs now show usage fields on responses by default, including
  `prompt_tokens_details.cached_tokens`, `cache_write_tokens`,
  `completion_tokens_details.reasoning_tokens`, and provider-reported cost.
- OpenRouter prompt caching is provider/model specific. Top-level
  `cache_control` is intentionally limited here to Anthropic model ids and is
  not treated as runaway-output protection.

## Escalation

- No senior escalation required after the lazy import fix.

## Validation

- Context7 PydanticAI docs checked for `ModelSettings`, `OpenRouterModelSettings`,
  `openrouter_usage`, and settings precedence.
- Context7 OpenRouter docs checked for usage telemetry and prompt caching
  `cache_control` semantics.
- `uv run --extra dev python -m pytest -s tests/test_llm_safety.py -q` ->
  `18 passed`.
- `uv run --extra dev python -m pytest -s tests/test_llm_safety.py tests/test_llm_attempts.py tests/test_quality_job.py tests/test_manager_job.py tests/test_quality_evaluator.py tests/test_manager_evaluator.py tests/test_llm_conversation_summary.py tests/test_response_adapter.py tests/test_auto_faq.py tests/test_services_followup_details.py tests/test_services_chat.py tests/test_services_chat_batch.py tests/test_chat_escalation.py -q`
  -> `156 passed`.
- `uv run python -m pytest -s tests/ -v --tb=short` ->
  `727 passed, 19 skipped`.
- `git diff --check` -> passed.
