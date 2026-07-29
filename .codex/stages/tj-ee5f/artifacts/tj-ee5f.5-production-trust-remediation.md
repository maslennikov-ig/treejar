---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-ee5f/stage-manifest.json
stream_owner: trust_remediation
orchestration_level: integration
scope_kind: foundation
immediate_consumer: tj-ee5f.1
public_facade: scripts/run_noor_e2e_acceptance.py
bounded_acceptance: real authority-bound HTTP dispatch and SSH readback materialize protected production facts
non_goals:
  - no live HTTP, SSH, provider, customer, CRM, quotation, deploy, paid call, or Beads mutation
evidence:
  - none
task_id: tj-ee5f.5
epic_id: tj-ee5f
stage_id: tj-ee5f
session_id: tj-ee5f.5
milestone: trusted production transport and evidence materialization
milestone_status: accepted
agent_type: worker
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: production evidence integrity and external side effects require strict fail-closed contracts
repo: treejar
branch: codex/tj-ee5f-trust-remediation
base_branch: main
base_commit: 844a3946f36070ca282b9fbe921fd9225cefeddc
worktree: /home/me/code/treejar/.worktrees/tj-ee5f-trust-remediation
write_zone:
  - scripts/e2e_acceptance/**
  - scripts/run_noor_e2e_acceptance.py
  - tests/test_e2e_acceptance_*.py
  - .codex/stages/tj-ee5f/artifacts/tj-ee5f.5-production-trust-remediation.md
success_criteria:
  - execute-resume uses the authority-bound one-shot HTTP adapter for sealed live plans
  - preflight, action reconciliation, execution evidence, and final readback come from fixed read-only SSH sources
  - protected evidence records exact raw bytes, duration, usage cost, and side-effect dispositions
  - unknown action effects block progress until independent reconciliation and settle the observed bounded cost
  - live endpoint, SSH host, and exact readback commands are digest-bound to protected authority; webhook origin matches the approved runtime identity
  - reconciliation is causally bound and cannot use a snapshot from before permit consumption or dispatch
  - mixed executed and blocked runs seal one ordered transcript manifest
selected_docs:
  - AGENTS.md
  - .codex/orchestrator.toml
  - .codex/handoff.md
  - docs/superpowers/plans/2026-07-28-noor-task3-production-trust-repair.md
selected_skills:
  - orchestrator-stage
  - superpowers:systematic-debugging
  - superpowers:test-driven-development
  - superpowers:verification-before-completion
selected_agents:
  - none
catalog_candidates:
  - none
parallel_group: tj-ee5f-trust-remediation
depends_on_streams:
  - tj-ee5f.5-task3-live-boundary
parallel_decision: parallel
status: returned
delivery_method: cherry-pick
accepted_by_orchestrator: no
cleanup_status: pending
cleanup_notes: isolated worktree and branch remain for orchestrator integration
risk_level: high
verification_tier: integration
risk_tags:
  - authorization
  - security
  - retry
  - state-transition
  - idempotency
  - data
affected_surfaces:
  - backend
  - data
invariants:
  - state-transition
  - idempotency
  - rollback
  - test-matrix
docs_impact: behavior
docs_reviewed: no-change-needed
docs_review_notes: implementation contract is recorded in this stage artifact; no end-user documentation changed
verification:
  - focused live runtime, transport, producer, production, and report tests: passed
  - focused authority and actual-cost reconciliation tests: passed
  - correction RED proved endpoint, SSH host, command, causal identity, and stale-snapshot gaps
  - correction focused live authority, runtime, transport, and producer tests: passed 44
  - correction focused reconciliation and authority-factory tests: passed 24
  - correction focused authority-bundle and lifecycle compatibility tests: passed 2
  - final materialization compatibility test: passed
  - focused Ruff check and format: passed
  - git diff check: passed
  - artifact validator: blocked until the root orchestrator registers this returned artifact in the owning stage manifest
changed_files:
  - scripts/e2e_acceptance/execution.py
  - scripts/e2e_acceptance/live_authority.py
  - scripts/e2e_acceptance/live_producer.py
  - scripts/e2e_acceptance/live_transport.py
  - scripts/e2e_acceptance/production.py
  - scripts/e2e_acceptance/trusted_run.py
  - scripts/run_noor_e2e_acceptance.py
  - tests/test_e2e_acceptance_live_runtime.py
  - tests/test_e2e_acceptance_live_authority.py
  - tests/test_e2e_acceptance_trusted_execution.py
  - .codex/stages/tj-ee5f/artifacts/tj-ee5f.5-production-trust-remediation.md
explicit_defers:
  - root orchestrator must register this returned artifact in .codex/stages/tj-ee5f/stage-manifest.json before artifact validation can pass
  - production invocation and evidence remain with the root orchestrator after integration, review, deploy authority, and fresh preflight
---

# Summary

The lifecycle CLI now selects sealed, authority-bound production components
instead of constructing a fake transport for a live plan. Fixed read-only SSH
sources materialize baseline, final inventory, action reconciliation, and each
execution observation. The producer preserves exact raw bytes and publishes
typed transcript timing, token/cost, tool trace, and side-effect disposition
facts into the protected evidence chain. The correction wave adds a protected
v3 authority receipt covering the canonical runtime transport configuration.
The webhook origin must match the approved runtime identity, while the SSH host
and exact readback commands are committed by digest. Unknown-action readback
now carries the exact reservation and causal event and must be observed after
the durable permit-consume or later action boundary.

# Scope / Routing

This stream changes only the E2E trust boundary and its focused tests. Existing
runtime-less fixture plans keep the local fake path for test compatibility.
Live plans bind the webhook target, collector, SSH host alias, and allowlisted
commands inside both the protected authority receipt and sealed run-plan
digest. Runtime-less v2 fixture authority remains supported; attempting to use
it for a live runtime fails closed because it has no runtime transport digest.

# Verification

Focused red-green tests cover live plan binding, real CLI dispatch/readback,
duration and cost materialization, exact side-effect coverage, independently
reported action cost, and mixed-run transcript ordering. The correction RED
also reproduced arbitrary endpoint/SSH/command substitution, missing causal
identity, and acceptance of a pre-dispatch snapshot; all focused GREEN targets
now pass. Focused Ruff, formatting, and materialization compatibility passed.
Artifact validation is blocked only by stage-manifest registration, which is
outside this stream's write-zone and belongs to the root orchestrator during
integration.

# Delivery / Cleanup

Returned as one local commit for orchestrator review and cherry-pick. No push,
deploy, paid model call, provider message, production mutation, or external
cleanup was performed.

# Risks / Follow-ups / Explicit Defers

The production run still requires a fresh sealed runtime plan with the actual
approved SSH command allowlist and target digest. Unknown or uncovered effects
remain fail-closed. The root orchestrator owns integration, independent review,
stage-manifest artifact registration, authorized deploy, production acceptance,
and final cleanup.
