---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-rt7w-overcomplication/stage-manifest.json
stream_owner: tj-rt7w.4-root-implementation
orchestration_level: slice_acceptance
scope_kind: product_slice
immediate_consumer: response-policy-stage
public_facade: src.llm.response_policy
bounded_acceptance: pure-response-policy-guards
non_goals:
  - response-exit-convergence
  - deterministic-route-retirement
evidence:
  - none
task_id: tj-rt7w.4
epic_id: tj-rt7w
stage_id: tj-rt7w-overcomplication
session_id: tj-rt7w-overcomplication
milestone: guards-out-of-process-message
milestone_status: accepted
agent_type: n/a
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: root-owned sequential behavior-preserving change
repo: treejar
branch: main
base_branch: main
base_commit: 7c0bd64
worktree: /home/me/code/treejar
write_zone:
  - src
  - tests
  - .codex
success_criteria:
  - four-guards-are-pure-module-functions
  - direct-tests-build-no-conversation
  - twenty-stored-raw-outputs-identical
  - no-existing-test-edited
selected_docs:
  - docs/superpowers/specs/2026-08-11-what-grew-too-big-and-how-we-cut-it-back-spec.md
selected_skills:
  - orchestrator-stage
  - superpowers-test-driven-development
selected_agents:
  - none
catalog_candidates:
  - none
parallel_group: n/a
depends_on_streams:
  - tj-rt7w.2
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
docs_impact: behavior
docs_reviewed: updated
docs_review_notes: stage summary records pure movement and replay proof
verification:
  - direct response-policy guard tests: 4 passed without Conversation
  - focused guard and engine tests: 909 passed
  - protected replay: 20 checked with zero per-guard or full-chain mismatches
  - process_message AST check: zero target guard closures
  - uv run ruff check src/ tests/: passed
  - uv run ruff format --check src/ tests/: passed over 361 files
  - uv run mypy src/: passed over 170 source files
  - uv run pytest tests/ -q --tb=short: 3540 passed and 19 skipped
  - scripts/orchestration/run_process_verification.sh: passed
changed_files:
  - .codex/stages/tj-rt7w-overcomplication/artifacts/tj-rt7w.4.md
  - .codex/stages/tj-rt7w-overcomplication/stage-manifest.json
  - .codex/stages/tj-rt7w-overcomplication/summary.md
  - src/llm/engine.py
  - src/llm/order_quote_routes.py
  - src/llm/response_policy.py
  - tests/test_llm_response_policy_guards.py
explicit_defers:
  - response-exit-convergence-belongs-to-tj-rt7w.5
  - tj-rt7w.7-remains-open-and-unstarted
---

# Summary

The opening, selling-turn, closed-question, and premature quote-detail guards
are pure functions in `src.llm.response_policy`. Production binds their explicit
turn state before applying the existing reply bound; none closes over
`process_message` or reads a conversation, database, or cache.

# Scope / Routing

Root-owned sequential work on `main`. The engine keeps one compatibility
adapter for existing callers of the old premature-guard name, but that adapter
only extracts state and delegates to the pure production function. No existing
test was edited.

# Verification

Four new direct tests construct no conversation. The existing acceptance
harness continues to import the same production opening, deferral, and
grounding guard objects rather than copying their implementations. The focused
guard-and-engine set passed 909 tests. An exact before/after replay over all
twenty protected raw outputs found zero mismatches per guard and across the
full chain. An AST check found none of the four target closures inside
`process_message`. Ruff, format, Mypy, and the complete Pytest suite passed.

# Delivery / Cleanup

Accepted directly in the root worktree for one local behavior-preserving
commit. No model call, push, deployment, production mutation, or real-user
message occurred.

# Risks / Follow-ups / Explicit Defers

The four response exits still converge in `tj-rt7w.5`; this child moves only
guard ownership. `tj-rt7w.7` remains open and unstarted.
