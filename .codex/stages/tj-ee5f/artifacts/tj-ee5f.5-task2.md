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
milestone_status: accepted
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
status: accepted
delivery_method: merge
accepted_by_orchestrator: yes
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
  - final independent full-range review: 0 P0, 3 P1, 1 P2; all three P1 corrected, P2 explicitly deferred
  - correction RED/GREEN: caller-authored PASS/FAIL recovery, exact criterion/execution evidence refs, and fictional defect lineage
  - final uv run pytest tests/test_e2e_acceptance_*.py -q --tb=short: passed 360
  - final uv run ruff check src/ tests/: passed
  - final uv run ruff format --check src/ tests/: passed, 317 files
  - final uv run mypy src/: passed, 163 source files
  - final uv run pytest tests/ -q --tb=short: passed 2240, skipped 19
  - final scripts/orchestration/run_process_verification.sh: passed
  - current correction and full branch history phone-pattern scans: zero matches
changed_files:
  - scripts/e2e_acceptance/execution.py
  - scripts/e2e_acceptance/production.py
  - scripts/e2e_acceptance/runner.py
  - scripts/e2e_acceptance/trusted_run.py
  - scripts/run_noor_e2e_acceptance.py
  - scripts/e2e_acceptance/coordinator.py
  - tests/test_e2e_acceptance_coordinator.py
  - tests/test_e2e_acceptance_final_review.py
  - tests/test_e2e_acceptance_production.py
  - tests/test_e2e_acceptance_trusted_execution.py
  - .codex/stages/tj-ee5f/artifacts/tj-ee5f.5-task2.md
  - .codex/stages/tj-ee5f/stage-manifest.json
explicit_defers:
  - Task 3 remains the separately authorized, sequential execution of any real external action.
---

# Summary

Added and accepted the local-only production trust facade: capability-dispatched fake transports, a permit-bound webhook adapter, protected producer/collector contracts, the exact 29-unit coordinator lifecycle, derived candidate materialization, defect ledger, and crash recovery. Raw request and response material remains under the protected journal; tracked projections contain redacted payloads plus checksums.

# Scope / Routing

The assigned write zone is limited to adapter/collector/CLI contracts and focused tests. No network, subprocess, provider, production, customer, CRM, quotation, order, Telegram, deployment, or cleanup behavior exists in this stream. Dispatch is by typed capability only; it contains no scenario-ID branch.

# Verification

The first focused adapter tests were RED because `production.py` did not exist. Additional RED/GREEN passes closed producer-owned baseline/final collection, exact lifecycle and materialization, sealed plan/evaluator drift, typed capability routing, permit ordering, raw/tracked separation, crash recovery, unknown-action reconciliation, and exact gate replay. The final independent review found three P1 trust gaps; the correction wave now revalidates recovered attempts through the protected producer, scopes evidence refs to the exact criterion and owning execution, and rejects unproved defect/fix/retest lineage. Acceptance passed 360 tests and the full repository gate passed 2240 tests with 19 skips.

# Delivery / Cleanup

Accepted for local integration; no external state or production action was performed.

# Risks / Follow-ups / Explicit Defers

Actual network/SSH transports and production attempt, gate, reconciliation, and inventory producers remain unavailable and are the exact Task 3 implementation boundary. The deferred P2 is strict rejection of extra commit fields; all decisive fields are already revalidated. A gate command validates producer-owned protected evidence and never manufactures a result.
