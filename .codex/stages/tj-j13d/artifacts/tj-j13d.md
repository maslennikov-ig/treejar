---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-j13d/stage-manifest.json
stream_owner: root-implementation-and-deployment
orchestration_level: release
scope_kind: product_slice
immediate_consumer: Noor production model routing and sales responses
public_facade: runtime model settings and customer-facing grounding behavior
bounded_acceptance: grounded GLM-5.2 sales and V4 Flash helper adoption through verified production deployment
non_goals:
  - real customer messages, outbound Wazzup, quotation/order creation, Zoho mutation, unrelated prompt redesign
evidence:
  - focused-tdd
  - provider-smoke
  - production-readback
task_id: tj-j13d
epic_id: n/a
stage_id: tj-j13d
session_id: n/a
milestone: cohesive-vertical-slice
milestone_status: in_progress
agent_type: worker
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: Root owns the shared model, prompt, deployment, and rollback boundary; one context-isolated reviewer is reserved for release risk.
repo: treejar
branch: main
base_branch: main
base_commit: dbd02f0
worktree: /home/me/code/treejar
write_zone:
  - model configuration, grounding policy, focused tests, verification script, stage documentation, protected production model variables and deploy evidence
success_criteria:
  - Deliver the accepted Beads criterion without customer-facing or business-system side effects.
selected_docs:
  - docs/superpowers/specs/2026-07-27-noor-model-switch-grounding-design.md
  - docs/faq.md
  - .codex/orchestrator.toml
selected_skills:
  - orchestrator-stage
  - brainstorming
  - writing-plans
  - test-driven-development
  - prompt-authoring
  - verification-before-completion
  - orchestration-closeout
selected_agents:
  - correctness reviewer at release boundary
catalog_candidates:
  - none; installed workflows and repository policy cover the stage
parallel_group: noor-grounded-model-adoption
depends_on_streams:
  - none
parallel_decision: sequential local implementation, release review, deploy, and post-deploy verification due shared files and hard dependency
status: returned
delivery_method: not accepted
accepted_by_orchestrator: no
cleanup_status: pending
cleanup_notes: Root worktree only; unrelated untracked user files remain untouched.
risk_level: high
verification_tier: release
risk_tags:
  - public-api
  - retry
affected_surfaces:
  - backend
invariants:
  - core-main-model
  - helper-fast-model
  - evidence-grounded-claims
  - tool-and-manager-authority
  - rollback-readiness
docs_impact: behavior
docs_reviewed: pending
docs_review_notes: Implementation and production evidence are pending.
verification:
  - pending
changed_files:
  - pending
explicit_defers:
  - Real customer messaging and business-system mutations remain outside this stage.
---

# Summary

The approved design and scope are ready for TDD implementation.

# Verification

- Pending.

# Risks / Follow-ups

- Production deployment is authorized only after local release gates and
  provider smoke evidence pass.

