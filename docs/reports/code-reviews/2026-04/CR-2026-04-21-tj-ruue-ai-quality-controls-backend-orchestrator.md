# Code Review: tj-ruue.3 AI Quality Controls Backend

**Date**: 2026-04-21
**Scope**: Orchestrator review of uncommitted `codex/tj-ruue-ai-quality-controls-backend`
**Files**: Admin API, AI Quality Controls config, QA cron integrations, evaluator model routing, focused tests

## Summary

|              | Critical | High | Medium | Low |
| ------------ | -------- | ---- | ------ | --- |
| Issues       | 0        | 1    | 0      | 0   |
| Improvements | -        | 0    | 0      | 0   |

**Verdict**: PASS after fix

The worker implementation correctly added conservative disabled defaults, admin GET/PUT/PATCH config endpoints, risky override validation, QA model propagation, and scheduled-mode gating. Context7 was checked for Pydantic v2 model validators; the implementation's `Field` bounds plus `model_validator(mode="after")` approach matches current Pydantic guidance.

## Issues

### High

#### 1. Daily controls were per-run only

- **File**: `src/quality/config.py:244`
- **Problem**: `daily_sample` and `max_calls_per_day` were represented in the backend config, but scheduled jobs only used `max_calls_per_run`/`max_calls_per_day` as a per-run candidate cap. A 30-minute cron could still execute a `daily_sample` scope repeatedly across the day.
- **Impact**: Admins could enable a mode that appears cost-bounded while the worker continues to spend on every cron tick.
- **Fix**: Added Redis UTC-day reservations for `daily_sample`, Redis daily call counters for `max_calls_per_day`, safe fallback to disabled defaults for invalid injected config, and wired those gates into bot QA, red flags, and manager QA jobs. Regression task: `tj-ruue.3.1`.

## Positive Patterns

- Admin API writes full JSON replacements to `SystemConfig`, avoiding SQLAlchemy JSON in-place mutation tracking pitfalls.
- GLM-5 and full transcript require explicit warning overrides before persistence.
- Disabled/manual modes now return before candidate scans, so default QA automation performs zero scheduled LLM calls.
- Configured QA model names are carried into evaluator calls and LLM attempt metadata.

## Validation

- Context7: Pydantic v2 `model_validator(mode="after")` and `ValueError` validation behavior checked.
- `uv run --extra dev python -m pytest -s tests/test_quality_job.py tests/test_manager_job.py tests/test_api_admin.py tests/test_quality_evaluator.py tests/test_manager_evaluator.py -q` -> 87 passed, 3 skipped.
- `npm ci` in `frontend/admin` -> passed; npm reported existing audit findings, not addressed in this backend review.
- `uv run python -m pytest -s tests/ -v --tb=short` -> 703 passed, 19 skipped.
- `uv run ruff check src/ tests/` -> passed.
- `uv run ruff format --check src/ tests/` -> passed.
- `uv run mypy src/` -> passed.
- `git diff --check` -> passed.
