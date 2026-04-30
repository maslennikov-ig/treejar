---
task_id: tj-final27.6
stage_id: tj-final27
repo: treejar
branch: codex/tj-final27-5-6-feedback-referrals
base_branch: main
base_commit: 10e128fab6958186dcfed079fa2e360129e5d43f
worktree: /home/me/code/treejar/.worktrees/codex-tj-final27-5-6-feedback-referrals
status: returned
verification:
  - uv run --extra dev python -m pytest -s tests/test_feedback_model.py tests/test_feedback_integration.py tests/test_dashboard_manager.py tests/test_services_followup.py tests/test_referrals.py -q: passed
  - uv run ruff check src/ tests/: passed
  - uv run ruff format --check src/ tests/: passed
  - uv run mypy src/: passed
  - git diff --check: passed
  - npm --prefix frontend/admin run lint: passed
  - npm --prefix frontend/admin run build: passed
changed_files:
  - src/services/referrals.py
  - src/api/v1/referrals.py
  - src/llm/engine.py
  - src/api/v1/admin.py
  - frontend/admin/src/components/OperatorCenter.tsx
  - frontend/admin/src/api/operators.ts
  - frontend/admin/src/types/operators.ts
  - tests/test_referrals.py
  - docs/client/final-feedback-referrals-acceptance.md
---

# Summary

No approved referral policy was found in repo docs/config, so referrals were not launched. The default referral policy is `client_decision_required`, disabled, and not approved. Protected referral API endpoints and LLM referral tools now read the policy before generating or applying codes; with default settings they return a customer-visible client-decision/manager-confirmation message and do not apply discounts. Operator Center exposes the policy status through the protected admin API.

Docs used: Context7 FastAPI `/fastapi/fastapi` for router-level admin dependencies; Context7 SQLAlchemy `/websites/sqlalchemy_en_20` for async `execute`/`scalar` config reads; Context7 React `/reactjs/react.dev` for useEffect stale-update cleanup; Context7 pytest `/pytest-dev/pytest` for focused assertion patterns.

# Verification

- RED: targeted pytest first failed on missing feedback candidate implementation; referral tests were added before policy gating implementation.
- GREEN: `uv run --extra dev python -m pytest -s tests/test_feedback_model.py tests/test_feedback_integration.py tests/test_dashboard_manager.py tests/test_services_followup.py tests/test_referrals.py -q` -> `55 passed`.
- `uv run ruff check src/ tests/` -> passed.
- `uv run ruff format --check src/ tests/` -> passed.
- `uv run mypy src/` -> passed.
- `git diff --check` -> passed.
- `npm --prefix frontend/admin run lint` -> passed.
- `npm --prefix frontend/admin run build` -> passed after installing ignored local frontend dependencies; npm reported Node 18 engine warnings during dependency install for packages that require Node 20, but lint/build completed.

# Risks / Follow-ups / Explicit Defers

- Referral launch remains explicitly deferred pending client approval of discount, eligibility, expiry, abuse, reporting, and live E2E rules.
- The low-level referral service remains available for future approved-policy implementation and existing internal tests; launched API/LLM callers are policy-gated.
- No live referral branch, production mutation, or discount application was run.
