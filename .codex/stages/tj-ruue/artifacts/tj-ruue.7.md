---
task_id: tj-ruue.7
stage_id: tj-ruue
repo: treejar
branch: codex/tj-ruue-frontend-ai-quality-controls
base_branch: codex/live-triage-20260417
base_commit: 23f3784
worktree: /home/me/code/treejar/.worktrees/codex-tj-ruue-frontend-ai-quality-controls
status: returned
verification:
  - npm ci in frontend/admin: passed
  - npm run lint in frontend/admin: passed
  - npm run build in frontend/admin: passed
  - uv run --extra dev python -m pytest -s tests/test_admin_dashboard_frontend.py tests/test_api_admin.py -q: passed
  - uv run ruff check src/ tests/: passed
  - uv run ruff format --check src/ tests/: passed
  - uv run mypy src/: passed
  - uv run pytest tests/ -v --tb=short: failed
  - uv run --extra dev python -m pytest -s tests/ -v --tb=short: passed
  - uv run python scripts/orchestration/validate_artifact.py .codex/stages/tj-ruue/artifacts/tj-ruue.7.md: passed
  - git diff --check: passed
changed_files:
  - .codex/stages/tj-ruue/artifacts/tj-ruue.7.md
  - docs/reports/code-reviews/2026-04/CR-2026-04-22-tj-ruue-frontend-ai-quality-controls-orchestrator.md
  - frontend/admin/src/api/operators.ts
  - frontend/admin/src/components/AIQualityControlsPanel.tsx
  - frontend/admin/src/components/OperatorCenter.tsx
  - frontend/admin/src/types/operators.ts
  - frontend/admin/tests/ai_quality_controls_api_regression.mjs
  - frontend/admin/tests/ai_quality_controls_dashboard_regression.mjs
  - tests/test_admin_dashboard_frontend.py
---

# Summary

Added the admin dashboard UI for AI Quality Controls inside the existing
Operator Center surface.

The panel reads and saves the existing backend contract at
`/api/v1/admin/ai-quality-controls` using PATCH payloads shaped by scope
(`bot_qa`, `manager_qa`, `red_flags`). It exposes mode, transcript mode, model,
daily budget, max calls per run/day, retry attempts/backoff, cache telemetry,
alert-on-failure, risky override acknowledgements, and criteria toggles when a
scope has criteria JSON.

The UI renders backend warnings for full transcript and GLM-5 overrides, shows a
clear zero-automation safe default when all scopes are disabled, and includes
tooltip help for mode cost/risk, full transcript risk, GLM-5 cost, budget/call
caps, retry cost, cache telemetry, and failure alerts.

Manual trigger surfaces only reference existing backend endpoints: bot QA can be
run through the existing internal quality review endpoint with an explicit
conversation ID, manager QA continues to use the existing admin Manager Review
Queue Evaluate action, and red flags explicitly show that no admin manual trigger
endpoint currently exists.

Orchestrator review found and fixed one frontend/backend contract mismatch:
GLM-5 warning detection now matches both `glm-5` and `glm5`, aligned with the
backend validator. Review report:
`docs/reports/code-reviews/2026-04/CR-2026-04-22-tj-ruue-frontend-ai-quality-controls-orchestrator.md`.

# Verification

- `npm ci` in `frontend/admin` -> passed with existing Node 18 engine warnings
  for current Vite/Tailwind packages and existing npm audit findings.
- `npm run lint` in `frontend/admin` -> passed.
- `npm run build` in `frontend/admin` -> passed after locally installing the
  missing optional Tailwind native package with
  `npm install --no-save @tailwindcss/oxide-linux-x64-gnu@4.2.1`; no package
  metadata changed.
- `uv run --extra dev python -m pytest -s tests/test_admin_dashboard_frontend.py tests/test_api_admin.py -q`
  -> passed, `20 passed, 3 skipped`.
- `uv run ruff check src/ tests/` -> passed.
- `uv run ruff format --check src/ tests/` -> passed.
- `uv run mypy src/` -> passed.
- `uv run pytest tests/ -v --tb=short` -> failed before test collection because
  pytest capture hit `FileNotFoundError` for the tmpfile in this environment.
- `uv run --extra dev python -m pytest -s tests/ -v --tb=short` -> passed,
  `737 passed, 19 skipped`.
- `uv run python scripts/orchestration/validate_artifact.py .codex/stages/tj-ruue/artifacts/tj-ruue.7.md`
  -> passed.
- `git diff --check` -> passed.
- Orchestrator review rerun:
  - `node frontend/admin/tests/ai_quality_controls_dashboard_regression.mjs`
    -> passed.
  - `node frontend/admin/tests/ai_quality_controls_api_regression.mjs`
    -> passed.
  - `uv run --extra dev python -m pytest -s tests/test_admin_dashboard_frontend.py -q`
    -> passed, `5 passed`.
  - `npm run lint` in `frontend/admin` -> passed.
  - `npm run build` in `frontend/admin` -> passed.

# Risks / Follow-ups / Explicit Defers

- This task does not add new backend manual trigger APIs. The red-flag manual
  surface is intentionally informational until backend exposes a reviewed admin
  endpoint.
- `npm ci` under the available Node 18 runtime did not install the Tailwind
  optional native binding automatically; the build passed after a local no-save
  install of the existing lockfile optional package. A Node >=20 runtime should
  avoid this local recovery step.
- No commit, push, deploy, staging mutation, or production mutation was done.
