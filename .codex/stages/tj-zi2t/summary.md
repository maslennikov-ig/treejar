# tj-zi2t Tail Closeout

Status: ready for delivery
Updated: 2026-05-12

## Scope

Review leftover branches/worktrees after the Noor CRM admin delivery, merge only safe work, preserve useful docs/research artifacts, and leave conflicting/stale work explicitly deferred.

## Integrated

- `codex/admin-light-theme-fix`: cherry-picked as a small admin UI fix for light-theme chart contrast, including frontend regression coverage.
- `codex/admin-owner-acceptance-checklist`: cherry-picked docs-only owner acceptance checklist.
- `codex/tester-primary-evidence-md`: cherry-picked docs-only client/tester evidence reports.

## Preserved Artifacts

- `.codex/project-index.md` restored from the stale orchestration project-index worktree as the stable repo navigation map.
- `docs/Research/Popular Bots Research/` preserved with AI sales assistant framework research.
- `docs/Research/Sales Playbook Research/` preserved with reusable B2B sales/support bot playbook research.
- `docs/client/github-issues-cheatsheet-ru.pdf` preserved from local output artifacts.

## Not Merged

- `codex/tj-final27-acceptance-integration` and child `tj-final27.4-.8` branches are not merged here because they conflict with current `origin/main` and require a dedicated rebase/integration stage.
- `codex/full-crm-admin` is not merged because its branch has no commits ahead of `origin/main` and the dirty worktree is stale relative to delivered admin work.
- `codex/orchestration-project-index-baseline` is not merged as a branch; only `.codex/project-index.md` was preserved.

## Verification

- `node frontend/admin/tests/light_theme_chart_regression.mjs` passed.
- `node frontend/admin/tests/crm_admin_static_regression.mjs` passed.
- `npm run lint --prefix frontend/admin` passed after `npm ci --prefix frontend/admin`.
- `npm run build --prefix frontend/admin` passed after `npm ci --prefix frontend/admin`.
- `PYTHONPATH=. uv run --extra dev python -m pytest tests/test_admin_dashboard_frontend.py -v --tb=short` passed: `11 passed`.
- `uv run --extra dev ruff check src/ tests/` passed.
- `uv run --extra dev ruff format --check src/ tests/` passed.
- `uv run --extra dev mypy src/` passed.
- `scripts/orchestration/run_process_verification.sh` passed.
- `PYTHONPATH=. uv run --extra dev python -m pytest tests/ -v --tb=short` passed: `955 passed, 19 skipped`.
