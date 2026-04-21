# Code Review: tj-ruue.2 LLM Attempt State

**Date**: 2026-04-21  
**Scope**: Uncommitted DB+Redis LLM attempt/cache state changes in `codex/tj-ruue-llm-attempt-state`  
**Files**: 10 changed files plus review artifact  

## Summary

|              | Critical | High | Medium | Low |
| ------------ | -------- | ---- | ------ | --- |
| Issues       | 0        | 3    | 0      | 0   |
| Improvements | -        | 0    | 2      | 1   |

**Initial Verdict**: NEEDS WORK  
**Resolution**: ADDRESSED in `codex/tj-ruue-llm-attempt-state`

## Resolution Notes

- `tj-ruue.2.1` fixed by making DB `next_retry_at` the source of truth for due retry decisions and adding Redis-failure regression coverage.
- `tj-ruue.2.2` fixed by rolling back failed transactions before attempt-error writes and by keeping success/no-action commit failures out of attempt-error classification.
- `tj-ruue.2.3` fixed by carrying latest assistant activity into red-flag candidates and using it as the red-flag logical attempt key.

## Issues

### High

#### 1. Redis-read failure can freeze a due retry

- **File**: `src/llm/attempts.py:163`
- **Problem**: If Redis `get()` fails after DB backoff has already expired, `_backoff_is_active()` returns `attempt.next_retry_at is not None`, which is still `True` for an expired retry timestamp.
- **Impact**: A transient Redis read failure can prevent a `failed_retryable` attempt from ever retrying, despite DB state saying the retry is due.
- **Fix**: Treat DB `next_retry_at` as the durable source of truth. After the DB timestamp is due, Redis read failure should not keep the attempt blocked.

#### 2. Commit failures are handled with the same failed session

- **File**: `src/quality/job.py:289`
- **Problem**: The job records `success`/`no_action` and commits inside a `try` whose `except` then writes `record_llm_attempt_error()` using the same `AsyncSession`. The same pattern exists in `src/quality/job.py:442` and `src/quality/manager_job.py:199`.
- **Impact**: If commit fails, SQLAlchemy requires rollback before further use. Attempting to flush an error state in the failed transaction can raise again and leave DB/Redis coordination inconsistent.
- **Fix**: Wrap the LLM-call phase so failed commits are rolled back before any fallback write, or only classify the actual LLM/evaluator call as attempt error and let commit failures fail the job after rollback.

#### 3. Red-flag attempt key can miss new assistant messages

- **File**: `src/quality/job.py:214`
- **Problem**: Red-flag candidates are selected by latest assistant `Message.created_at`, but the attempt key uses `Conversation.updated_at`. The message write path does not guarantee that adding a new message bumps `Conversation.updated_at`.
- **Impact**: A previous `no_action` or `success` terminal attempt can suppress red-flag scanning for a later assistant reply if the conversation row timestamp did not change.
- **Fix**: Include the latest assistant activity timestamp in the red-flag logical attempt key, while keeping final-review keys based on conversation update time.

## Improvements

### Medium

#### 1. Add explicit Redis-failure retry regression coverage

- **File**: `tests/test_llm_attempts.py`
- **Current**: Tests cover active backoff, but not Redis read failure after DB backoff expiry.
- **Recommended**: Add a test where `next_retry_at` is in the past, Redis `get()` raises, and `begin_llm_attempt()` still starts a retry.

#### 2. Add attempt-key regression coverage for red-flag activity timestamps

- **File**: `tests/test_quality_job.py`
- **Current**: Job tests use a single `updated_at` field, so they do not catch message activity diverging from conversation update time.
- **Recommended**: Add a red-flag job test asserting `begin_llm_attempt(entity_updated_at=latest_assistant_activity_at)`.

### Low

#### 1. Keep status definitions from drifting

- **File**: `src/models/llm_attempt.py:21`
- **Current**: Status literals are defined in both `src.models.llm_attempt` and `src.llm.attempts`.
- **Recommended**: In a future cleanup, derive one from the other or add a unit assertion that both lists stay in sync.

## Positive Patterns

- The status set and DB `CheckConstraint` cover all required task statuses.
- Terminal status handling prevents repeated LLM calls for `success`, `no_action`, `failed_final`, `budget_blocked`, and `needs_manual_review`.
- Redis lock acquisition uses `SET NX` with TTL, and lock release is token-checked rather than a blind `DEL`.
- The migration revision id fits the repository's Alembic version-column constraint.

## Escalation

- Database schema changes and cron billing behavior should be reviewed by the stage orchestrator before merge.

## Validation Notes

- Prior worker verification passed targeted pytest, `ruff check`, `ruff format --check`, `mypy`, artifact validation, and `git diff --check`.
- This review identified additional failure-path coverage gaps and one red-flag logical-key regression not covered by the original targeted tests.
