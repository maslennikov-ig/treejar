---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-uvld-stock-sync/stage-manifest.json
stream_owner: release-quote-tests
orchestration_level: slice_acceptance
scope_kind: product_slice
evidence:
  - none
task_id: tj-uvld-release-quote-tests
stage_id: tj-uvld-stock-sync
repo: treejar
branch: codex/tj-uvld-release-quote-tests
base_branch: codex/tj-uvld-stock-sync
base_commit: 4dbbf495c58780cf7c53d081e6610e2ee94153d8
worktree: /home/me/code/treejar/.worktrees/tj-uvld-release-quote-tests
status: accepted
delivery_method: cherry-pick
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: Patch and all four file identities verified in root; clean worktree removed.
risk_level: low
verification_tier: delta
risk_tags:
  - retry
  - idempotency
affected_surfaces:
  - user-flow
invariants:
  - idempotency
docs_impact: tests-only
docs_reviewed: no-change-needed
docs_review_notes: Root owns release documentation and full canonical acceptance.
verification:
  - PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$PWD UV_PROJECT_ENVIRONMENT=/home/me/code/treejar/.venv uv run --no-sync pytest tests/test_llm_engine.py tests/test_quotation_turn_integrity.py tests/test_e2e_tools.py tests/test_dialog_scenarios.py -q --tb=short: passed, 747 tests in 5.54s
  - PYTHONDONTWRITEBYTECODE=1 UV_PROJECT_ENVIRONMENT=/home/me/code/treejar/.venv uv run --no-sync ruff check tests/test_llm_engine.py tests/test_quotation_turn_integrity.py tests/test_e2e_tools.py tests/test_dialog_scenarios.py: passed
  - PYTHONDONTWRITEBYTECODE=1 UV_PROJECT_ENVIRONMENT=/home/me/code/treejar/.venv uv run --no-sync ruff format --check tests/test_llm_engine.py tests/test_quotation_turn_integrity.py tests/test_e2e_tools.py tests/test_dialog_scenarios.py: passed, 4 files already formatted
  - git diff --check: passed
changed_files:
  - tests/test_llm_engine.py
  - tests/test_quotation_turn_integrity.py
  - tests/test_e2e_tools.py
  - tests/test_dialog_scenarios.py
explicit_defers:
  - none
---

# Summary

Commit `d773bf437b33bed2ae1015f2551d0e5e6048ce07` adapts only quotation doubles to `get_stock_bulk_fresh`; browsing mocks keep `get_stock_bulk`. Existing customer-field, consent, PDF, VAT, delivery and idempotency assertions remain. Guards now prove no fresh read before consent/details or for an unchanged sent quote. Missing fresh rows assert exact pending positions, preserved customer details and consent, one operational alert, and no discovery/catalog fallback, customer/order creation, PDF or delivery.

# Verification

All commands above ran in the dedicated worktree on the committed content. Original happy-path failure reproduced before editing; it passed after the minimal fresh-mock correction. The final four-file acceptance passed 747/747. Worktree is clean; commit has `Co-Authored-By: Codex <noreply@openai.com>`.

# Risks / Follow-ups

Root owns cherry-pick, full canonical release acceptance and all external delivery. This is local mock proof. No production/staging mutation, paid call, external write or message was performed. This report stays outside the repository because the assigned write zone contains only the four test files.

Root accepted as5f9e992; matching files and git cherry equivalence proved.
Root canonical full release:4458 passed,20 skipped; no provider writes.
