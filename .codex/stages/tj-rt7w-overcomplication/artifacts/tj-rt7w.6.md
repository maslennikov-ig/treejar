---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-rt7w-overcomplication/stage-manifest.json
stream_owner: tj-rt7w.6-root-implementation
orchestration_level: slice_acceptance
scope_kind: product_slice
immediate_consumer: message-orchestration-stage
public_facade: src.llm.engine.process_message
bounded_acceptance: process-message-size-and-suite-proof
non_goals:
  - deterministic-route-retirement
  - customer-visible-behavior-change
evidence:
  - none
task_id: tj-rt7w.6
epic_id: tj-rt7w
stage_id: tj-rt7w-overcomplication
session_id: tj-rt7w-overcomplication
milestone: split-message-orchestration
milestone_status: accepted
agent_type: n/a
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: root-owned sequential behavior-preserving change
repo: treejar
branch: main
base_branch: main
base_commit: 3199b1a
worktree: /home/me/code/treejar
write_zone:
  - src
  - tests
  - .codex
success_criteria:
  - public-process-message-under-300-lines
  - engine-under-12000-lines
  - catalog-routing-and-response-ownership-separated
  - twenty-stored-raw-outputs-identical
  - no-existing-test-edited
selected_docs:
  - docs/superpowers/specs/2026-08-11-what-grew-too-big-and-how-we-cut-it-back-spec.md
selected_skills:
  - orchestrator-stage
  - superpowers-test-driven-development
  - superpowers-systematic-debugging
selected_agents:
  - none
catalog_candidates:
  - none
parallel_group: n/a
depends_on_streams:
  - tj-rt7w.5
parallel_decision: sequential
status: accepted
delivery_method: manual integration
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: root-owned main worktree; no dedicated worktree or branch existed
risk_level: medium
verification_tier: release
risk_tags:
  - none
affected_surfaces:
  - backend
invariants:
  - test-matrix
  - deterministic-route-registry
docs_impact: behavior
docs_reviewed: updated
docs_review_notes: stage summary records module ownership and behavior-preserving proof
verification:
  - structural test: process_message is the only public function with that name and is 40 lines
  - structural test: engine.py is 11849 lines
  - focused engine and deterministic-route set: 917 passed
  - protected replay against 3199b1a: 20 checked with zero mismatches
  - response-policy and guard sources are identical to 3199b1a
  - no existing test edited; one structural test added
  - uv run ruff check src/ tests/: passed
  - uv run ruff format --check src/ tests/: passed over 367 files
  - uv run mypy src/: passed over 173 source files
  - uv run pytest tests/ -q --tb=short: 3547 passed and 19 skipped
  - scripts/orchestration/run_process_verification.sh: passed
changed_files:
  - .codex/stages/tj-rt7w-overcomplication/artifacts/tj-rt7w.6.md
  - .codex/stages/tj-rt7w-overcomplication/stage-manifest.json
  - .codex/stages/tj-rt7w-overcomplication/summary.md
  - src/llm/__init__.py
  - src/llm/catalog_planning.py
  - src/llm/engine.py
  - src/llm/message_processor.py
  - src/llm/order_quote_routes.py
  - src/llm/response_runtime.py
  - src/services/followup.py
  - tests/test_llm_engine_structure.py
explicit_defers:
  - deterministic-route-retirement-remains-out-of-scope
  - tj-rt7w.7-remains-open-and-unstarted
---

# Summary

The public `process_message` is a 40-line facade. Catalog planning and
materialization live in `src.llm.catalog_planning`; response transport types
and construction helpers live in `src.llm.response_runtime`; text policy stays
in `src.llm.response_policy`; quote and order routing remains in
`src.llm.order_quote_routes`. The remaining orchestration sequence lives in
`src.llm.message_processor` instead of the catalog-and-tool monolith.

# Scope / Routing

Root-owned sequential work on `main`. Existing `src.llm.engine.*` patch points
remain available at runtime. Deterministic static replies use the production
route builder in `order_quote_routes`, so the existing registry test still
finds every customer-facing route without changing that test.

# Verification

The structural test proves the settled 40-line and 11,849-line limits. No
existing test was edited. An exact replay of the twenty protected raw outputs
against commit `3199b1a` produced zero mismatches; the response-policy and guard
sources are themselves unchanged. The focused engine and route-registry set
passed 917 tests. Ruff, format, Mypy, and the complete Pytest suite passed.

# Delivery / Cleanup

Accepted directly in the root worktree for one local behavior-preserving
commit. No model call, push, deployment, production mutation, or real-user
message occurred.

# Risks / Follow-ups / Explicit Defers

Retiring deterministic routes remains outside this stage. `tj-rt7w.7` remains
open and unstarted.
