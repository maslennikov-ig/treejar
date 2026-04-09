# Code Review: quality-identity-alerts

**Date**: 2026-04-09  
**Scope**: branch `codex/quality-alert-identity-block` vs `origin/main`  
**Files**: 8 changed files | **Changes**: +633 / -102

## Summary

|              | Critical | High | Medium | Low |
| ------------ | -------- | ---- | ------ | --- |
| Issues       | 0        | 1    | 1      | 0   |
| Improvements | 0        | 1    | 1      | 0   |

**Verdict**: NEEDS WORK

## Issues

### High

#### 1. Default placeholder name bypasses CRM enrichment

- **File**: [`src/services/customer_identity.py:79`](/home/me/code/treejar/.worktrees/tj-quality-identity/src/services/customer_identity.py#L79)
- **File**: [`src/llm/engine.py:650`](/home/me/code/treejar/.worktrees/tj-quality-identity/src/llm/engine.py#L650)
- **Problem**: `resolve_owner_customer_name()` returns the conversation value immediately whenever it is non-empty, but the LLM path seeds conversations with `"Valued Customer"` when there is no real name. That means the new identity block will keep the generic fallback and never query CRM for the actual customer name.
- **Impact**: The main production path for unknown customers will still show a generic placeholder in Telegram, so the feature does not deliver the identity enrichment it advertises.
- **Fix**: Treat generic placeholders as missing values and fall through to cache/CRM lookup. Add a regression test that proves `"Valued Customer"` still triggers Zoho lookup and resolves to the CRM contact name.

### Medium

#### 2. Identity lookup is on the critical path and can suppress marker writes

- **File**: [`src/quality/job.py:217`](/home/me/code/treejar/.worktrees/tj-quality-identity/src/quality/job.py#L217)
- **File**: [`src/quality/job.py:302`](/home/me/code/treejar/.worktrees/tj-quality-identity/src/quality/job.py#L302)
- **File**: [`src/services/customer_identity.py:83`](/home/me/code/treejar/.worktrees/tj-quality-identity/src/services/customer_identity.py#L83)
- **Problem**: The new CRM/cache enrichment runs inside the same `try` block that owns notification dispatch and Redis marker persistence. `resolve_owner_customer_name()` currently lets Redis and CRM exceptions bubble out, so a transient outage aborts the whole candidate path before `redis.setex(...)` runs.
- **Impact**: A temporary Zoho or Redis failure now causes the same conversation to be reprocessed on every job tick. That can spam logs, repeatedly hit the failing dependency, and delay both realtime red flags and final reviews even though the notification body could safely fall back to `"не указано"`.
- **Fix**: Make identity enrichment best-effort. Catch cache/CRM errors inside the helper, return unknown placeholders, and ensure the Redis marker is written once the review has been saved and the send attempt has been made.

## Improvements

### Medium

#### 1. Add explicit regression coverage for placeholder and outage paths

- **Current**: Tests cover the happy path for CRM enrichment, but not the default placeholder name or dependency failures.
- **Recommended**: Add cases for `"Valued Customer"` and for Redis/CRM exceptions so the branch proves it fails open to unknown identity instead of skipping enrichment or reprocessing indefinitely.

### Low

#### 2. Centralize the placeholder-name policy

- **Current**: The fallback name lives in the LLM engine, while the identity helper has no explicit list of generic placeholders it should ignore.
- **Recommended**: Put the default conversation-name placeholders into a shared constant/helper so future fallback changes do not silently bypass enrichment again.

## Positive Patterns

- The identity block is factored into a dedicated helper and reused by all quality notification formatters, which keeps the message layout consistent.
- Candidate pagination is still preserved, so the new enrichment does not regress the existing batched job structure.
- The new message format keeps HTML escaping in place for user-facing fields.

## Validation

- Targeted pytest run: inconclusive in this environment. `uv run pytest tests/test_customer_identity.py tests/test_quality_job.py tests/test_telegram_notifications.py -v --tb=short` collected 0 items and then hit a pytest capture cleanup `FileNotFoundError`, so I did not get a reliable pass signal.
- Build/type-check: not run.

