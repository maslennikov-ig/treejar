---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-vz7o-real-openings/stage-manifest.json
stream_owner: opening-measurement-integrator
orchestration_level: slice_acceptance
scope_kind: product_slice
immediate_consumer: client-opening-readiness-report
public_facade: protected-real-opening-acceptance-runner
bounded_acceptance: twenty-luna-openings-and-twenty-glm-evaluations
non_goals:
  - haiku comparison, live traffic, production mutation, real-user messaging, deploy, push, conversion claims, or rubric changes
evidence:
  - protected-run-manifest
  - integer-only-acceptance-summary
task_id: tj-vz7o.10-runner
epic_id: tj-vz7o
stage_id: tj-vz7o-real-openings
session_id: tj-vz7o.10
milestone: luna-glm-real-opening-acceptance
milestone_status: in_progress
agent_type: worker
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: Root owns the paid-call boundary and final acceptance; no delegated implementation stream is needed.
repo: treejar
branch: codex/tj-vz7o-corpus-bridge
base_branch: main
base_commit: b0cf0034c40295500add15b67d30e29cf1b8a343
worktree: /home/me/code/treejar
write_zone:
  - scripts/corpus_bridge/
  - tests/test_corpus_bridge_real_opening_acceptance.py
  - .codex/goals/tj-vz7o.10/
  - .codex/stages/tj-vz7o-real-openings/
  - .codex/orchestrator.toml
  - .codex/handoff.md
  - docs/reports/
success_criteria:
  - exactly 20 protected Luna replies and 20 GLM evaluations
  - zero critical opening failures with weighted score and interval
  - two manual reads and a narrow client-ready opening claim
  - corpus guard and repository acceptance pass without remote delivery
selected_docs:
  - AGENTS.md
  - .codex/orchestrator.toml
  - .codex/handoff.md
  - docs/superpowers/specs/2026-08-10-the-clients-ruler-and-the-corpus-bridge-spec.md
selected_skills:
  - orchestrator-stage
selected_agents:
  - none
catalog_candidates:
  - none
parallel_group: none
depends_on_streams:
  - none
parallel_decision: sequential
status: returned
delivery_method: manual integration
accepted_by_orchestrator: no
cleanup_status: not_applicable
cleanup_notes: Protected evidence is retained outside Git; no child worktree exists.
risk_level: high
verification_tier: integration
risk_tags:
  - data
affected_surfaces:
  - data
invariants:
  - test-matrix
docs_impact: behavior
docs_reviewed: complete
docs_review_notes: The measured failure and its limits are recorded in the acceptance report and current-state handoff.
verification:
  - 15 focused runner tests passed
  - ruff and format passed over 429 files
  - mypy passed over 168 source files
  - pytest passed 3463 with 19 skipped
  - process verification passed
  - exactly 20 Luna and 20 GLM calls journaled
  - protected analysis records 2 critical failures across 2/20 openings
changed_files:
  - scripts/corpus_bridge/real_opening_acceptance.py
  - tests/test_corpus_bridge_real_opening_acceptance.py
  - docs/reports/2026-08-10-luna-glm-real-opening-acceptance.md
explicit_defers:
  - tj-vz7o.10.1 removes two product failures before rerun
  - tj-vz7o.10.2 freezes a shape-aware gate before rerun
---

# Summary

Measured but not accepted. Transcript-bearing inputs and outputs remain
protected outside Git.

# Scope / Routing

One root-owned measurement stream. The paid calls are the accepted external
action; no production or customer-facing action is authorized.

# Verification

20/20 Luna responses and 20/20 GLM evaluations exist. Corrected analysis leaves
2 critical failures across 2/20 openings, so orchestrator acceptance remains no.

# Delivery / Cleanup

Local branch only; no push or deploy.

# Risks / Follow-ups / Explicit Defers

The result does not yet support opening readiness. It cannot establish
conversion, revenue, close rate, deal size, or off-channel outcomes.
