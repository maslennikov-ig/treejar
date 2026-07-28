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
  - scripts/e2e_acceptance/production.py
  - scripts/e2e_acceptance/runner.py
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
  - none
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
  - focused production/runner tests: passed 9
  - uv run --extra dev pytest tests/test_e2e_acceptance_*.py -q --tb=short: passed 270
  - uv run --extra dev ruff check src/ tests/ scripts/e2e_acceptance/ scripts/run_noor_e2e_acceptance.py: passed
  - uv run --extra dev ruff format --check src/ tests/ scripts/e2e_acceptance/ scripts/run_noor_e2e_acceptance.py: passed, 327 files
  - uv run --extra dev mypy src/: passed, 163 source files
  - scripts/orchestration/run_process_verification.sh: passed
  - artifact validator and git diff --check: passed
  - exact added-file privacy and secret scans: zero matches
  - uv run --extra dev pytest tests/ -q --tb=short: blocked by seven unrelated frontend assertions because local esbuild is unavailable; remaining result 2143 passed, 19 skipped
changed_files:
  - scripts/e2e_acceptance/production.py
  - scripts/e2e_acceptance/runner.py
  - scripts/run_noor_e2e_acceptance.py
  - tests/test_e2e_acceptance_production.py
  - .codex/stages/tj-ee5f/artifacts/tj-ee5f.5-task2.md
  - .codex/stages/tj-ee5f/stage-manifest.json
explicit_defers:
  - Task 3 remains the separately authorized, sequential execution of any real external action.
---

# Summary

Added local-only, capability-dispatched fake transports and a permit-bound webhook adapter. Raw request and response material remains under the protected journal; tracked projections contain redacted payloads plus checksums. The read-only collector has no mutation API and produces the Task 1 final readback artifact and receipt layout. The CLI can prepare, preflight, resume, validate an independently produced gate, and finalize only a terminal committed run.

# Scope / Routing

The assigned write zone is limited to adapter/collector/CLI contracts and focused tests. No network, subprocess, provider, production, customer, CRM, quotation, order, Telegram, deployment, or cleanup behavior exists in this stream. Dispatch is by typed capability only; it contains no scenario-ID branch.

# Verification

The first focused adapter tests were RED because `production.py` did not exist. They are GREEN after implementation. Additional final-collector testing caught a readback-digest mismatch, then passed after the final observation was rebuilt rather than mutated in place. Acceptance tests pass 270/270; Ruff, format, Mypy over `src`, artifact validation, privacy checks and process verification pass. The full repository suite is blocked only by missing local `esbuild` in seven pre-existing frontend regression tests; it otherwise reached 2143 passed and 19 skipped.

# Delivery / Cleanup

Returned for orchestrator review; no external state or local worktree cleanup was performed.

# Risks / Follow-ups / Explicit Defers

Actual transports intentionally remain unavailable. Task 3 must supply current explicit authorization and a fresh exact preflight before an external action can be attempted. A gate command validates producer-owned protected evidence; it never manufactures a gate result.
