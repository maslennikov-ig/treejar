---
task_id: tj-ruue.5
stage_id: tj-ruue
repo: treejar
branch: codex/tj-ruue-model-routing-cache-telemetry
base_branch: codex/live-triage-20260417
base_commit: eb4fa520c07111d0500353851f9e37f07f2cda3a
worktree: /home/me/code/treejar/.worktrees/codex-tj-ruue-model-routing-cache-telemetry
status: returned
verification:
  - Context7 PydanticAI docs query: passed
  - Context7 OpenRouter docs query: passed
  - Orchestrator review report docs/reports/code-reviews/2026-04/CR-2026-04-22-tj-ruue-model-routing-cache-telemetry-orchestrator.md: passed after fixing tj-ruue.5.1
  - uv run --extra dev python -m pytest -s tests/test_llm_safety.py -q: passed
  - uv run --extra dev python -m pytest -s tests/test_llm_safety.py tests/test_llm_attempts.py tests/test_quality_job.py tests/test_manager_job.py tests/test_quality_evaluator.py tests/test_manager_evaluator.py tests/test_llm_conversation_summary.py tests/test_response_adapter.py tests/test_auto_faq.py tests/test_services_followup_details.py tests/test_services_chat.py tests/test_services_chat_batch.py tests/test_chat_escalation.py -q: passed
  - uv run --extra dev python -m pytest -s tests/test_llm_safety.py tests/test_llm_attempts.py tests/test_quality_job.py tests/test_manager_job.py tests/test_quality_evaluator.py tests/test_manager_evaluator.py tests/test_llm_conversation_summary.py tests/test_response_adapter.py tests/test_auto_faq.py tests/test_services_followup_details.py -q: passed
  - uv run ruff check src/ tests/: passed
  - uv run ruff format --check src/ tests/: passed
  - uv run mypy src/: passed
  - uv run python scripts/orchestration/validate_artifact.py .codex/stages/tj-ruue/artifacts/tj-ruue.5.md: passed
  - git diff --check: passed
  - npm ci in frontend/admin: passed
  - uv run python -m pytest -s tests/ -v --tb=short: passed
changed_files:
  - .codex/stages/tj-ruue/artifacts/tj-ruue.5.md
  - docs/reports/code-reviews/2026-04/CR-2026-04-22-tj-ruue-model-routing-cache-telemetry-orchestrator.md
  - src/llm/__init__.py
  - src/llm/attempts.py
  - src/llm/conversation_summary.py
  - src/llm/engine.py
  - src/llm/response_adapter.py
  - src/llm/safety.py
  - src/quality/config.py
  - src/quality/evaluator.py
  - src/quality/job.py
  - src/quality/manager_evaluator.py
  - src/quality/manager_job.py
  - src/services/auto_faq.py
  - src/services/followup.py
  - tests/test_llm_attempts.py
  - tests/test_llm_safety.py
  - tests/test_manager_evaluator.py
  - tests/test_quality_evaluator.py
  - tests/test_quality_job.py
---

# Summary

Implemented centralized LLM model routing and OpenRouter usage/cache telemetry.

`src/llm/safety.py` now owns default model selection by path: core client-facing
chat/follow-up paths keep `openrouter_model_main`, while non-core QA, manager
QA, red flags, summaries, response adapter, and Auto-FAQ translation default to
`openrouter_model_fast` unless the caller/admin explicitly supplies an override.

OpenRouter request settings now add `usage: {"include": true}` through
PydanticAI `ModelSettings.extra_body` when telemetry is enabled. Top-level
`cache_control: {"type": "ephemeral"}` is sent only for supported Anthropic
model ids and is removed for unsupported models such as GLM-5 and Xiaomi.
Provider-side `max_tokens` still comes from the safety policy and remains the
runaway-output control.

Usage telemetry is normalized into path/model/provider plus prompt/input tokens,
completion/output tokens, reasoning tokens, cached tokens, cache-write tokens,
and cost when available. QA, manager QA, and red-flag jobs now persist those
fields into `llm_attempts` for `success` and LLM-backed `no_action` outcomes
when evaluator result usage is available.

Orchestrator review found and fixed `tj-ruue.5.1`: importing
`src.quality.config` without `OPENROUTER_API_KEY` failed because the `src.llm`
package eagerly imported `src.llm.engine`. `src/llm/__init__.py` now exposes
`LLMResponse` and `process_message` lazily, so config/safety imports do not
instantiate OpenRouter providers.

# Context7 Facts

PydanticAI:

- `ModelSettings(max_tokens=...)` can be configured at model, agent, or run
  level; run-level settings have highest precedence.
- `OpenAIChatModel` can be constructed directly with a provider, including an
  OpenRouter-compatible provider.
- Current local PydanticAI `ModelSettings` exposes `extra_body`; this is the
  safe path used here for OpenRouter request extras while preserving
  provider-side `max_tokens`.
