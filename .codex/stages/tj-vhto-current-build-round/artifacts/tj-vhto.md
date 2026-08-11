---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-vhto-current-build-round/stage-manifest.json
stream_owner: tj-vhto-root-measurement
orchestration_level: slice_acceptance
scope_kind: product_slice
immediate_consumer: owner-decision
public_facade: real_opening_acceptance
bounded_acceptance: one-blind-round-on-the-shipped-build
non_goals:
  - paid-second-reader
  - client-comparison
  - conversion-claim
evidence:
  - protected-round-under-git-common-dir
task_id: tj-vhto
epic_id: tj-vhto
stage_id: tj-vhto-current-build-round
session_id: tj-vhto-current-build-round
milestone: a-current-number-with-its-limits-named
milestone_status: accepted
agent_type: n/a
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: root-owned measurement and blind reading; the judge may not be delegated
repo: treejar
branch: main
base_branch: main
base_commit: 3682203
worktree: /home/me/code/treejar
write_zone:
  - scripts/corpus_bridge/pair_rounds.py
  - tests/test_corpus_bridge_pair_rounds.py
  - docs/reports/2026-08-11-where-the-bot-stands-on-the-shipped-build.md
  - .codex
success_criteria:
  - twenty-generation-calls-and-zero-scoring-calls
  - complete-coverage-and-language
  - score-cut-by-attainable-ceiling
  - every-delta-attributed-or-refused
selected_docs:
  - docs/reports/2026-08-11-permission-list-measured-round.md
  - docs/reports/2026-08-11-repair-architecture-measured-round.md
selected_skills:
  - orchestrator-stage
  - superpowers-verification-before-completion
selected_agents:
  - none
catalog_candidates:
  - none
parallel_group: n/a
depends_on_streams:
  - tj-t6ug
parallel_decision: sequential
status: accepted
delivery_method: manual integration
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: root-owned main worktree; no child worktree or branch exists
risk_level: high
verification_tier: release
risk_tags:
  - authorization
affected_surfaces:
  - backend
invariants:
  - root-judge-reads-blind-and-is-free
  - authorized-call-count-not-exceeded
  - protected-corpus-stays-outside-git
  - no-claim-the-frozen-set-cannot-support
docs_impact: none
docs_reviewed: updated
docs_review_notes: one tracked report; handoff records the current number, the instrument floor and the three new defects
verification:
  - preflight: judge_model root-orchestrator, no second reader requested
  - run: 20 Luna calls, 1 repair-judge call, 0 scoring calls, $0.005386
  - blind reading: 20 replies and 300 criteria read by the root before any comparison
  - analyze: 20/20 coverage, 20/20 language, weighted 15.3 (12.6-17.9), raw 12.8 (12.0-13.5)
  - paired against tj-n7p4.5 and against the pre-stage baseline, both by pair_rounds.py
  - uv run ruff check src/ tests/ scripts/: passed
  - uv run ruff format --check src/ tests/ scripts/: passed
  - uv run mypy src/: passed over 174 source files
  - uv run pytest tests/ -v --tb=short: 3609 passed and 19 skipped
  - scripts/orchestration/run_process_verification.sh: passed
changed_files:
  - .codex/handoff.md
  - .codex/goals/tj-vhto/scope-criterion-snapshot.json
  - .codex/stages/tj-vhto-current-build-round/stage-manifest.json
  - .codex/stages/tj-vhto-current-build-round/summary.md
  - .codex/stages/tj-vhto-current-build-round/artifacts/tj-vhto.md
  - docs/reports/2026-08-11-where-the-bot-stands-on-the-shipped-build.md
  - scripts/corpus_bridge/pair_rounds.py
  - tests/test_corpus_bridge_pair_rounds.py
explicit_defers:
  - none
---

# Summary

The shipped build scores **15.3/30 weighted** and **12.8/30 raw**, on 20/20
coverage and language, with one critical that is the known SKU false positive.
Cut by what is reachable: 99% of the ceiling on greeting-only openings, 75% on
openings carrying a real request.

# Scope / Routing

Root-owned. The judge may not be delegated: it is the owner's standing
decision and the harness defaults to it. The reading was done before any
comparison was computed, so the deltas could not steer it.

# Verification

Every paired delta is attributed. Five openings carry all the movement, and
the two largest are a repair-judge provider failure and a stricter reading of
the same reply shape — neither is a change in the build. Because the only code
change since the previous round cannot affect a first turn, and the protected
replay proves the rendered text is identical, the −0.60 raw delta with an
interval excluding zero is a direct measurement of the instrument's floor.

# Delivery / Cleanup

One local commit on `main`. Protected transcripts stayed under the git common
dir; the tracked report carries dialog identifiers, integers and digests only.
No push, deploy, live mutation, model configuration change, or real-user
message occurred. Paid calls: 20 Luna generation calls and one failed
repair-judge call, $0.005386, under owner authority given in session.

# Risks / Follow-ups / Explicit Defers

No defer. Three defects were found and tracked rather than absorbed:
`tj-0s42`, the repair judge falls back to a manager after a single failed
call; `tj-4q79`, the root judge drifts between sittings and that drift is
larger than the deltas being reported; `tj-ge07`, no frozen set has a second
turn, so rules 14 and 15 remain unobservable.
