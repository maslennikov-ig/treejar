---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-rt7w-overcomplication/stage-manifest.json
stream_owner: tj-rt7w.3-root-implementation
orchestration_level: slice_acceptance
scope_kind: product_slice
immediate_consumer: response-policy-stage
public_facade: src.llm.money
bounded_acceptance: canonical-money-parser-agreement
non_goals:
  - currency-alias-expansion
  - deterministic-route-retirement
evidence:
  - none
task_id: tj-rt7w.3
epic_id: tj-rt7w
stage_id: tj-rt7w-overcomplication
session_id: tj-rt7w-overcomplication
milestone: one-money-parser
milestone_status: accepted
agent_type: n/a
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: root-owned sequential behavior-preserving change
repo: treejar
branch: main
base_branch: main
base_commit: 75962a6
worktree: /home/me/code/treejar
write_zone:
  - src
  - tests
  - .codex
success_criteria:
  - one-money-module-and-canonical-form
  - four-call-sites-agree-on-twenty-stored-outputs
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
cleanup_status: not_applicable
cleanup_notes: root-owned main worktree
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
docs_review_notes: stage summary records the behavior-preserving replay proof
verification:
  - focused money and four-consumer tests: 986 passed
  - protected replay: 20 checked with zero mismatches in all four modules
  - uv run ruff check src/ tests/: passed
  - uv run ruff format --check src/ tests/: passed over 360 files
  - uv run mypy src/: passed over 170 source files
  - uv run pytest tests/ -q --tb=short: 3536 passed and 19 skipped
  - scripts/orchestration/run_process_verification.sh: passed
changed_files:
  - .codex/stages/tj-rt7w-overcomplication/artifacts/tj-rt7w.3.md
  - .codex/stages/tj-rt7w-overcomplication/stage-manifest.json
  - .codex/stages/tj-rt7w-overcomplication/summary.md
  - src/llm/engine.py
  - src/llm/fact_extractor.py
  - src/llm/grounding_output.py
  - src/llm/money.py
  - src/llm/opening_guard.py
  - tests/test_llm_money.py
explicit_defers:
  - currency-alias-expansion-would-be-a-separate-behavior-change
  - tj-rt7w.7-remains-open-and-unstarted
---

# Summary

One money module now owns amount-token recognition, the existing currency
spellings, and canonical decimal rendering. Engine budget parsing, customer
fact extraction, grounding, and the opening guard all consume it.

# Scope / Routing

Root-owned sequential work on `main`. The move intentionally preserves each
call site's existing currency vocabulary; accepting new aliases would be a
separate behavior change. No existing test was edited.

# Verification

Ten new direct tests cover canonical values, both existing amount orders, and
opening currency presence. The focused money-and-consumer set passed 986 tests.
An exact pre-move replay over all twenty protected raw outputs found zero
mismatches in each of engine, fact extraction, grounding, and opening guard.
Ruff, format, Mypy, and the complete Pytest suite passed.

# Delivery / Cleanup

Accepted directly in the root worktree for one local behavior-preserving
commit. No model call, push, deployment, production mutation, or real-user
message occurred.

# Risks / Follow-ups / Explicit Defers

Currency alias expansion remains outside this pure move. `tj-rt7w.7` remains
open and unstarted.
