---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-ee5f/stage-manifest.json
stream_owner: tj-ee5f.5-task3-live-boundary
orchestration_level: integration
scope_kind: foundation
immediate_consumer: tj-ee5f-task3-authorized-execution
public_facade: scripts/run_noor_e2e_acceptance.py
bounded_acceptance: exact protected authority, one-shot live transports, and honest zero-turn production gates
non_goals:
  - no live HTTP, SSH, provider, customer, CRM, quotation, Telegram, cleanup, deploy, or paid action in this implementation stream
evidence:
  - none
task_id: tj-ee5f.5-task3-live-boundary
epic_id: tj-ee5f
stage_id: tj-ee5f
session_id: tj-ee5f.5
milestone: production authorization and transport boundary
milestone_status: accepted
agent_type: worker
subagent_model: inherit_orchestrator
reasoning_effort: high
model_reasoning_rationale: authorization, privacy, one-shot dispatch, and fail-closed evidence are high-risk contracts
repo: treejar
branch: codex/tj-ee5f-task3-live-transports
base_branch: main
base_commit: 3b618c36e9945dcbea2c09710a9b2f5370aa8de8
worktree: /home/me/code/treejar/.worktrees/tj-ee5f-task3-live-transports
write_zone:
  - scripts/e2e_acceptance/live_authority.py
  - scripts/e2e_acceptance/live_transport.py
  - scripts/e2e_acceptance/live_producer.py
  - scripts/e2e_acceptance/production.py
  - scripts/e2e_acceptance/coordinator.py
  - scripts/e2e_acceptance/trusted_run.py
  - scripts/run_noor_e2e_acceptance.py
  - tests/test_e2e_acceptance_live_*.py
success_criteria:
  - exact protected live inputs commit an authority bundle without exposing raw targets
  - Wazzup HTTP dispatch is one-shot with no redirect or retry and uncertain post-dispatch handling
  - SSH readback is fixed-allowlist and read-only
  - blocked scenarios publish zero turns without inventing Q/A
  - passing or failing executed scenarios still require exact transcript turns
selected_docs:
  - AGENTS.md
  - .codex/orchestrator.toml
  - .codex/handoff.md
  - docs/superpowers/plans/2026-07-28-noor-task3-production-trust-repair.md
selected_skills:
  - orchestrator-stage
  - superpowers:test-driven-development
  - superpowers:systematic-debugging
selected_agents:
  - backend_developer
catalog_candidates:
  - none
parallel_group: tj-ee5f-task3-live-boundary
depends_on_streams:
  - tj-ee5f.5-task2
parallel_decision: parallel
status: accepted
delivery_method: merge
accepted_by_orchestrator: yes
cleanup_status: not_applicable
cleanup_notes: external execution has not started
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
docs_impact: api-contract
docs_reviewed: updated
docs_review_notes: refreshed the handoff source digest after the accepted current-state handoff changed
verification:
  - focused live authority, transport, and producer tests: passed 24
  - complete acceptance suite: passed 380
  - focused live-module Mypy: passed 4 modules
  - focused Ruff, format, and git diff check: passed
  - worker authority stream: passed 8 tests
  - worker transport stream and P1 correction: passed 13 tests
  - gate-only zero-action correction: passed 14 focused tests
  - gate publication acceptance correction: passed 14 focused tests
  - post-commit gate journal registration: passed 14 focused tests and 1 gate replay test
  - zero-turn transcript manifest: passed 15 focused tests
  - typed published gate quartet: passed 16 focused tests
  - final protected run `tj-ee5f-live-20260728t165236z`: verified and finalized
  - independent full-range review: one P1 found and corrected; all other requested boundaries approved
  - full release Pytest: passed 2260, skipped 19
  - full release Ruff, format, and Mypy over 163 source files: passed
changed_files:
  - .codex/stages/tj-ee5f/traceability-manifest.json
  - .codex/stages/tj-ee5f/stage-manifest.json
  - .codex/stages/tj-ee5f/artifacts/tj-ee5f.5-task3-live-boundary.md
  - .superpowers/sdd/tj-ee5f-task3-live-authority-report.md
  - .superpowers/sdd/tj-ee5f-task3-live-transport-report.md
  - scripts/e2e_acceptance/live_authority.py
  - scripts/e2e_acceptance/live_transport.py
  - scripts/e2e_acceptance/live_producer.py
  - scripts/e2e_acceptance/production.py
  - scripts/e2e_acceptance/coordinator.py
  - scripts/e2e_acceptance/trusted_run.py
  - scripts/run_noor_e2e_acceptance.py
  - tests/test_e2e_acceptance_live_authority.py
  - tests/test_e2e_acceptance_live_transport.py
  - tests/test_e2e_acceptance_live_producer.py
explicit_defers:
  - exact production preflight and sequential acceptance execution remain the next authorized stream
---

# Summary

Added the minimal real Task 3 boundary: fixed protected authority inputs,
one-shot HTTPS, fixed read-only SSH, and a code-owned conservative gate that
can only publish `BLOCKED` for the next canonical unit. Scenario gates now
retain zero turns; executed `PASS` or `FAIL` scenarios still require transcript
facts. Gate-only runs no longer need a dummy action or reconciliation step.
Each protected gate publication is accepted atomically before the next
canonical execution can be issued.

# Verification

The complete acceptance suite passed 380 tests. Focused Mypy, Ruff, formatting,
and diff checks passed. The one full-range review found a mutable SSH argument
surface; `find` and `journalctl` were removed from the executable allowlist and
four negative regressions now pass. The full repository suite passed 2260 tests
with 19 skips. No live or paid action was performed.

# Risks / Follow-ups / Explicit Defers

The boundary does not by itself prove a unit executable. Fresh production
preflight must still bind the exact protected runtime and synthetic targets.
Units without proven isolation, provider origin, cleanup, or independent
evidence remain non-passing.

# Final protected run

Run `tj-ee5f-live-20260728t165236z` finalized against repository commit
`deab79b1134210a9d1fbb7691137363263e1cd98`, CI
`github-actions-30379943318`, and deployed release
`0dd9615a16fdf4eb17abe156551c53fb77f39c21`.

- `coverage_complete=true`
- `execution_complete=true`
- `requirements_met=false`
- 29/29 execution units: `BLOCKED`
- external actions, model calls, messages, and cost: zero
- tracked redacted result:
  `.codex/stages/tj-ee5f/results/tj-ee5f-live-20260728t165236z/`
- client Markdown:
  `docs/client/noor-e2e-acceptance-2026-07-28.md`