- `UsageLimits` supports request and token limits, including
  `request_limit`, `response_tokens_limit`/`output_tokens_limit`, and
  `total_tokens_limit`, but token-limit exceptions can happen after a provider
  response exists. It is not a substitute for provider-side `max_tokens`.
- PydanticAI OpenRouter docs also document `OpenRouterModelSettings` with
  `openrouter_usage={"include": True}`; this codebase currently uses
  `OpenAIChatModel` plus `OpenRouterProvider`, so request extras are sent via
  `extra_body`.

OpenRouter:

- Response usage can include `prompt_tokens`, `completion_tokens`, and
  `total_tokens`.
- `prompt_tokens_details.cached_tokens` reports tokens read from cache.
- `prompt_tokens_details.cache_write_tokens` reports tokens written to cache
  for explicit cache-capable models.
- `completion_tokens_details.reasoning_tokens` reports thinking/reasoning
  tokens where supported.
- `usage.cost` may be returned when usage accounting is included.
- Prompt caching `cache_control` supports `{"type": "ephemeral"}` and optional
  TTL. OpenRouter documents automatic top-level `cache_control` and explicit
  content-block breakpoints for Anthropic Claude models.
- OpenRouter states provider sticky routing helps cache hits for implicit and
  explicit caching, but `cache_control` support is model/provider-specific.
  This implementation only sends `cache_control` for Anthropic model ids and
  never sends it to GLM-5 or Xiaomi defaults.
- Prompt caching is observability/cost optimization only; runaway output is
  still controlled by provider-side `max_tokens`.

# Verification

Run so far:

- Context7 PydanticAI docs query: passed.
- Context7 OpenRouter docs query: passed.
- Orchestrator code review report:
  `docs/reports/code-reviews/2026-04/CR-2026-04-22-tj-ruue-model-routing-cache-telemetry-orchestrator.md`.
- `uv run --extra dev python -m pytest -s tests/test_llm_safety.py -q` ->
  passed, `18 passed`.
- `uv run --extra dev python -m pytest -s tests/test_llm_safety.py tests/test_llm_attempts.py tests/test_quality_job.py tests/test_manager_job.py tests/test_quality_evaluator.py tests/test_manager_evaluator.py tests/test_llm_conversation_summary.py tests/test_response_adapter.py tests/test_auto_faq.py tests/test_services_followup_details.py tests/test_services_chat.py tests/test_services_chat_batch.py tests/test_chat_escalation.py -q` ->
  passed, `156 passed`.
- `uv run --extra dev python -m pytest -s tests/test_llm_safety.py tests/test_llm_attempts.py tests/test_quality_evaluator.py tests/test_manager_evaluator.py tests/test_quality_job.py tests/test_manager_job.py -q` -> passed, `118 passed`.
- `uv run --extra dev python -m pytest -s tests/test_llm_safety.py tests/test_llm_attempts.py tests/test_quality_job.py tests/test_manager_job.py tests/test_quality_evaluator.py tests/test_manager_evaluator.py tests/test_llm_conversation_summary.py tests/test_response_adapter.py tests/test_auto_faq.py tests/test_services_followup_details.py -q` -> passed, `136 passed`.
- `uv run ruff check src/ tests/` -> passed.
- `uv run ruff format --check src/ tests/` -> passed.
- `uv run mypy src/` -> passed, `Success: no issues found in 121 source files`.
- `uv run python scripts/orchestration/validate_artifact.py .codex/stages/tj-ruue/artifacts/tj-ruue.5.md` -> passed, `artifact validation OK`.
- `git diff --check` -> passed.
- Initial full `uv run python -m pytest -s tests/ -v --tb=short` failed only on
  two dashboard frontend tests because `frontend/admin/node_modules/esbuild` was
  missing in this fresh worktree.
- `npm ci` in `frontend/admin` -> passed; npm reported Node 18 engine warnings
  for packages requiring Node 20+ and existing high-severity audit findings.
- Re-run `uv run python -m pytest -s tests/ -v --tb=short` -> passed,
  `727 passed, 19 skipped`.

# Risks / Follow-ups / Explicit Defers

- No commit, push, deploy, staging mutation, or production mutation was done.
- Review follow-up Bead `tj-ruue.5.1` tracks the import-side-effect fix and
  should be closed by the orchestrator after stage integration.
- `llm_attempts.cost_usd` stores the normalized OpenRouter `usage.cost` field
  when available; OpenRouter documents this as cost/credits, so downstream
  reporting should treat it as provider-reported cost rather than a locally
  recomputed invoice.
- `cache_control` is intentionally conservative: only Anthropic model ids get
  the request directive. Other providers can still report implicit cache usage
  through OpenRouter usage fields when available.
- Bead `tj-ruue.5` is intentionally left open/returned for orchestrator review.
