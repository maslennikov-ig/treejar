---
schema_version: orchestration-artifact/v1
task_id: tj-final27.5
stage_id: tj-final27
repo: treejar
branch: codex/tj-final27-5-6-feedback-referrals
base_branch: main
base_commit: 10e128fab6958186dcfed079fa2e360129e5d43f
worktree: /home/me/code/treejar/.worktrees/codex-tj-final27-5-6-feedback-referrals
status: merged
delivery_method: manual integration
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: Accepted content is preserved in main; source branch/worktree cleanup is complete or no longer applicable.
risk_level: medium
verification:
  - uv run --extra dev python -m pytest -s tests/test_feedback_model.py tests/test_feedback_integration.py tests/test_dashboard_manager.py tests/test_services_followup.py tests/test_referrals.py -q: passed
  - uv run ruff check src/ tests/: passed
  - uv run ruff format --check src/ tests/: passed
  - uv run mypy src/: passed
  - git diff --check: passed
  - npm --prefix frontend/admin run lint: passed
  - npm --prefix frontend/admin run build: passed
changed_files:
  - src/services/followup.py
  - src/llm/engine.py
  - src/services/dashboard_metrics.py
  - src/schemas/admin.py
  - src/api/v1/admin.py
  - frontend/admin/src/components/OperatorCenter.tsx
  - frontend/admin/src/api/operators.ts
  - frontend/admin/src/types/operators.ts
  - tests/test_feedback_model.py
  - tests/test_feedback_integration.py
  - tests/test_dashboard_manager.py
  - tests/test_services_followup.py
  - docs/client/final-feedback-referrals-acceptance.md
explicit_defers:
  - none
---

# Summary

Post-delivery feedback is now acceptance-visible and context-gated. Delivered active order conversations produce a single deterministic feedback request candidate, feedback sends use audited deterministic `crmMessageId`, sent/skipped state is recorded in conversation metadata for dedupe, and `save_feedback` rejects non-delivery/non-feedback contexts. The admin dashboard metrics payload now includes recent feedback rows, and Operator Center reads them through the protected admin API.

Docs used: Context7 FastAPI `/fastapi/fastapi` for router dependencies and dependency `HTTPException`; Context7 SQLAlchemy `/websites/sqlalchemy_en_20` for async `execute`/`scalar` patterns; Context7 React `/reactjs/react.dev` for useEffect stale-update cleanup; Context7 pytest `/pytest-dev/pytest` for `raises`/monkeypatch patterns.

# Verification

- RED: targeted pytest first failed on missing `build_feedback_request_candidate`.
- GREEN: `uv run --extra dev python -m pytest -s tests/test_feedback_model.py tests/test_feedback_integration.py tests/test_dashboard_manager.py tests/test_services_followup.py tests/test_referrals.py -q` -> `55 passed`.
- `uv run ruff check src/ tests/` -> passed.
- `uv run ruff format --check src/ tests/` -> passed after formatting `src/services/followup.py`.
- `uv run mypy src/` -> passed.
- `git diff --check` -> passed.
- `npm --prefix frontend/admin run lint` -> passed.
- `npm --prefix frontend/admin run build` -> passed after installing ignored local frontend dependencies; npm reported Node 18 engine warnings during dependency install for packages that require Node 20, but lint/build completed.

# Risks / Follow-ups / Explicit Defers

- No live WhatsApp feedback branch was run because worker stop rules forbid live feedback/referral tests without explicit approval.
- Feedback request timing remains the existing 24-48 hour post-delivery window; conversations missed outside that window are not backfilled by this worker.
- Formal client acceptance still needs approved final E2E scope if the client wants a live feedback branch demonstration.
