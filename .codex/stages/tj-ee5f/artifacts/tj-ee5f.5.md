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
milestone_status: returned
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
  - superpowers:receiving-code-review
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
  - initial independent full-range review decision: FIX
  - correction RED proved caller final readback, incomplete gate provenance, incomplete transcript receipt provenance, and unbound retention authority
  - second correction RED proved dataclass authority-handle substitution, quota undercharge/settlement gaps, and caller-shaped exclusion/retention authority gaps
  - reviewer FIX D RED proved late cost settlement regressed final_turn_anchored back to executing and duplicate replay reopened without rejection
  - reviewer FIX D focused RED to GREEN: passed 2
  - correction focused trust suite: passed 163
  - protected execution authority semantic-drift slice: passed 4
  - uv run pytest tests/test_e2e_acceptance_*.py -q --tb=short: passed 253
  - uv run ruff check src/ tests/ scripts/e2e_acceptance: passed
  - uv run ruff format --check src/ tests/ scripts/e2e_acceptance: passed, 324 files
  - uv run mypy src/: passed (163 source files)
  - strict module-mode Mypy for policy execution trusted_run and evidence: passed
  - scripts/orchestration/run_process_verification.sh: passed
  - uv run pytest tests/ -q --tb=short: passed 2133, skipped 19
  - current-tree exact and separator-normalized protected-identity scans: zero matches
  - full Task 1 delta exact and separator-normalized protected-identity scans: zero matches
  - full Task 1 delta blocked-secret scan: zero matches
  - artifact validator: passed
  - check_stage_ready tj-ee5f: reported structurally ready; stage was not closed and this returned artifact remains unaccepted
  - git diff --check: passed
changed_files:
  - scripts/e2e_acceptance/evidence.py
  - scripts/e2e_acceptance/execution.py
  - scripts/e2e_acceptance/trusted_run.py
  - tests/test_e2e_acceptance_evidence.py
  - tests/test_e2e_acceptance_trusted_execution.py
  - tests/test_e2e_acceptance_trusted_report.py
  - tests/test_e2e_acceptance_final_review.py
  - .codex/stages/tj-ee5f/artifacts/tj-ee5f.5.md
explicit_defers:
  - Task 2 must provide the real protected collector, gate, transcript, and inventory producers plus adapter and CLI wiring; fixture-only Task 1 producers authorize no external I/O
---

# Summary

Added the local trusted-execution core for Task 1. An executable v2 authorization
can be built only from typed v1/preflight inputs, action permits are request-bound
and one-use, and committed attempts are typed as executed or gate variants. The
issued authority handle is identity-registered so dataclass replacement cannot
substitute a broader authorization. Each protected action binds its exact
messages, model calls, maximum cost, and cost-settlement mode; an independently
terminal action may record bounded actual cost without refunding the charged
maximum or weakening retry safety. Settlement is permitted only while the
journal remains in the executing phase; late, duplicate, nonterminal, and
phase-regressive replay attempts fail closed without reopening finalization.
Final inventory is accepted only from a fresh protected independent collector
artifact and producer receipt bound to the exact authorization, preflight,
collector, journal head, final-turn anchor, and inventory digest. Report turns
carry protected transcript/receipt identities bound to the authorization,
attempt digest, phase head, and exact ordered manifest path set. The run document
derives closeout from an authority-bound ledger and independently committed
inventory rather than a caller-supplied status. Client exclusions and retained
artifacts require receipt-covered typed issuer grants bound to exact execution,
criteria, owner, cleanup authority, and validity windows.

# Scope / Routing

The changed path is local-only: policy/manifest input enters the v1 bridge,
`ProtectedExecutionJournal` reserves and consumes one action permit, and
`trusted_run` independently verifies collector, gate, transcript, retention, and
side-effect identities before exposing rollups. Production adapters, real
producer implementations, and all external transport remain outside this stream.

# Verification

The independent full-range reviews returned `FIX`; none accepted the stream.
The corrections close the final-collector/inventory,
retention-authority, typed-gate, transcript-provenance, authority-handle
substitution, quota-charge settlement, and protected client-authority findings.
Reviewer FIX D additionally closes the late-settlement phase regression and
duplicate replay path. Fresh correction evidence passed 163 focused trust
tests, 253 acceptance-contract tests, and the full local suite with 2133 passed
and 19 skipped. Ruff, format, both Mypy scopes, process verification,
exact/normalized privacy scans, the blocked-secret scan, and `git diff --check`
also passed. These results return the stream for a new orchestrator review; they
do not record acceptance.

# Delivery / Cleanup

Returned for orchestrator review with `accepted_by_orchestrator: no`; no Git
merge, push, production action, business action, or external cleanup was
performed.

# Risks / Follow-ups / Explicit Defers

Task 2 must pass the exact permit parameters immediately before its real adapter
I/O and implement the real protected collector, gate, transcript, and final
inventory producers. The local core intentionally exposes only fixture producers
and no transport or fallback path that could bypass these checks.
