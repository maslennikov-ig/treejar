---
task_id: tj-ruue.3
stage_id: tj-ruue
repo: treejar
branch: codex/tj-ruue-ai-quality-controls-backend
base_branch: codex/live-triage-20260417
base_commit: 124109f9198ab7cf2291446304ced68f14747f45
worktree: /home/me/code/treejar/.worktrees/codex-tj-ruue-ai-quality-controls-backend
status: returned
verification:
  - Context7 FastAPI docs query: passed
  - Context7 Pydantic docs query: passed
  - Context7 SQLAlchemy docs query: passed
  - uv run --extra dev python -m pytest -s tests/test_quality_job.py tests/test_manager_job.py tests/test_api_admin.py -q: passed
  - uv run --extra dev python -m pytest -s tests/test_quality_job.py tests/test_manager_job.py tests/test_api_admin.py tests/test_quality_evaluator.py tests/test_manager_evaluator.py -q: passed
  - npm ci in frontend/admin: passed
  - uv run python -m pytest -s tests/ -v --tb=short: passed
  - uv run ruff check src/ tests/: passed
  - uv run ruff format --check src/ tests/: passed
  - uv run mypy src/: passed
  - uv run python scripts/orchestration/validate_artifact.py .codex/stages/tj-ruue/artifacts/tj-ruue.3.md: passed
  - git diff --check: passed
changed_files:
  - .codex/handoff.md
  - .codex/stages/tj-ruue/artifacts/tj-ruue.3.md
  - docs/reports/code-reviews/2026-04/CR-2026-04-21-tj-ruue-ai-quality-controls-backend-orchestrator.md
  - src/api/v1/admin.py
  - src/quality/config.py
  - src/quality/evaluator.py
  - src/quality/job.py
  - src/quality/manager_evaluator.py
  - src/quality/manager_job.py
  - tests/test_api_admin.py
  - tests/test_manager_job.py
  - tests/test_quality_job.py
---

# Summary

Implemented SystemConfig-backed Admin AI Quality Controls for the three configured scopes: bot QA, manager QA, and red flags.

The new backend config schema stores JSON under `SystemConfig.key == "ai_quality_controls"` and exposes admin GET/PUT/PATCH routes at `/api/v1/admin/ai-quality-controls`. Defaults are conservative: every scope starts in `disabled`, transcript mode is `summary`, QA model defaults to the fast model, budgets are low, max calls are low, and retry attempts are bounded to one retry.

Validation rejects full-transcript mode without `full_transcript_warning_override`, rejects GLM-5 QA models without `glm5_warning_override`, bounds budget/call/retry settings, and returns warning metadata when risky overrides are explicitly enabled. PATCH now deep-merges partial updates instead of resetting unspecified scopes.

Cron entrypoints for final bot QA, red flags, and manager QA now read the AI Quality Controls run gate before candidate queries. `disabled` and `manual` modes perform zero scheduled LLM calls; scheduled/daily-sample modes cap LLM work by `max_calls_per_run`. The selected QA model is passed through to evaluator calls and attempt metadata.

Orchestrator review found one cost-control semantics gap: `daily_sample` and `max_calls_per_day` were initially represented but only enforced as per-run limits. This branch now reserves `daily_sample` once per UTC day per scope with Redis, consumes Redis daily call counters for bot QA/red-flags/manager-QA cron attempts, and falls back to safe disabled defaults when injected context config is invalid. Review report: `docs/reports/code-reviews/2026-04/CR-2026-04-21-tj-ruue-ai-quality-controls-backend-orchestrator.md`; Bead: `tj-ruue.3.1`.

Context7 docs facts recorded:

- FastAPI request body models are validated through Pydantic, invalid request data returns structured 422 validation errors, and typed body parameters become typed route arguments.
- Pydantic v2 supports `Field` constraints plus `model_validator(mode="after")` for cross-field validation; raising `ValueError` becomes validation failure metadata for API consumers.
- SQLAlchemy 2.0 JSON ORM columns do not detect in-place nested mutations unless mutable extensions such as `MutableDict` are used; assigning a replacement JSON structure triggers change detection. The implementation assigns a full replacement dict when saving config.

# Verification

Current local verification already run:

- Context7 FastAPI docs query: passed.
- Context7 Pydantic docs query: passed.
- Context7 SQLAlchemy docs query: passed.
- `uv run --extra dev python -m pytest -s tests/test_quality_job.py tests/test_manager_job.py tests/test_api_admin.py -q` -> passed, `49 passed, 3 skipped`.
- `uv run --extra dev python -m pytest -s tests/test_quality_job.py tests/test_manager_job.py tests/test_api_admin.py tests/test_quality_evaluator.py tests/test_manager_evaluator.py -q` -> passed, `87 passed, 3 skipped`.
- `npm ci` in `frontend/admin` -> passed; npm reported existing high-severity audit findings, not changed here.
- `uv run python -m pytest -s tests/ -v --tb=short` -> passed, `703 passed, 19 skipped`.
- `uv run ruff check src/ tests/` -> passed.
- `uv run ruff format --check src/ tests/` -> passed.
- `uv run mypy src/` -> passed, `Success: no issues found in 120 source files`.
- `uv run python scripts/orchestration/validate_artifact.py .codex/stages/tj-ruue/artifacts/tj-ruue.3.md` -> passed.
- `git diff --check` -> passed.

# Risks / Follow-ups / Explicit Defers

- Daily budget accounting is config-gated here, including zero-budget blocking, but detailed token/cost-based daily spend accounting remains part of the later model routing/cache telemetry work.
- Existing non-admin internal manual quality endpoints are not widened in this task; this backend slice provides config, validation, warning metadata, model propagation for QA jobs, and scheduled cron gating.
- No frontend UI, deploy, production mutation, commit, or push is included in this task.
