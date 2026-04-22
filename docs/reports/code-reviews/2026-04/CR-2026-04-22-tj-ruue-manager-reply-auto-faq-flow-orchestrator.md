# Code Review: tj-ruue.6 Manager Reply and Auto-FAQ Flow

**Date**: 2026-04-22
**Scope**: Worker diff in `codex/tj-ruue-manager-reply-auto-faq-flow`
**Files**: 11 | **Verdict**: PASS

## Summary

|              | Critical | High | Medium | Low |
| ------------ | -------- | ---- | ------ | --- |
| Issues       | 0        | 0    | 0      | 0   |
| Improvements | -        | 0    | 0      | 0   |

No blocking issues found. The implementation preserves the low-cost path for
normal manager replies, uses a single structured LLM call only for explicit
`faq_global` actions, and changes Auto-FAQ persistence to confirmation-first
with deterministic post-checks.

## Issues

None.

## Positive Patterns

- Normal manager replies still call only `adapt_manager_response`; the combined
  Auto-FAQ path is isolated behind explicit `faq_global` mode.
- `PATH_AUTO_FAQ_CANDIDATE` is a non-core safety path with provider-side
  `max_tokens`, usage limits, retry policy, timeout, and fast-model routing.
- Candidate review runs before persistence and blocks missing, low-confidence,
  unsafe, context-specific, and duplicate candidates.
- The old `save_to_faq()` entrypoint remains backward-compatible while changing
  its default behavior to `needs_confirmation` unless `admin_confirmed=True`.

## Context7 Notes

- PydanticAI docs confirm that `Agent(..., output_type=SomeBaseModel)` returns
  typed structured output via `result.output` and validates through Pydantic.
- Nested Pydantic models in structured outputs match the implementation shape:
  `ManagerReplyWithAutoFAQResult` contains an optional `AutoFAQCandidate`.
- The existing safety wrapper remains the correct place to pass run-time
  `model_settings` and `UsageLimits`.

## Escalation

- No senior escalation required.

## Validation

- Context7 PydanticAI docs checked for structured `output_type` behavior.
- `uv run --extra dev python -m pytest -s tests/test_auto_faq.py tests/test_response_adapter.py tests/test_webhook_manager.py tests/test_services_chat.py tests/test_llm_safety.py tests/test_faq_translation.py -q`
  -> `56 passed`.
- `uv run ruff check src/ tests/` -> passed.
- `uv run ruff format --check src/ tests/` -> passed.
- `uv run mypy src/` -> passed.
- `uv run python scripts/orchestration/validate_artifact.py .codex/stages/tj-ruue/artifacts/tj-ruue.6.md`
  -> passed.
- `git diff --check` -> passed.
- Full pytest was not run in the worker worktree because `frontend/admin/node_modules/esbuild`
  is missing there. The stage worktree has frontend dependencies and should run
  full pytest after integration.
