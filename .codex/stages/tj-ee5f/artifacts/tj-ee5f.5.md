---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-ee5f/stage-manifest.json
stream_owner: tj-ee5f.5-task1-trust-core
orchestration_level: slice_acceptance
scope_kind: foundation
immediate_consumer: tj-ee5f.5-task2-production-adapters
public_facade: scripts/e2e_acceptance execution trust contracts
bounded_acceptance: local fixture-only trusted authorization, permits, transcript and closeout contracts
non_goals:
  - production, provider, customer, CRM, deploy, or cleanup action
evidence:
  - none
task_id: tj-ee5f.5
epic_id: tj-ee5f
stage_id: tj-ee5f
session_id: tj-ee5f.5
milestone: trusted production execution and evidence core
milestone_status: accepted
agent_type: worker
subagent_model: inherit_orchestrator
reasoning_effort: high
model_reasoning_rationale: authorization, side-effect integrity, and immutable evidence are high-risk contracts
repo: treejar
branch: codex/tj-ee5f-production-execution
base_branch: main
base_commit: 75f57b7
worktree: /home/me/code/treejar/.worktrees/tj-ee5f-production-execution
write_zone:
  - scripts/e2e_acceptance/execution.py
  - scripts/e2e_acceptance/policy.py
  - scripts/e2e_acceptance/trusted_run.py
  - scripts/e2e_acceptance/evidence.py
  - tests/test_e2e_acceptance_*.py
  - .codex/stages/tj-ee5f/artifacts/tj-ee5f.5.md
  - .codex/stages/tj-ee5f/stage-manifest.json
success_criteria:
  - approved v1/preflight bridge carries only exact digest-bound v2 authority
  - permits bind exact request identity, consume quota before I/O, and fail closed on drift or reuse
  - reports bind turns to committed transcript/producer identities and permit zero turns only for typed gate outcomes
  - finalization no longer accepts caller-owned side-effect closeout
selected_docs:
  - AGENTS.md
  - .codex/orchestrator.toml
  - .codex/handoff.md
  - docs/superpowers/plans/2026-07-28-noor-task3-production-trust-repair.md
selected_skills:
  - superpowers:systematic-debugging
  - superpowers:test-driven-development
selected_agents:
  - none
catalog_candidates:
  - none
parallel_group: tj-ee5f-production-trust
depends_on_streams:
  - tj-ee5f.3-policy-v2
parallel_decision: local
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
  - state-transition
  - idempotency
  - retry
  - data
affected_surfaces:
  - backend
  - data
invariants:
  - state-transition
  - idempotency
  - rollback
docs_impact: api-contract
docs_reviewed: updated
docs_review_notes: this stage artifact records the new local trust contract; no end-user documentation changed
verification:
  - RED focused authorization/permit/transcript/closeout tests: failed as expected before implementation
  - uv run pytest tests/test_e2e_acceptance_*.py -q: passed 211
  - uv run ruff check src/ tests/: passed
  - uv run ruff format --check src/ tests/: passed
  - uv run mypy src/: passed (163 source files)
  - scripts/orchestration/run_process_verification.sh: passed
  - uv run pytest tests/ -v --tb=short: blocked by seven pre-existing frontend checks because local esbuild is absent; 2084 passed, 19 skipped
changed_files:
  - scripts/e2e_acceptance/execution.py
  - scripts/e2e_acceptance/trusted_run.py
  - tests/test_e2e_acceptance_trusted_execution.py
  - tests/test_e2e_acceptance_trusted_report.py
  - tests/test_e2e_acceptance_final_review.py
  - .codex/stages/tj-ee5f/artifacts/tj-ee5f.5.md
  - .codex/stages/tj-ee5f/stage-manifest.json
explicit_defers:
  - Task 2 owns production adapters, collector, and CLI wiring; no local contract in this task authorizes external I/O
---

# Summary

Added the local trusted-execution core for Task 1. An executable v2 authorization
can be built only from typed v1/preflight inputs, action permits are request-bound
and one-use, report turns carry protected transcript/receipt identities, and the
run document derives closeout from bound ledger/inventory identities rather than a
caller-supplied status.

# Scope / Routing

The changed path is local-only: policy/manifest input enters the v1 bridge,
`ProtectedExecutionJournal` reserves and consumes one action permit, and
`trusted_run` verifies report/side-effect identities before exposing rollups.
Production adapters and all external transport remain outside this stream.

# Verification

The focused RED suite failed before implementation for each contract family.
The focused acceptance suite passed 211 tests after implementation. Ruff, format,
Mypy, and process verification passed. The full suite reached 2084 passed and 19
skipped; seven unrelated frontend regression tests could not load the missing local
`esbuild` package.

# Delivery / Cleanup

Returned for orchestrator review; no Git merge, push, production action, or
external cleanup was performed.

# Risks / Follow-ups / Explicit Defers

Task 2 must pass the exact permit parameters immediately before its real adapter
I/O and produce protected transcript/ledger artifacts. The local core intentionally
does not expose a transport or fallback path that could bypass these checks.
