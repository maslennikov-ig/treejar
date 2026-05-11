---
task_id: tj-admin-regression-fixes
stage_id: tj-final27
repo: treejar
branch: codex/admin-regression-fixes
base_branch: origin/main
base_commit: 79538a2fdc7ddd47d28519dcb87e815861353216
worktree: /home/me/code/treejar/.worktrees/codex-admin-regression-fixes
status: returned
verification:
  - uv run ruff check src/ tests/: passed
  - uv run ruff format --check src/ tests/: passed
  - uv run mypy src/: passed
  - uv run pytest tests/test_admin_knowledge_base_api.py tests/test_admin_crm_api.py tests/test_api_admin.py -v --tb=short: passed
  - node frontend/admin/tests/crm_admin_static_regression.mjs && node frontend/admin/tests/app_operator_center_regression.mjs: passed
  - npm run lint --prefix frontend/admin: passed
  - npm run build --prefix frontend/admin: passed
  - uv run pytest tests/ -v --tb=short: passed
changed_files:
  - frontend/admin/src/App.tsx
  - frontend/admin/src/api/crm.ts
  - frontend/admin/src/api/operators.ts
  - frontend/admin/src/types/crm.ts
  - frontend/admin/tests/app_operator_center_regression.mjs
  - frontend/admin/tests/crm_admin_static_regression.mjs
  - src/api/v1/admin.py
  - src/services/admin_crm.py
  - src/services/admin_knowledge_base.py
  - tests/test_admin_crm_api.py
  - tests/test_admin_knowledge_base_api.py
  - tests/test_api_admin.py
---

# Summary

Prepared local fixes for the Noor CRM admin production E2E regressions from run `20260511110724`.

- `tj-cin3`: KB soft-delete now binds the selected entry into the delete action, clears stale editor/list state, and reloads after the API delete.
- `tj-w9zr`: Auto-FAQ candidate approval now uses collision-safe KB titles and returns expected 409 conflicts instead of 500; reject is exposed from the admin UI and covered by API tests.
- `tj-qh8e`: Bot QA and Manager QA manual actions now honor Admin AI Quality Controls and show disabled/configuration feedback instead of implying success when backend review cannot run.
- `tj-wu6s`: the Support sidebar action now opens a simple internal support/help view instead of being a dead button.

# Verification

- `uv run ruff check src/ tests/`: passed.
- `uv run ruff format --check src/ tests/`: passed.
- `uv run mypy src/`: passed.
- `uv run pytest tests/test_admin_knowledge_base_api.py tests/test_admin_crm_api.py tests/test_api_admin.py -v --tb=short`: `35 passed, 3 skipped`.
- `node frontend/admin/tests/crm_admin_static_regression.mjs && node frontend/admin/tests/app_operator_center_regression.mjs`: passed.
- `npm run lint --prefix frontend/admin`: passed.
- `npm run build --prefix frontend/admin`: passed.
- `uv run pytest tests/ -v --tb=short`: `953 passed, 19 skipped`.

# Risks / Follow-ups / Explicit Defers

- No deploy, push, merge, or production mutation was performed.
- Repeat production smoke/regression remains pending after review, merge, deploy, and explicit authorization for production-mutating E2E.
- Existing broken disposable QA/FAQ candidates in production should be cleaned up only after the fix is deployed and a production cleanup action is explicitly authorized.
