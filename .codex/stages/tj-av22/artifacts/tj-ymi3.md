---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-av22/stage-manifest.json
stream_owner: operations-worker
orchestration_level: slice_acceptance
scope_kind: product_slice
immediate_consumer: tj-av22.3 integration and approved production reconciliation
public_facade: scripts/escalation_guard.py
bounded_acceptance: local classification, manifest integrity, transaction, rollback, and repeat-run evidence
non_goals:
  - production dry-run or database mutation
  - manager approval of real pending cases
  - real Telegram or WhatsApp delivery
evidence:
  - none
task_id: tj-ymi3
epic_id: tj-av22
stage_id: tj-av22
session_id: tj-av22
milestone: operational-safety-controls
milestone_status: in_progress
agent_type: worker
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: inherited reasoning for bounded high-risk state-transition and atomicity work
repo: treejar
branch: codex/tj-av22-ops
base_branch: codex/tj-av22-stabilization
base_commit: 0db977074dbce3b5d00fe08ecb97a0eeff7ae13f
worktree: /home/me/code/treejar/.worktrees/tj-av22-stabilization/.worktrees/tj-av22-ops
write_zone:
  - src/services/escalation_state.py
  - scripts/escalation_guard.py
  - focused escalation tests
  - docs/operations-runbook.md
success_criteria:
  - default audit is select-only and privacy-safe
  - apply requires an intact archived exact-ID manifest
  - exact apply is transactional and repeats as a no-op
  - ambiguous and active human-owned states remain human review
selected_docs:
  - AGENTS.md
  - .codex/orchestrator.toml
  - docs/superpowers/specs/2026-07-23-noor-stabilization-design.md
  - docs/superpowers/plans/2026-07-23-noor-stabilization.md
selected_skills:
  - systematic-debugging
  - test-driven-development
  - verification-before-completion
selected_agents:
  - built-in worker
catalog_candidates:
  - none
parallel_group: ops
depends_on_streams:
  - none
parallel_decision: parallel
status: returned
delivery_method: n/a
accepted_by_orchestrator: no
cleanup_status: pending
cleanup_notes: branch retained for root review and integration
risk_level: high
verification_tier: slice_acceptance
risk_tags:
  - state-transition
  - atomicity
  - idempotency
  - rollback
  - data
affected_surfaces:
  - database
  - data
  - backend
invariants:
  - state-transition
  - idempotency
  - rollback
  - test-matrix
docs_impact: ops-deploy
docs_reviewed: updated
docs_review_notes: docs/operations-runbook.md documents archive, approval, readback, idempotency, and rollback
verification:
  - uv run pytest focused escalation and maintenance files - 41 passed: passed
  - uv run ruff check changed Python and script files: passed
  - uv run ruff format --check changed Python and script files: passed
  - uv run mypy src/services/escalation_state.py: passed
  - uv run python scripts/escalation_guard.py --help: passed
changed_files:
  - src/services/escalation_state.py
  - scripts/escalation_guard.py
  - tests/test_escalation_state.py
  - tests/test_scripts_escalation_guard.py
  - docs/operations-runbook.md
  - .codex/stages/tj-av22/artifacts/tj-ymi3.md
explicit_defers:
  - tj-ymi3 production dry-run, classification of the live 33-row set, manager approval, exact apply, and post-apply readback remain approval-gated
---

# Summary

Added one repository-derived classification policy and a privacy-safe JSON
audit. Only unambiguous stale row/conversation combinations enter the exact-ID
action set. Apply requires an intact archived manifest, locks and checks every
row before mutation, commits once, rolls back on mismatch, and reports repeat
runs as already applied. The reconciliation path never sends external alerts.

# Scope / Routing

Work stayed inside the assigned escalation service, script, focused tests, and
operator documentation. The branch was refreshed from
`codex/tj-av22-stabilization@281242c` before this artifact; the merge had no
write-zone conflict. Graphify is not configured, so graph review was not
needed.

# Verification

Fresh post-merge verification passed 41 focused tests, Ruff check and format,
Mypy for the changed service, CLI help, and diff/static safety checks. No
production database, alert channel, or runtime was accessed.

# Delivery / Cleanup

Returned for root review on `codex/tj-av22-ops`. The worker did not merge into
the integration branch, push, deploy, or clean the worktree.

# Risks / Follow-ups / Explicit Defers

The live 33-row disposition is deliberately not claimed: it requires an
approved production dry-run. Any real pending case remains manager review.
Committed reconciliation has no broad automatic inverse; the runbook requires
an approved exact-ID recovery transaction using the archived pre-state.
