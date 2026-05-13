---
schema_version: orchestration-artifact/v1
artifact_type: delegated-stream
task_id: tj-gh12.19
stage_id: tj-gh12
repo: treejar
branch: codex/tj-gh12-name-gate-hotfix-clean
base_branch: main
base_commit: 0a283a42a94b10e77456f641ee0b87a789f13efd
worktree: /home/me/code/treejar/.worktrees/codex-tj-gh12-name-gate-hotfix-clean
status: accepted
delivery_method: manual integration
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: "Implemented locally in the hotfix worktree; production recheck pending after deploy."
risk_level: high
verification:
  - "uv run pytest tests/test_llm_engine.py::test_process_message_exact_quote_missing_details_accepts_quantity_x_sku -q": failed before fix, passed after fix
  - "uv run pytest tests/test_llm_engine.py tests/test_llm_quotation.py tests/test_response_adapter.py tests/test_webhook_manager.py tests/test_services_chat_batch.py tests/test_messaging_wazzup.py tests/test_proposal_followup.py tests/services/test_quotation_template.py tests/services/test_pdf_generator.py -q": passed, 203 passed
  - "uv run ruff check src/ tests/": passed
  - "uv run ruff format --check src/ tests/": passed
  - "uv run mypy src/": passed
  - "env DYLD_FALLBACK_LIBRARY_PATH=\"${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}\" uv run pytest tests/ -v --tb=short": passed, 1006 passed and 19 skipped
changed_files:
  - src/llm/engine.py
  - tests/test_llm_engine.py
  - .codex/stages/tj-gh12/artifacts/tj-gh12.15-second-post-deploy-live-e2e.md
  - .codex/stages/tj-gh12/artifacts/tj-gh12.19-quantity-x-hotfix.md
explicit_defers:
  - "Deploy and recheck live missing-data quotation scenario; then clean the synthetic pending escalation from the failed E2E run."
---

# Summary

Fixed the production blocker found by second post-deploy E2E: exact quotation parsing now treats `1 x CH-620` as quantity `1` and SKU/item candidate `CH-620`, instead of carrying the multiplier marker `x` into SKU resolution.

Before the fix, `x CH-620` failed deterministic SKU resolution and the exact-quote path fell through to fail-closed manager escalation. After the fix, the existing required-data gate catches the missing company/specific delivery address and returns the customer-facing missing-details request without Zoho, PDF, media, or manager escalation.

# Documentation

Context7 routing was checked for SQLAlchemy 2.0 async ORM readback examples (`/websites/sqlalchemy_en_20_orm`) for the live E2E DB inspection pattern. The code change itself is business-logic parsing and did not require framework behavior changes.

# Verification

RED/GREEN regression:

```text
tests/test_llm_engine.py::test_process_message_exact_quote_missing_details_accepts_quantity_x_sku
```

Fresh local verification after the fix:

```text
uv run pytest impacted suite -q -> 203 passed
uv run ruff check src/ tests/ -> passed
uv run ruff format --check src/ tests/ -> passed
uv run mypy src/ -> passed
uv run pytest tests/ -v --tb=short -> 1006 passed, 19 skipped
```

# Risks / Follow-ups / Explicit Defers

Production live E2E must be repeated after deploy for the exact failed prompt. The existing synthetic pending escalation from `d82cb1ca-4cde-4042-9f18-4c3129901f93` remains pending until cleanup through the normal application-level manager-resolution path.
