# Code Review: tj-ruue.2 Orchestrator Follow-up

**Date**: 2026-04-21
**Scope**: Follow-up review of uncommitted `codex/tj-ruue-llm-attempt-state` after worker self-review fixes
**Files**: LLM attempt state, QA cron integrations, migration, focused tests

## Summary

|              | Critical | High | Medium | Low |
| ------------ | -------- | ---- | ------ | --- |
| Issues       | 0        | 2    | 2      | 0   |
| Improvements | -        | 0    | 0      | 0   |

**Verdict**: NEEDS WORK

The worker-fixed findings in `CR-2026-04-21-tj-ruue-llm-attempt-state.md` are addressed, but follow-up review found four additional risks. Context7 docs were checked for SQLAlchemy 2.0 `AsyncSession` failure handling and redis-py locking primitives. SQLAlchemy guidance requires rollback after failed flush/commit before session reuse; redis-py supports expiring keys and lock ownership patterns, so token-checked release after post-lock DB failure should be handled inside `begin_llm_attempt()`.

## Issues

### High

#### 1. Terminal success can block delivery retry

- **File**: `src/quality/job.py:341`
- **Problem**: Red-flag and final-review jobs record a terminal LLM `success` before Telegram notification and Redis marker writes. `begin_llm_attempt()` then skips terminal statuses in `src/llm/attempts.py:239`, so a notification/marker failure can permanently suppress downstream delivery retry for the same logical key.
- **Impact**: The new cache avoids repeat LLM spend, but can lose the QA notification or final marker. Subsequent cron runs skip the LLM attempt and do not replay delivery from `result_json`.
- **Fix**: Separate LLM result caching from delivery state. If a terminal success exists but the delivery marker is missing, retry notification/marker from persisted `result_json` or the saved review without calling the LLM again.

#### 2. Persistence failures can become terminal LLM failures

- **File**: `src/quality/job.py:468`
- **Problem**: Final review catches `evaluate_conversation()` and `save_review()` in the same attempt-error block. Manager review similarly wraps `evaluate_manager_conversation()`, `save_manager_review()`, and success recording. Generic persistence exceptions can be classified as `failed_final` by `record_llm_attempt_error()`.
- **Impact**: A DB/materialization failure can block future retries for the same logical key even when the LLM call itself succeeded, or when the failure was unrelated to model behavior.
- **Fix**: Only pass actual evaluator/LLM exceptions to `record_llm_attempt_error()`. Handle review persistence failures after rollback in a separate retry path, ideally by materializing from cached result data rather than re-calling the model.

### Medium

#### 3. Final and manager keys do not cover transcript updates

- **File**: `src/quality/job.py:68`
- **Problem**: Red flags now use latest assistant activity for the logical key, but final review still keys on `Conversation.updated_at` and manager review keys on `Escalation.updated_at`/`created_at`, while both evaluators read message transcripts.
- **Impact**: If message inserts do not bump the parent row timestamp, a terminal success/no-action/manual state can suppress evaluation after later relevant messages.
- **Fix**: Include latest relevant transcript activity in final/manager logical keys and input hashes, or guarantee that message writes bump the parent timestamps.

#### 4. Redis lock leaks until TTL on begin DB failure

- **File**: `src/llm/attempts.py:251`
- **Problem**: `begin_llm_attempt()` acquires the Redis lock before DB flush/commit. If DB mutation or commit raises before a lease is returned, callers cannot release the lock because `lease` remains `None`.
- **Impact**: The logical attempt is blocked until lock TTL expires and the session cleanup path owns rollback implicitly. This is usually bounded by TTL, but it creates avoidable cron stalls and noisy failure behavior.
- **Fix**: Wrap post-lock DB work in `try/except`; on exception, rollback and token-release the Redis lock before re-raising. Handle uniqueness races cleanly by re-querying or returning a skip.

## Positive Patterns

- DB and Redis state now prevent the original runaway cron loop for terminal outcomes.
- Existing fixes correctly use DB `next_retry_at` as durable retry truth and avoid rewriting attempt state after commit failure.
- Red-flag keys now include latest assistant activity, matching the worker's accepted review finding.

## Validation

- Context7: SQLAlchemy 2.0 `AsyncSession` rollback/commit guidance checked.
- Context7: redis-py lock/SETEX/Lua eval patterns checked.
- Independent review subagent confirmed the same four follow-up risks.
- No new verification run in this report; fixes and regression tests are required before accepting `tj-ruue.2`.
