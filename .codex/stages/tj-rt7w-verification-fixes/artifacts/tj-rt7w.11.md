---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-rt7w-verification-fixes/stage-manifest.json
stream_owner: tj-rt7w.11-root-implementation
orchestration_level: slice_acceptance
scope_kind: product_slice
immediate_consumer: tj-rt7w-real-split
public_facade: n/a
bounded_acceptance: spec-matches-implemented-bound
non_goals:
  - process-message-impl-split
  - deterministic-route-retirement
evidence:
  - none
task_id: tj-rt7w.11
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
base_commit: dce7442
worktree: /home/me/code/treejar
write_zone:
  - src
  - tests
  - scripts
  - docs
  - .codex
success_criteria:
  - spec-matches-code
  - residual-gap-tracked
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
risk_level: low
verification_tier: release
risk_tags:
  - none
affected_surfaces:
  - backend
invariants:
  - test-matrix
docs_impact: behavior
docs_reviewed: updated
docs_review_notes: R2 now states the bound that shipped and names what it does not do
verification:
  - uv run ruff check src/ tests/ scripts/: passed
  - uv run ruff format --check src/ tests/ scripts/: passed
  - uv run mypy src/: passed over 173 source files
  - uv run pytest tests/ -q --tb=line: 3554 passed and 19 skipped
  - scripts/orchestration/run_process_verification.sh: passed
changed_files:
  - docs/superpowers/specs/2026-08-11-what-grew-too-big-and-how-we-cut-it-back-spec.md
explicit_defers:
  - tj-rt7w.10-the-genuine-split-remains-open
  - tj-rt7w.7-remains-open-and-blocked-on-tj-rt7w.10
---

# Summary

R2 was rewritten during `tj-rt7w.2` to say semantic validity belongs to the
guard-specific semantic validator. There is none. The implemented bound is
letters-or-digits-in, letters-or-digits-out, which catches F5 and does not
stop a guard shrinking four sentences to one word. The rule now says both,
and the gap is `tj-rt7w.14`.

# Scope / Routing

Documentation only. Adding a semantic check would change output and owes a measured round under R5.

# Verification

No code changed; the suite is unaffected and was run anyway.

Ruff, format, Mypy, the complete Pytest suite and process verification passed.
No existing test was edited.

# Delivery / Cleanup

Accepted in the root worktree as commit `8a80c1f` on `main`. No paid model
call, push, PR, deployment, production mutation, or real-user message occurred.

# Risks / Follow-ups / Explicit Defers

`tj-rt7w.10` is open with its plan in the Bead notes. `tj-rt7w.7` is blocked on
it. `tj-rt7w.14` records the missing semantic half of R2.
