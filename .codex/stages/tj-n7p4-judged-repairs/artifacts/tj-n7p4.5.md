---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-n7p4-judged-repairs/stage-manifest.json
stream_owner: tj-n7p4.5-root-measurement
orchestration_level: slice_acceptance
scope_kind: product_slice
immediate_consumer: tj-n7p4-root-closeout
public_facade: real_opening_acceptance
bounded_acceptance: frozen-twenty-blind-measured-round
non_goals:
  - paid-scoring-reader
  - live-traffic-or-deployment
  - frozen-rubric-or-detector-change
evidence:
  - protected-blind-reading-and-paired-comparison
task_id: tj-n7p4.5
epic_id: tj-n7p4
stage_id: tj-n7p4-judged-repairs
session_id: tj-n7p4-judged-repairs
milestone: measured-repair-architecture
milestone_status: accepted
agent_type: n/a
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: root-owned sequential measurement preserves the shared provider journal blind-reading and cost boundary
repo: treejar
branch: main
base_branch: main
base_commit: 0764ce2
worktree: /home/me/code/treejar
write_zone:
  - docs/reports/2026-08-11-repair-architecture-measured-round.md
  - .codex
success_criteria:
  - exact-twenty-luna-calls-and-only-triggered-repair-calls
  - root-blind-reading-without-paid-scoring-reader
  - complete-coverage-and-language
  - critical-failures-do-not-rise
  - trigger-answer-fallback-cost-and-rewrite-counts-reported
selected_docs:
  - docs/superpowers/specs/2026-08-11-nothing-is-deleted-without-a-judge-spec.md
  - docs/plans/2026-08-11-orchestrator-prompt.md
  - docs/reports/2026-08-11-the-round-after-the-cleanup.md
selected_skills:
  - orchestrator-stage
  - superpowers-systematic-debugging
  - superpowers-verification-before-completion
selected_agents:
  - none
catalog_candidates:
  - none
parallel_group: n/a
depends_on_streams:
  - tj-n7p4.4
parallel_decision: sequential
status: accepted
delivery_method: manual integration
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: root-owned main worktree; protected corpus remains under git-common-dir and no child worktree or branch exists
risk_level: high
verification_tier: release
risk_tags:
  - authorization
  - data
affected_surfaces:
  - backend
invariants:
  - protected-corpus-stays-outside-git
  - zero-paid-scoring-calls
  - no-trigger-no-repair-call
  - no-rise-in-critical-failure-count
docs_impact: behavior
docs_reviewed: updated
docs_review_notes: measured-round report stage summary and handoff record calls costs blind reading paired uncertainty and instrument limits
verification:
  - protected preflight: exact frozen digest and zero paid calls before dispatch
  - paid round: exactly 20 Luna calls 0 repair calls and 0 scoring calls
  - protected state: 20 generation records 20 root judgments and 20 language matches
  - root blind reading: all 20 replies and 300 criteria read before baseline comparison with 0 red flags
  - repair trace: 0 flags approvals corrections cannot-fix rejected corrections fallbacks provider failures and rewrite comparisons
  - paired result: criticals 1 to 1; weighted delta +1.16 with 95 percent interval -0.28 to +3.00; raw delta +0.50 with interval +0.05 to +1.10
  - cost: round 0.005444 USD; both stages including one .3 repair call 0.012167216 USD against 2.00 USD authority
  - uv run ruff check src/ tests/: passed
  - uv run ruff format --check src/ tests/: passed over 373 files
  - uv run mypy src/: passed over 174 source files
  - initial full Pytest exposed missing mandatory handoff labels; focused reproduction passed after restoring them
  - uv run pytest tests/ -v --tb=short: 3594 passed and 19 skipped on the final rerun
  - scripts/orchestration/run_process_verification.sh: passed
changed_files:
  - .codex/handoff.md
  - .codex/stages/tj-ee5f/traceability-manifest.json
  - .codex/stages/tj-n7p4-judged-repairs/stage-manifest.json
  - .codex/stages/tj-n7p4-judged-repairs/summary.md
  - .codex/stages/tj-n7p4-judged-repairs/artifacts/tj-n7p4.5.md
  - docs/reports/2026-08-11-repair-architecture-measured-round.md
explicit_defers:
  - tj-2p4c-known-sku-numeric-detector-false-positive
  - tj-9dp2-stale-public-judge-label
---

# Summary

The frozen twenty completed with full response, judgment, and language
coverage. No removal flag fired, so the production-parity harness made no
repair call and changed no clean model-written reply. Public criticals stayed
at one; the candidate event is the frozen detector's known SKU false positive.

# Scope / Routing

The root owned generation, blind reading, protected accounting, and paired
comparison as one sequential boundary. Baseline scores were not opened until
the current root judgment was durably ingested. Corpus text never entered Git.

# Verification

The journal proves 20 Luna calls and zero repair or scoring calls. The root read
all replies and criteria, then compared redacted integer results with the
baseline. Weighted movement is inconclusive; the positive raw movement cannot
be attributed to repair because no repair fired. Static checks, types, and all
repository tests pass. A missing handoff-label failure was reproduced and
fixed before the successful full rerun.

# Delivery / Cleanup

Accepted directly in the root worktree for one local child commit. Protected
evidence stays under `.git` with private modes. No push, deploy, live mutation,
model-configuration change, real-user message, or paid scoring call occurred.

# Risks / Follow-ups / Explicit Defers

The frozen numeric detector still mistakes digits inside a supported SKU for
an unsupported number (`tj-2p4c`), and the public summary still labels the root
judge as GLM (`tj-9dp2`). Neither frozen ruler changed during this round.
