# Code Review: Daily Summary Follow-up

**Date**: 2026-04-04
**Scope**: Review of commit `19ef73c` (`fix: make daily summary metrics honest`)
**Files**: 11 | **Changes**: +525 / -64

## Summary

|              | Critical | High | Medium | Low |
| ------------ | -------- | ---- | ------ | --- |
| Issues       | 0        | 1    | 1      | 0   |
| Improvements | —        | 0    | 0      | 0   |

**Verdict**: NEEDS WORK

## Issues

### High

#### 1. Refreshed quality reviews disappear from period-based analytics

- **File**: `src/quality/service.py:62`
- **Problem**: `save_review()` now updates an existing `QualityReview` row in place, but downstream period analytics in `src/services/reports.py:101` and `src/services/dashboard_metrics.py:187` still filter by `QualityReview.created_at`.
- **Impact**: Once a conversation's review is refreshed by the rolling evaluator, weekly/monthly quality averages can silently miss it if the row was originally created outside the reporting window. This makes the new rolling evaluator inconsistent with the rest of the reporting surface.
- **Fix**: Stop using `QualityReview.created_at` as the period filter for refreshed quality metrics. Use assistant-activity window semantics for report/dashboard quality averages, or add a dedicated refresh timestamp and query that instead.

### Medium

#### 2. Rolling quality alerts will spam Telegram for the same bad conversation

- **File**: `src/quality/job.py:43`
- **Problem**: `evaluate_recent_conversations_quality()` reevaluates recent conversations every run and unconditionally sends `notify_quality_alert()` whenever the score is below threshold.
- **Impact**: A single low-scoring active conversation can trigger repeated Telegram alerts every 30 minutes for up to 24 hours, while also wasting LLM calls on repeated notifications for the same state.
- **Fix**: Gate notifications so an alert is sent only when the score newly crosses below threshold or when a previously alerted conversation recovers and regresses again.

## Positive Patterns

- The dedicated daily summary calculator cleanly decouples Telegram reporting from the broader dashboard payload.
- `Conversion Rate (7d)` and `Avg Quality` now render `N/A` instead of false zeroes, which is a clear product improvement.
- The review-upsert direction is correct; the main gap is aligning the rest of the analytics stack with that new lifecycle.

## Escalation

- None.

## Validation

- Ruff: PASS
- Mypy: PASS
- Pytest: PASS (`uv run pytest -s tests/ -v --tb=short` in this environment; plain captured pytest currently fails inside pytest's own capture layer with `FileNotFoundError`)
