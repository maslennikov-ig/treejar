# Code Review: quality-review-redesign

**Date**: 2026-04-05  
**Scope**: branch `codex/quality-review-redesign` vs `origin/main`  
**Files**: 14 changed files

## Summary

|              | Critical | High | Medium | Low |
| ------------ | -------- | ---- | ------ | --- |
| Issues       | 0        | 1    | 1      | 0   |
| Improvements | -        | 0    | 0      | 1   |

**Verdict**: NEEDS WORK

## Issues

### High

#### 1. API review endpoint bypasses stage-aware scoring

- **File**: `/home/me/code/treejar/.worktrees/codex-quality-review-redesign/src/api/v1/quality.py:77-80`
- **File**: `/home/me/code/treejar/.worktrees/codex-quality-review-redesign/src/quality/evaluator.py:349-361`
- **Problem**: `create_review()` calls `evaluate_conversation(body.conversation_id, db)` without passing `sales_stage`. In `evaluate_conversation()`, that means `sales_stage is None` and the code explicitly marks all 15 rules applicable. The worker path does pass `candidate.sales_stage`, so the same conversation can receive a different score depending on whether it is reviewed through the API or by the background job.
- **Impact**: API-triggered reviews will over-count late-stage rules like contact collection, closing, and next-contact planning for early-stage conversations. That makes the admin/manual path inconsistent with the new final-review logic and can produce materially different scores for the same dialogue.
- **Fix**: Load `Conversation.sales_stage` in the API route and pass it through to `evaluate_conversation()`, or move stage lookup into the evaluator so both worker and API paths share the same applicability logic. Add a regression test that verifies the API path produces the same block applicability as the worker path for an early-stage conversation.

### Medium

#### 2. Candidate selection is hard-capped at 50 and can silently skip active conversations

- **File**: `/home/me/code/treejar/.worktrees/codex-quality-review-redesign/src/quality/service.py:187-218`
- **File**: `/home/me/code/treejar/.worktrees/codex-quality-review-redesign/src/quality/service.py:234-259`
- **Problem**: Both new candidate queries apply `.limit(50)` with no pagination or cursor. Under normal load, the jobs only see the newest 50 matching conversations in the window. Any additional active conversations are silently dropped from evaluation in that run, and if the backlog remains above 50 they can be missed repeatedly.
- **Impact**: Realtime red flags and mature final reviews become non-deterministic under load. This is especially risky for the final-review job because omitted conversations may never be scored or alerted even though they are eligible.
- **Fix**: Process candidates in batches until the eligible set is exhausted, or store a cursor/checkpoint so every matching conversation is eventually visited. If a safety cap is still needed, make it explicit in config and log when the cap is hit.

## Improvements

### Low

#### 1. Admin guide still points operators at the old runtime path

- **File**: `/home/me/code/treejar/.worktrees/codex-quality-review-redesign/docs/admin-guide.md:130-190`
- **Current**: The incident/runbook snippets still tell operators to `cd /opt/treejar-prod`, even though the canonical runtime path elsewhere in the repo is `/opt/noor`.
- **Recommended**: Update the SSH/runbook commands to the canonical runtime path so incident response instructions match the live environment.

## Positive Patterns

- The branch added direct tests for the new final-review and red-flag flows, which makes the new behavior much easier to reason about.
- Legacy quality-review rows are still readable through the API schema, so the JSON shape change did not break backward compatibility.
- The new Telegram notifications are split into compact warning vs. richer owner-facing review formats, which is a clear UX improvement over the old single-score alert.

## Validation

- `uv run ruff check src tests/` — PASS
- `uv run mypy src` — PASS
- `pytest tests/test_api_quality.py tests/test_quality_evaluator.py tests/test_quality_job.py tests/test_telegram_notifications.py tests/test_worker.py -q` — PASS (`54 passed`)

## Conclusion

The redesign is directionally sound and the test coverage is materially better than before, but the branch still has two actionable gaps: the API path does not share the worker's stage-aware scoring, and the new jobs can skip work once candidate volume exceeds the fixed 50-row cap.
