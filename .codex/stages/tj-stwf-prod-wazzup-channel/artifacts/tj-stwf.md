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
  - provider-readback
  - protected-env-backup
  - production-health-readback
task_id: tj-stwf
epic_id: tj-stwf
stage_id: tj-stwf-prod-wazzup-channel
session_id: tj-stwf-prod-wazzup-channel
milestone: production-wazzup-channel-routing
milestone_status: internal_ready
agent_type: deploy_specialist
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: production runtime configuration and rollback risk inherit the orchestrator model and reasoning
repo: treejar
branch: codex/prod-wazzup-channel-switch
base_branch: main
base_commit: 167e67c817e6f7a3c06cb36037c81a14bd31e526
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
  - "provider GET /v3/channels: old channel qridle, target channel active"
  - "preflight public health: ok at release 43d6430b266a14f14e7f77845e60dbca6c05de52, Redis and PostgreSQL ok"
  - "preflight app/worker readback: matching old channel ID, running, restart 0, OOM false"
  - "sanitized env comparison: only WAZZUP_CHANNEL_ID changed"
  - "post-switch public health: unchanged release, Redis and PostgreSQL ok"
  - "post-switch app/worker readback: matching target channel ID, running, restart 0, OOM false"
  - "db/redis/nginx start times unchanged; app/worker recreated together"
  - "post-switch startup markers: 3; error markers: 0"
  - "post-switch unexpected-channel warnings: 0; fresh inbound batches: 0 at observation time"
changed_files:
  - .codex/stages/tj-stwf-prod-wazzup-channel/artifacts/tj-stwf.md
explicit_defers:
  - fresh-tester-message-proof-requires-new-inbound-after-switch
---

# Summary

The authorized production channel switch is complete. Production `app` and
`worker` now use the active `Treejar Trading` Wazzup channel. No source deploy,
provider registration change, old-message replay, paid model call, or real-user
message was performed.

# Scope / Routing

Changed only production `WAZZUP_CHANNEL_ID` from the disconnected Treejar
channel `b49b1b9d-757f-4104-b56d-8f43d62cc515` to the owner-approved active
Treejar Trading channel `13c71a7f-cf9d-4df2-8b27-11ea67e6b0d9`.

Readiness was content-free: public health was green, provider `GET
/v3/channels` reported the old channel as `qridle` and the target as `active`,
and both app and worker held the old ID with zero restarts and no OOM events.

The exact `.env` was copied with mode `0600` before each mutation attempt:

- `/opt/noor/.codex-backups/tj-stwf-wazzup-channel-before-20260827T135525Z.env`
- `/opt/noor/.codex-backups/tj-stwf-wazzup-channel-before-retry-20260827T135741Z.env`

A sanitized full-file digest, with only the channel value redacted, matched
before and after the successful edit. This proves all other `.env` lines and
their ordering remained unchanged.

# Verification

The first attempt reached the app/worker recreation but its local health JSON
parser was wired with conflicting stdin redirects. The guard therefore failed
closed and automatically restored the first protected backup. Rollback
readback proved public health green, both services back on the old ID, and both
containers running with restart `0` and OOM `false`.

After fixing only that diagnostic command and refreshing provider state, the
switch was retried from the proven rollback state. The successful command used
the repository's Compose boundary:

```text
docker compose up -d --no-deps --force-recreate app worker
```

Final content-free readback proved:

- public health `ok` at unchanged release
  `43d6430b266a14f14e7f77845e60dbca6c05de52`;
- Redis and PostgreSQL health `ok`;
- `.env`, app, and worker all hold the target channel ID;
- app and worker are running with restart `0` and OOM `false`;
- DB, Redis, and nginx retained their earlier start times and were not
  recreated;
- three startup markers and zero error markers after the final recreation;
- zero unexpected-channel warnings and zero new inbound batches during the
  bounded observation window.

Rollback remains: restore the retry backup to `/opt/noor/.env`, preserve mode
`0600`, recreate only app and worker with the same Compose command, then repeat
the public health and runtime-ID readbacks.

# Delivery / Cleanup

Branch artifact commit is ready for root review and stage acceptance. Runtime
mutation itself is complete; there was no source deployment.

# Risks / Follow-ups / Explicit Defers

The fresh-message proof remains explicit and unperformed: the tester or owner
must send a new message after the switch. Existing dropped events were not
replayed or manually answered, and no message or quarantine content was read.
