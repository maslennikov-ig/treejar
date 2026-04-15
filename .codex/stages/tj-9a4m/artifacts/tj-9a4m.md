---
task_id: tj-9a4m
stage_id: tj-9a4m
repo: treejar
branch: codex/tj-9a4m-audit-admin
base_branch: main
base_commit: 64fd98c2a7b2a5ff7abbfc761b1713654610e4a5
worktree: /Users/igor/code/treejar-tj-9a4m
status: accepted_and_integrated
verification:
  - git pull --rebase: passed
  - uv run ruff check src/ tests/: passed
  - uv run ruff format --check src/ tests/: passed
  - uv run mypy src/: passed
  - npm run lint: passed
  - npm run build: passed
  - env DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib uv run pytest tests/ -v --tb=short: passed (633 passed, 19 skipped)
  - scripts/orchestration/run_process_verification.sh: passed
  - python3 scripts/orchestration/validate_artifact.py .codex/stages/tj-9a4m/artifacts/tj-9a4m.md: passed
  - python3 scripts/orchestration/check_stage_ready.py tj-9a4m: passed
  - python3 scripts/orchestration/run_stage_closeout.py --stage tj-9a4m: passed
  - gh run view 24411947429 --json conclusion,status,headSha,url: passed (`success` on `main@fa47ec01424af79fe02ca8685e0b3d7573f4c561`)
  - uv run python scripts/verify_api.py --base-url https://noor.starec.ai: passed (7 passed, 0 failed)
  - python3 scripts/orchestration/cleanup_stage_workspace.py --stage tj-9a4m: passed
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

The stage was implemented in an isolated child worktree, reviewed findings-first, then merged into `main` via the stage branch `codex/tj-9a4m-audit-admin`. Final delivered closeout landed on `main@fa47ec01424af79fe02ca8685e0b3d7573f4c561`, after the CI test job dependency fix was integrated and the production delivery path was revalidated.

# Verification

- `git pull --rebase` -> passed
- `uv run ruff check src/ tests/` -> passed
- `uv run ruff format --check src/ tests/` -> passed
- `uv run mypy src/` -> passed
- `npm run lint` -> passed
- `npm run build` -> passed
- `env DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib uv run pytest tests/ -v --tb=short` -> `633 passed, 19 skipped`
- `scripts/orchestration/run_process_verification.sh` -> passed
- `python3 scripts/orchestration/validate_artifact.py .codex/stages/tj-9a4m/artifacts/tj-9a4m.md` -> passed
- `python3 scripts/orchestration/check_stage_ready.py tj-9a4m` -> passed
- `python3 scripts/orchestration/run_stage_closeout.py --stage tj-9a4m` -> passed
- `gh run view 24411947429 --json conclusion,status,headSha,url` -> passed (`success`)
- `uv run python scripts/verify_api.py --base-url https://noor.starec.ai` -> `7 passed, 0 failed`
- `python3 scripts/orchestration/cleanup_stage_workspace.py --stage tj-9a4m` -> passed

# Risks / Follow-ups / Explicit Defers

- Extended referrals admin/reporting remains intentionally deferred because `docs/tz.md` still marks it optional.
- Production delivery continues to use the canonical `main` push -> GitHub Actions deploy workflow into `/opt/noor`.
