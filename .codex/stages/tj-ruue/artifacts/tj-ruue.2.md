---
task_id: tj-ruue.2
stage_id: tj-ruue
repo: treejar
branch: codex/tj-ruue-llm-attempt-state
base_branch: codex/live-triage-20260417
base_commit: 10eb7690cb4c5fbe4fcbf26c7486a403ffb143c0
worktree: /home/me/code/treejar/.worktrees/codex-tj-ruue-llm-attempt-state
status: returned
verification:
  - uv run --extra dev python -m pytest -s tests/test_llm_attempts.py tests/test_quality_job.py tests/test_manager_job.py tests/test_migrations.py -q: passed
  - uv run ruff check src/ tests/: passed
  - uv run ruff format --check src/ tests/: passed
  - uv run mypy src/: passed
  - uv run python scripts/orchestration/validate_artifact.py .codex/stages/tj-ruue/artifacts/tj-ruue.2.md: passed
  - uv run python -m pytest -s tests/ -v --tb=short: passed
  - git diff --check: passed
changed_files:
  - .codex/stages/tj-ruue/artifacts/tj-ruue.2.md
  - docs/reports/code-reviews/2026-04/CR-2026-04-21-tj-ruue-llm-attempt-state.md
  - docs/reports/code-reviews/2026-04/CR-2026-04-21-tj-ruue-llm-attempt-state-orchestrator.md
  - migrations/versions/2026_04_21_add_llm_attempts.py
  - src/llm/attempts.py
  - src/models/__init__.py
  - src/models/llm_attempt.py
  - src/quality/job.py
  - src/quality/manager_job.py
  - src/quality/service.py
  - tests/test_llm_attempts.py
  - tests/test_manager_job.py
  - tests/test_quality_job.py
---

# Summary

Added DB-backed LLM attempt/cache state for expensive QA jobs. The new
`llm_attempts` model and migration store logical attempt keys, statuses, retry
state, model/provider metadata, token/cost fields, result JSON, and errors.

Added `src.llm.attempts` with required status validation, Redis `SET NX` lock
acquisition with TTL, token-safe Lua lock release, DB retry backoff plus Redis
backoff markers, and terminal status handling. Integrated it into mature final
quality review, realtime red flags, and manager evaluation cron jobs. Red-flag
scans now persist `no_action` when no flags are found.

Ran a post-implementation code review and captured it in
`docs/reports/code-reviews/2026-04/CR-2026-04-21-tj-ruue-llm-attempt-state.md`.
Review findings were tracked as Beads `tj-ruue.2.1`, `tj-ruue.2.2`, and
`tj-ruue.2.3`; all three were fixed and closed with regression coverage.

Orchestrator follow-up review captured four additional issues in
`docs/reports/code-reviews/2026-04/CR-2026-04-21-tj-ruue-llm-attempt-state-orchestrator.md`
and tracked them as `tj-ruue.2.4` through `tj-ruue.2.7`.

Follow-up fixes add replay paths for terminal successful QA attempts whose
Telegram/Redis delivery did not complete. Realtime red flags and final reviews
can now replay downstream delivery from persisted `result_json` or saved review
without another LLM call. Final and manager attempt keys now account for latest
relevant transcript activity, and DB persistence failures after a successful LLM
call are not misclassified as terminal model failures. `begin_llm_attempt()` now
rolls back and token-releases the Redis lock when DB work fails after lock
acquisition.

# Verification

- `uv run --extra dev python -m pytest -s tests/test_quality_job.py tests/test_manager_job.py tests/test_llm_attempts.py tests/test_migrations.py -q` -> passed, `45 passed`.
- `uv run ruff check src/ tests/` -> passed.
- `uv run ruff format --check src/ tests/` -> passed.
- `uv run mypy src/` -> passed, `Success: no issues found in 119 source files`.
- `uv run python scripts/orchestration/validate_artifact.py .codex/stages/tj-ruue/artifacts/tj-ruue.2.md` -> passed.
- `git diff --check` -> passed.
- `uv run python -m pytest -s tests/ -v --tb=short` -> passed after local `npm ci` in `frontend/admin`, `689 passed, 19 skipped`.

# Risks / Follow-ups / Explicit Defers

- Token/cost columns are present, but the existing evaluator APIs return only
  structured outputs, not provider usage objects. Populating detailed token and
  cost fields should be handled by the model routing/cache telemetry task.
- Admin AI Quality Controls config, daily budget accounting, frontend controls,
  summary transcript builder, and production scheduler changes are explicitly
  out of scope for this task.
- Existing Redis notification markers remain for backward-compatible alert
  suppression; DB attempt state is the durable LLM-call guard.
