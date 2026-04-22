# Code Review: tj-ruue.4 Summary Transcript Builder

**Date**: 2026-04-22
**Scope**: Worker diff in `codex/tj-ruue-summary-transcript-builder` plus orchestrator follow-up fix
**Files**: 15 | **Verdict**: PASS after fix

## Summary

|              | Critical | High | Medium | Low |
| ------------ | -------- | ---- | ------ | --- |
| Issues       | 0        | 1    | 0      | 0   |
| Improvements | -        | 0    | 0      | 0   |

The bounded transcript builder is directionally correct: scheduled QA defaults to summary mode, disabled mode skips provider calls, full transcript is routed only through explicit config/gate state, and prompts stay under the intended QA budgets in tests.

## Issues

### High

#### 1. Terminal LLM attempts ignored transcript/settings hash changes

- **File**: `src/llm/attempts.py:263`
- **Problem**: The worker correctly added `transcript_mode` and `quality-review-context-summary:v1` into QA `input_hash`/`settings_hash`, but `begin_llm_attempt()` still skipped every terminal attempt by the old logical key only: `path`, `entity_type`, `entity_id`, `entity_updated_at`, `prompt_version`.
- **Impact**: A previous `no_action` from disabled transcript mode, or a previous `success` from another model/settings combination, could block re-evaluation after an admin changed `disabled -> summary/full` or changed QA model/settings. That would silently undercut the new admin controls.
- **Fix**: Fixed in review follow-up `tj-ruue.4.1`. Terminal attempts are now reusable only when incoming `input_hash` and `settings_hash` match stored values. Changed hashes reopen the existing row under Redis lock and clear stale `result_json`/`last_error`.
- **Tests**: Added `test_terminal_attempt_reopens_when_input_hash_changes` and `test_terminal_attempt_reopens_when_settings_hash_changes`.

## Positive Patterns

- Summary contexts are built from deterministic excerpts, not raw full history by default.
- Disabled transcript mode returns local insufficient/no-action results without provider calls.
- Manager QA focuses post-escalation messages while retaining compact prior context.
- Attempt hashes now carry transcript mode and summary prompt version; the review fix makes those hashes operationally effective.

## Escalation

- No senior escalation required after the attempt reuse fix.

## Validation

- Context7 PydanticAI docs checked for structured output, `ModelSettings(max_tokens=...)`, and `UsageLimits`.
- `uv run --extra dev python -m pytest -s tests/test_llm_attempts.py tests/test_quality_transcript_context.py tests/test_quality_job.py tests/test_manager_job.py tests/test_quality_evaluator.py tests/test_manager_evaluator.py tests/test_llm_conversation_summary.py tests/test_llm_context.py -q` -> `113 passed`.
- `uv run ruff check src/ tests/` -> passed.
- `uv run ruff format --check src/ tests/` -> passed.
- `uv run mypy src/` -> passed.
- `uv run python -m pytest -s tests/ -v --tb=short` -> `720 passed, 19 skipped`.
- `git diff --check` -> passed.
