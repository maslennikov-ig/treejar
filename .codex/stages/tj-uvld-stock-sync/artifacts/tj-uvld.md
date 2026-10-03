---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-uvld-stock-sync/stage-manifest.json
stream_owner: root-stock-implementation
orchestration_level: slice_acceptance
scope_kind: product_slice
immediate_consumer: quotation creation and discovery stock
public_facade: ZohoInventoryClient
bounded_acceptance: AC01–AC12 local acceptance; external gates explicit
non_goals:
  - deployment and external business writes
  - website catalog scoping and webhooks
evidence:
  - none
task_id: tj-uvld
epic_id: n/a
stage_id: tj-uvld-stock-sync
session_id: n/a
milestone: stock optimization and fresh quotation consumer
milestone_status: in_progress
agent_type: root
subagent_model: n/a
reasoning_effort: n/a
model_reasoning_rationale: tightly coupled work at root; independent read-only docs and review delegated
repo: treejar
branch: codex/tj-uvld-stock-sync
base_branch: main
base_commit: 36c86137a51d2e6485db92c28ec057fe26f03339
worktree: /home/me/code/treejar/.worktrees/tj-uvld-stock-sync
write_zone:
  - src/integrations/inventory/
  - src/worker.py
  - src/core/config.py
  - src/llm/engine.py
  - src/llm/customer_intent_tools.py
  - src/services/quotation_retry.py
  - tests/
  - scripts/zoho_stock_*.py
  - scripts/vps-deploy.sh
  - scripts/orchestration/run_stage_closeout.py
  - docs/ and .codex/
success_criteria:
  - AC01–AC12 per anchored specification
selected_docs:
  - docs/specs/zoho-stock-sync-optimization/spec.md
  - docs/research/2026-10-03-zoho-stock/README.md
selected_skills:
  - orchestrator-stage
  - orchestration-closeout
selected_agents:
  - provider_docs
  - stock_correctness_review
catalog_candidates:
  - none
parallel_group: root
depends_on_streams:
  - none
parallel_decision: local
status: accepted
delivery_method: manual integration
accepted_by_orchestrator: yes
cleanup_status: blocked
cleanup_notes: root candidate intentionally retained for review; delivery lacks authority
risk_level: high
verification_tier: slice_acceptance
risk_tags:
  - concurrency
  - atomicity
  - retry
  - state-transition
  - idempotency
  - rollback
affected_surfaces:
  - backend
  - user-flow
invariants:
  - state-transition
  - idempotency
  - rollback
  - test-matrix
docs_impact: behavior
docs_reviewed: updated
docs_review_notes: report, provider receipts, spec, entrypoints and current handoff
verification:
  - root selected Ruff/format and mypy: passed
  - focused pytest: 241 passed; 8 real Redis integration tests
  - canonical stage closeout and process verification: passed
changed_files:
  - src/integrations/inventory/stock_state.py
  - src/integrations/inventory/zoho_inventory.py
  - src/integrations/inventory/sync.py
  - src/worker.py
  - src/llm/engine.py
  - src/llm/customer_intent_tools.py
  - src/services/quotation_retry.py
  - tests/test_zoho_stock_incremental.py
  - tests/test_zoho_stock_bulk.py
explicit_defers:
  - tj-uvld provider operation coverage, authorized delivery and real24h proof
---

# Summary

Root accepted local implementation content with eligibility closed. External
acceptance remains owned by tj-uvld; final tests and source-bound receipts are recorded below.

# Scope / Routing

One coupled implementation stream, read-only provider/docs and correctness
review in separate clean trees; no independent helper-only deliveries.

# Verification

Root final acceptance passed:241 tests, Ruff/format, mypy193 files,
process verification and git diff --check. Exact commands/evidence are in
evidence/ and logs below. Provider operation coverage remains unproved.
Verification sidecars are in .codex/stages/tj-uvld-stock-sync/evidence/
(frontmatter validator currently permits tokens only). Canonical closeout owns
source/command/environment identity and rejects mismatching reuse.

Real disposable Redis validates lease/CAS behavior; synthetic provider HTTP
and intercepted quotation effects do not prove live transaction coverage.

# Delivery / Cleanup

No main merge/push/deploy. Root worktree retained pending owner authorization.
Clean auxiliary docs/review worktrees/branches and disposable Redis removed.

# Risks / Follow-ups

AC02 requires approved stock/lifecycle diagnostics and paging semantics.
Actual production reduction requires approved activation and24h evidence.
