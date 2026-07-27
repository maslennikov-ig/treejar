---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-5e3k/stage-manifest.json
stream_owner: model-battle-stage-owner
orchestration_level: release
scope_kind: product_slice
immediate_consumer: Noor model-routing decision
public_facade: n/a
bounded_acceptance: four-candidate synthetic model battle for both Noor routes
non_goals:
  - production model switch, customer traffic, Zoho/Wazzup mutations
evidence:
  - route-decisions
  - decision-report
task_id: tj-5e3k
epic_id: n/a
stage_id: tj-5e3k
session_id: n/a
milestone: cohesive-vertical-slice
milestone_status: in_progress
agent_type: worker
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: Root owns the shared benchmark; anonymous sales scoring uses context isolation.
repo: treejar
branch: main
base_branch: main
base_commit: 8f73c4e
worktree: /home/me/code/treejar
write_zone:
  - benchmark profile, tests, tracked evidence, report, Beads, and stage documentation
success_criteria:
  - Compare all accepted candidates reproducibly and record strict and practical route decisions without production mutation.
selected_docs:
  - docs/superpowers/specs/2026-07-27-noor-glm52-v4pro-model-battle-design.md
  - docs/superpowers/plans/2026-07-27-noor-glm52-v4pro-model-battle.md
selected_skills:
  - orchestrator-stage
  - brainstorming
  - writing-plans
  - test-driven-development
  - prompt-authoring
  - verification-before-completion
selected_agents:
  - qa_expert for context-isolated anonymous sales review
catalog_candidates:
  - none; installed workflows cover the stage
parallel_group: noor-extended-model-battle
depends_on_streams:
  - none
parallel_decision: sequential inference followed by isolated read-only scoring
status: returned
delivery_method: manual integration
accepted_by_orchestrator: no
cleanup_status: pending
cleanup_notes: Stage uses the root worktree; unrelated untracked user files remain untouched.
risk_level: high
verification_tier: release
risk_tags:
  - api
affected_surfaces:
  - backend
invariants:
  - test-matrix
  - structured-output
  - production-unchanged
docs_impact: behavior
docs_reviewed: pending
docs_review_notes: Durable report and handoff update are pending benchmark evidence.
verification:
  - pending
changed_files:
  - scripts/model_battle.py
  - tests/test_scripts_model_battle.py
  - .codex/stages/tj-5e3k/results/
  - docs/reports/model-battle-glm52-v4pro-2026-07-27.md
explicit_defers:
  - Production adoption and deployment remain separately gated.
---

# Summary

The stage is in progress. The accepted profile will be extended through TDD,
then the full synthetic inference matrix and anonymous sales review will run
before route recommendations are recorded.

# Verification

- Pending implementation and benchmark execution.

# Risks / Follow-ups

- Production adoption and deployment remain separately gated.

