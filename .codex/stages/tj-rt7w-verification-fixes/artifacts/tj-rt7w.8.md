---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-rt7w-verification-fixes/stage-manifest.json
stream_owner: tj-rt7w.8-root-implementation
orchestration_level: slice_acceptance
scope_kind: product_slice
immediate_consumer: tj-rt7w-real-split
public_facade: n/a
bounded_acceptance: named-frozen-source-repin
non_goals:
  - process-message-impl-split
  - deterministic-route-retirement
evidence:
  - none
task_id: tj-rt7w.8
epic_id: tj-rt7w
stage_id: tj-rt7w-verification-fixes
session_id: tj-rt7w-verification-fixes
milestone: overcomplication-verification-fixes
milestone_status: accepted
agent_type: n/a
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: root-owned sequential work; repo contract disallows inline subagents
repo: treejar
branch: main
base_branch: main
base_commit: 58a64de
worktree: /home/me/code/treejar
write_zone:
  - src
  - tests
  - scripts
  - docs
  - .codex
success_criteria:
  - tip-suite-green
  - mutable-set-unchanged
  - unknown-source-name-rejected
selected_docs:
  - docs/superpowers/specs/2026-08-11-what-grew-too-big-and-how-we-cut-it-back-spec.md
selected_skills:
  - orchestrator-stage
selected_agents:
  - none
catalog_candidates:
  - none
parallel_group: n/a
depends_on_streams:
  - none
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
docs_review_notes: the re-pin step documents why the index is not current state
verification:
  - uv run ruff check src/ tests/ scripts/: passed
  - uv run ruff format --check src/ tests/ scripts/: passed
  - uv run mypy src/: passed over 173 source files
  - uv run pytest tests/ -q --tb=line: 3554 passed and 19 skipped
  - scripts/orchestration/run_process_verification.sh: passed
changed_files:
  - scripts/orchestration/repin_traceability_sources.py
  - tests/test_orchestration_repin_traceability.py
  - .codex/stages/tj-ee5f/traceability-manifest.json
explicit_defers:
  - tj-rt7w.10-the-genuine-split-remains-open
  - tj-rt7w.7-remains-open-and-blocked-on-tj-rt7w.10
---

# Summary

Three manifest tests failed on `main`. `58a64de` updated
`.codex/project-index.md` for the new `src/llm/` boundaries and did not
re-pin the digests two `tj-ee5f` criteria cite. Bisected: 44 passed at
`4640602`, 3 failed at `58a64de`, so the stage's reported `3547 passed` was
never true of its own tip.

The re-pin step refused the drift correctly. Its mutable set is exactly the
two files `AGENTS.md` calls current state; the index calls itself a stable
navigation map. `--source` records the move of one named source and rejects
a name the manifest does not carry, so a typo cannot read as no drift.

# Scope / Routing

Root-owned. The mutable set is untouched, which its own test still locks.

# Verification

Four new tests, red before green: a named frozen source is re-pinned, naming
one does not re-pin another, an unknown name raises, and the result still
loads through the real validator.

Ruff, format, Mypy, the complete Pytest suite and process verification passed.
No existing test was edited.

# Delivery / Cleanup

Accepted in the root worktree as commit `a4e3647` on `main`. No paid model
call, push, PR, deployment, production mutation, or real-user message occurred.

# Risks / Follow-ups / Explicit Defers

`tj-rt7w.10` is open with its plan in the Bead notes. `tj-rt7w.7` is blocked on
it. `tj-rt7w.14` records the missing semantic half of R2.
