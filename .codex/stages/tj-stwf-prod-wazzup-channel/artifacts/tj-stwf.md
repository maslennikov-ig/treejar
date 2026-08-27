---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-stwf-prod-wazzup-channel/stage-manifest.json
stream_owner: prod-wazzup-channel-worker
orchestration_level: slice_acceptance
scope_kind: product_slice
immediate_consumer: root-orchestrator-production-incident
public_facade: production-Wazzup-message-path
bounded_acceptance: switch-only-app-worker-to-owner-approved-active-channel-with-rollback-and-no-message-replay
non_goals:
  - code-change-deploy-or-provider-registration-mutation
  - dropped-message-replay-or-real-user-message
  - database-redis-or-neighboring-service-mutation
evidence:
  - none
task_id: tj-stwf
epic_id: tj-stwf
stage_id: tj-stwf-prod-wazzup-channel
session_id: tj-stwf-prod-wazzup-channel
milestone: production-wazzup-channel-routing
milestone_status: in_progress
agent_type: deploy_specialist
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: production runtime configuration and rollback risk inherit the orchestrator model and reasoning
repo: treejar
branch: codex/prod-wazzup-channel-switch
base_branch: main
base_commit: 6be1d698dd1275a5800e1029b0568c3b2c78b570
worktree: /home/me/code/treejar/.worktrees/prod-wazzup-channel-switch
write_zone:
  - .codex/stages/tj-stwf-prod-wazzup-channel/artifacts/tj-stwf.md
success_criteria:
  - protected-backup-and-exact-old-new-channel-readback
  - recreate-only-noor-app-and-noor-worker
  - unchanged-release-public-health-and-dependencies-green
  - fresh-tester-message-reaches-normal-path-with-no-old-message-replay
selected_docs:
  - AGENTS.md
  - .codex/orchestrator.toml
  - .codex/handoff.md
  - .codex/stages/tj-stwf-prod-wazzup-channel/stage-manifest.json
selected_skills:
  - technical-premortem
selected_agents:
  - deploy_specialist
catalog_candidates:
  - none
parallel_group: production-wazzup-channel-incident
depends_on_streams:
  - none
parallel_decision: sequential
status: returned
delivery_method: not accepted
accepted_by_orchestrator: no
cleanup_status: pending
cleanup_notes: dedicated worktree and branch remain until root acceptance
risk_level: high
verification_tier: delta
risk_tags:
  - rollback
  - state-transition
  - authorization
affected_surfaces:
  - api
  - backend
  - user-flow
invariants:
  - rollback
  - state-transition
  - test-matrix
docs_impact: ops-deploy
docs_reviewed: no-change-needed
docs_review_notes: runtime incident evidence is recorded in this stage artifact and current handoff
verification:
  - pending: blocked
changed_files:
  - .codex/stages/tj-stwf-prod-wazzup-channel/artifacts/tj-stwf.md
explicit_defers:
  - fresh-tester-message-proof-requires-new-inbound-after-switch
---

# Summary

Production incident stream is in progress.

# Scope / Routing

Change only the production `WAZZUP_CHANNEL_ID` from the disconnected Treejar
channel to the owner-approved active Treejar Trading channel. Preserve a
mode-`0600` rollback copy, recreate only app and worker, and do not replay or
manually answer the dropped messages.

# Verification

Pending production execution and root acceptance.

# Delivery / Cleanup

Pending.

# Risks / Follow-ups / Explicit Defers

The fresh-message proof requires the tester or owner to send a new message after
the switch. Existing dropped payloads are not present in the application queue.
