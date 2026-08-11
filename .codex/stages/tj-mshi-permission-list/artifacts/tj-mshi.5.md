---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-mshi-permission-list/stage-manifest.json
stream_owner: tj-mshi.5-root-measurement
orchestration_level: slice_acceptance
scope_kind: product_slice
immediate_consumer: tj-mshi-permission-list-stage-closeout
public_facade: build_system_prompt
bounded_acceptance: frozen-twenty-blind-paired-measurement
non_goals:
  - scoring-ruler-change
  - applicability-map-change
  - deterministic-commitment-check
evidence:
  - protected-run-under-git-common-dir
task_id: tj-mshi.5
epic_id: tj-mshi
stage_id: tj-mshi-permission-list
session_id: tj-mshi-permission-list
milestone: ratified-permission-list-measured
milestone_status: accepted
agent_type: n/a
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: root-owned blind reading on the shared sequential prompt path
repo: treejar
branch: main
base_branch: main
base_commit: 6649d2c
worktree: /home/me/code/treejar
write_zone:
  - docs/reports/2026-08-11-permission-list-measured-round.md
  - .codex
success_criteria:
  - exactly-20-authorized-luna-calls-and-zero-judging-calls
  - root-blind-reading-of-all-20-replies
  - paired-critical-count-does-not-rise
  - dialogs-28-and-789-hold-the-ratified-boundary
  - rules-14-and-15-reported-with-uncertainty-and-applicability
selected_docs:
  - docs/superpowers/specs/2026-08-11-what-noor-may-promise-spec.md
  - docs/plans/2026-08-11-permission-list-plan.md
  - docs/reports/2026-08-11-the-round-after-the-cleanup.md
selected_skills:
  - orchestrator-stage
  - superpowers-verification-before-completion
selected_agents:
  - none
catalog_candidates:
  - none
parallel_group: n/a
depends_on_streams:
  - tj-mshi.4-root-implementation
parallel_decision: sequential
status: accepted
delivery_method: manual integration
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: root-owned main worktree; no child worktree or branch exists
risk_level: high
verification_tier: release
risk_tags:
  - prompt-contract-change
  - paid-model-calls
  - protected-corpus-handling
affected_surfaces:
  - backend
invariants:
  - frozen-scenario-set-and-rulers
  - root-judge-without-second-reader
  - corpus-text-outside-git
docs_impact: behavior
docs_reviewed: updated
docs_review_notes: measured-round report, stage summary, artifact, and handoff record the paired result and instrument limits
verification:
  - frozen preflight: 20 scenarios, scenario digest 2ba7e4fe..., openai/gpt-5.6-luna generation, root-orchestrator judge, no second reader
  - protected run: 20 Luna calls, 0 judging calls, cost 5458 micro-USD
  - root blind reading: 20 replies, 300 criteria, 0 red flags
  - paired bootstrap: weighted delta +0.32 with 95% CI -0.86 to +1.82; raw delta +0.25 with 95% CI -0.10 to +0.70
  - critical count: baseline 1, candidate 1; dialog 28 fixed; dialog 789 fixed
  - rules 14 and 15: 0 to 0, candidate applicable 0/20
  - uv run ruff check src/ tests/: passed
  - uv run ruff format --check src/ tests/: passed over 369 files
  - uv run mypy src/: passed over 173 source files
  - uv run pytest tests/ -v --tb=short: 3561 passed and 19 skipped
  - scripts/orchestration/run_process_verification.sh: passed
changed_files:
  - .codex/handoff.md
  - .codex/stages/tj-ee5f/traceability-manifest.json
  - .codex/stages/tj-mshi-permission-list/stage-manifest.json
  - .codex/stages/tj-mshi-permission-list/summary.md
  - .codex/stages/tj-mshi-permission-list/artifacts/tj-mshi.5.md
  - docs/reports/2026-08-11-permission-list-measured-round.md
explicit_defers:
  - tj-2p4c-supported-sku-numeric-detector-false-positive
  - tj-9dp2-root-judge-public-summary-metadata
---

# Summary

The authorized frozen-twenty round completed with 20/20 coverage and language.
Criticals did not rise, dialog 28 no longer makes an unsupported recruitment
promise, and dialog 789 remains fixed. The paired score movement is inside its
uncertainty and rules 14/15 were inapplicable on all 20 openings, so no general
quality or supported-next-step improvement is claimed.

# Scope / Routing

Root-owned sequential measurement on `main`; no subagent was used because the
blind reading and acceptance boundary have one owner and follow the same prompt
path as `.2` through `.4`. The scoring ruler and applicability map remained
frozen. Corpus-bearing artifacts stayed under the git-common-dir.

# Verification

The root read all 20 replies blind and recorded all 300 criteria with zero red
flags. The generic harness retains one `hallucination` code on dialog 1067,
traced to a supported SKU digit omitted from `_allowed_numbers`; `tj-2p4c`
tracks that frozen-ruler false positive. The actual run-state records
`root-orchestrator` and zero judging calls; `tj-9dp2` tracks the stale GLM label
in the public summary.

Ruff, format, Mypy, the complete Pytest suite, artifact validation, and process
verification passed.

# Delivery / Cleanup

Protected evidence stayed outside Git; tracked files contain identifiers,
integer metrics, intervals, codes, and cost only. No push, deploy, live
mutation, real-user message, or second reader occurred. The root worktree has
no child branch or workspace to clean.

# Risks / Follow-ups / Explicit Defers

The paired delta is inconclusive and rules 14/15 are unreachable on this
frozen first-turn set. `tj-2p4c` and `tj-9dp2` preserve the two measurement
instrument defects without changing the frozen ruler during this stage.
