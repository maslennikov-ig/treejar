---
task_id: tj-9a4m
stage_id: tj-9a4m
repo: treejar
branch: codex/tj-9a4m-audit-admin
base_branch: main
base_commit: 64fd98c2a7b2a5ff7abbfc761b1713654610e4a5
worktree: /Users/igor/code/treejar-tj-9a4m
status: merged
verification:
  - git pull --rebase: passed
  - uv run ruff check src/ tests/: passed
  - uv run ruff format --check src/ tests/: passed
  - uv run mypy src/: passed
  - npm run lint: passed
  - npm run build: passed
  - env DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib OPENROUTER_API_KEY=test-key WAZZUP_API_KEY=fake-wazzup-key WAZZUP_API_URL=http://fake-wazzup-url LOGFIRE_IGNORE_NO_CONFIG=1 uv run pytest tests/ -v --tb=short: passed (631 passed, 19 skipped)
  - scripts/orchestration/run_process_verification.sh: passed
  - python3 scripts/orchestration/validate_artifact.py .codex/stages/tj-9a4m/artifacts/tj-9a4m.md: passed
  - python3 scripts/orchestration/check_stage_ready.py tj-9a4m: passed
  - python3 scripts/orchestration/run_stage_closeout.py --stage tj-9a4m: passed
changed_files:
  - .codex/orchestrator.toml
  - .codex/handoff.md
  - .github/workflows/ci.yml
  - .codex/stages/tj-9a4m/artifacts/tj-9a4m.md
  - .codex/stages/tj-9a4m/summary.md
  - README.md
  - docs/admin-guide.md
  - docs/architecture.md
  - docs/dev-guide.md
  - docs/metrics.md
  - docs/testing-guide-stage1.md
  - frontend/admin/src/App.tsx
  - frontend/admin/src/api/operators.ts
  - frontend/admin/src/components/OperatorCenter.tsx
  - frontend/admin/src/types/metrics.ts
  - frontend/admin/src/types/operators.ts
  - frontend/admin/tests/app_operator_center_regression.mjs
  - src/api/admin/auth.py
  - src/api/admin/views.py
  - src/api/v1/admin.py
  - src/api/v1/products.py
  - src/main.py
  - src/schemas/__init__.py
  - src/schemas/admin.py
  - src/services/dashboard_metrics.py
  - tests/conftest.py
  - tests/test_admin_dashboard_frontend.py
  - tests/test_admin_views_localization.py
  - tests/test_api_admin.py
  - tests/test_api_products.py
  - tests/test_dashboard_manager.py
---

# Summary

This stage audited and aligned the admin panel with the current Treejar runtime. It removed the split auth/session boundary between SQLAdmin and the dashboard/admin API, protected operational endpoints behind the shared admin session, expanded SQLAdmin/runtime model coverage, aligned dashboard manager/feedback metrics across backend/frontend/docs, and introduced an operator center for the admin session surface.

The stage was implemented in an isolated child worktree, reviewed findings-first, then merged locally into `main@84f016614750ad0d3dd52c8cdbe4733c3c4d88e0` via the stage branch `codex/tj-9a4m-audit-admin`.

# Verification

- `git pull --rebase` -> passed
- `uv run ruff check src/ tests/` -> passed
- `uv run ruff format --check src/ tests/` -> passed
- `uv run mypy src/` -> passed
- `npm run lint` -> passed
- `npm run build` -> passed
- `env DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib OPENROUTER_API_KEY=test-key WAZZUP_API_KEY=fake-wazzup-key WAZZUP_API_URL=http://fake-wazzup-url LOGFIRE_IGNORE_NO_CONFIG=1 uv run pytest tests/ -v --tb=short` -> `631 passed, 19 skipped`
- `scripts/orchestration/run_process_verification.sh` -> passed
- `python3 scripts/orchestration/validate_artifact.py .codex/stages/tj-9a4m/artifacts/tj-9a4m.md` -> passed
- `python3 scripts/orchestration/check_stage_ready.py tj-9a4m` -> passed
- `python3 scripts/orchestration/run_stage_closeout.py --stage tj-9a4m` -> passed

# Risks / Follow-ups / Explicit Defers

- Extended referrals admin/reporting remains intentionally deferred because `docs/tz.md` still marks it optional.
- Production delivery should continue to use the canonical `main` push -> GitHub Actions deploy workflow into `/opt/noor`.
