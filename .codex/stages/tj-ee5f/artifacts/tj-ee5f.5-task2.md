---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-ee5f/stage-manifest.json
stream_owner: tj-ee5f.5-task2-production-adapters
orchestration_level: slice_acceptance
scope_kind: foundation
immediate_consumer: tj-ee5f-task3-authorized-execution
public_facade: scripts/e2e_acceptance/runner.py and scripts/run_noor_e2e_acceptance.py
bounded_acceptance: local fake capability adapters, protected collector and resumable CLI contracts
non_goals:
  - network, SSH, provider, production, customer, CRM, quotation, order, Telegram, deploy, or cleanup action
evidence:
  - none
task_id: tj-ee5f.5-task2
epic_id: tj-ee5f
stage_id: tj-ee5f
session_id: tj-ee5f.5
milestone: production capability adapters, collector, and runnable CLI
milestone_status: in_progress
agent_type: worker
subagent_model: inherit_orchestrator
reasoning_effort: high
model_reasoning_rationale: permit, protected evidence, crash recovery, and read-only collection are high-risk contracts
repo: treejar
branch: codex/tj-ee5f-production-adapters
base_branch: main
base_commit: 48493b679423aa679aefe513f1eaf47f37ed17e7
worktree: /home/me/code/treejar/.worktrees/tj-ee5f-production-adapters
write_zone:
  - scripts/e2e_acceptance/execution.py
  - scripts/e2e_acceptance/production.py
  - scripts/e2e_acceptance/runner.py
  - scripts/e2e_acceptance/trusted_run.py
  - scripts/run_noor_e2e_acceptance.py
  - tests/test_e2e_acceptance_*.py
  - .codex/stages/tj-ee5f/artifacts/tj-ee5f.5-task2.md
  - .codex/stages/tj-ee5f/stage-manifest.json
success_criteria:
  - typed capabilities, not scenario IDs, select local fake transports
  - protected raw adapter and collector responses have only redacted checksum projections
  - the independent collector writes the exact Task 1 final artifact and producer receipt layout
  - lifecycle commands fail closed on authority, plan, journal, gate, and finalization drift
selected_docs:
  - AGENTS.md
  - .codex/orchestrator.toml
  - .codex/handoff.md
  - .superpowers/sdd/tj-ee5f.5-task2-brief.md
  - docs/superpowers/plans/2026-07-28-noor-task3-production-trust-repair.md
selected_skills:
  - superpowers:test-driven-development
selected_agents:
  - backend_developer
  - correctness_reviewer
catalog_candidates:
  - none
parallel_group: tj-ee5f-production-trust
depends_on_streams:
  - tj-ee5f.5
parallel_decision: sequential
status: returned
delivery_method: cherry-pick
accepted_by_orchestrator: no
cleanup_status: not_applicable
cleanup_notes: no external state was created
risk_level: high
verification_tier: integration
risk_tags:
  - authorization
  - security
  - retry
  - idempotency
  - state-transition
  - data
affected_surfaces:
  - backend
  - data
invariants:
  - state-transition
  - idempotency
  - rollback
docs_impact: api-contract
docs_reviewed: no-change-needed
docs_review_notes: local-only implementation contract; no user documentation changed
verification:
  - RED focused production adapter tests: failed as expected before implementation
  - initial focused production/runner tests: passed 9
  - initial uv run --extra dev pytest tests/test_e2e_acceptance_*.py -q --tb=short: passed 270
  - uv run --extra dev ruff check src/ tests/ scripts/e2e_acceptance/ scripts/run_noor_e2e_acceptance.py: passed
  - uv run --extra dev ruff format --check src/ tests/ scripts/e2e_acceptance/ scripts/run_noor_e2e_acceptance.py: passed, 327 files
  - uv run --extra dev mypy src/: passed, 163 source files
  - scripts/orchestration/run_process_verification.sh: passed
  - artifact validator and git diff --check: passed
  - exact added-file privacy and secret scans: zero matches
  - Correction A/B focused adapter/runner tests: passed 16
  - Correction A/B uv run --extra dev pytest tests/test_e2e_acceptance_*.py -q --tb=short: passed 277
  - final protected lifecycle and snapshot focused matrix: passed 179
  - final uv run --extra dev pytest tests/test_e2e_acceptance_*.py -q --tb=short: passed 298
  - final uv run --extra dev ruff check src/ tests/ scripts/e2e_acceptance/ scripts/run_noor_e2e_acceptance.py: passed
  - final uv run --extra dev ruff format --check src/ tests/ scripts/e2e_acceptance/ scripts/run_noor_e2e_acceptance.py: passed, 327 files
  - final uv run --extra dev mypy src/: passed, 163 source files
  - final git diff --check: passed
changed_files:
  - scripts/e2e_acceptance/execution.py
  - scripts/e2e_acceptance/production.py
  - scripts/e2e_acceptance/runner.py
  - scripts/e2e_acceptance/trusted_run.py
  - scripts/run_noor_e2e_acceptance.py
  - tests/test_e2e_acceptance_final_review.py
  - tests/test_e2e_acceptance_production.py
  - tests/test_e2e_acceptance_trusted_execution.py
  - .codex/stages/tj-ee5f/artifacts/tj-ee5f.5-task2.md
  - .codex/stages/tj-ee5f/stage-manifest.json
explicit_defers:
  - Task 3 remains the separately authorized, sequential execution of any real external action.
---

# Summary

Added local-only, capability-dispatched fake transports and a permit-bound webhook adapter. Raw request and response material remains under the protected journal; tracked projections contain redacted payloads plus checksums. The read-only collector has no mutation API and produces the Task 1 baseline/final readback artifacts and receipts. The CLI can prepare, preflight, resume, reconcile an uncertain action, validate an independently produced gate, and finalize only a terminal committed run through a strict production snapshot.

# Scope / Routing

The assigned write zone is limited to adapter/collector/CLI contracts and focused tests. No network, subprocess, provider, production, customer, CRM, quotation, order, Telegram, deployment, or cleanup behavior exists in this stream. Dispatch is by typed capability only; it contains no scenario-ID branch.

# Verification

The first focused adapter tests were RED because `production.py` did not exist. Additional RED/GREEN passes closed producer-owned baseline/final collection, sealed plan/evaluator drift, typed capability routing, permit ordering, raw/tracked separation, partial producer recovery, unknown-action reconciliation and settlement recovery, exact gate replay, unsafe run IDs, and intermediate-symlink snapshot writes. The strict production snapshot validates candidate checksums and the complete publication projection before its first write, binds independent final-causal and terminal-journal heads, and recovers only byte-identical partial commits. The artifact remains returned and unaccepted pending a fresh independent review and full repository gates.

# Delivery / Cleanup

Returned for orchestrator review; no external state or local worktree cleanup was performed.

# Risks / Follow-ups / Explicit Defers

Actual transports intentionally remain unavailable. Task 3 must supply current explicit authorization, production transports, and a fresh exact preflight before an external action can be attempted. A gate command validates producer-owned protected evidence; it never manufactures a gate result. Full repository Pytest, process verification, privacy/secret scans, artifact validation, and independent review remain pending at this returned checkpoint.
