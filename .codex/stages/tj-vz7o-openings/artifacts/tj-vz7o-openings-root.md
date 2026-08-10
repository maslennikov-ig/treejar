---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-vz7o-openings/stage-manifest.json
stream_owner: measurement-integrator
orchestration_level: slice_acceptance
scope_kind: product_slice
immediate_consumer: tj-vz7o-judge-bridge
public_facade: score_raw_convention-and-corpus-bridge-scripts
bounded_acceptance: map-free-reread-response-metrics-and-frozen-real-openings
non_goals:
  - paid judge calls, corpus-panel arm, live traffic, deploy, push, production mutation, real-user messaging, outcome claims, rubric changes, or applicability changes
evidence:
  - real-opening-public-manifest
  - map-free-reread-report
task_id: tj-vz7o-openings-root
epic_id: tj-vz7o
stage_id: tj-vz7o-openings
session_id: tj-vz7o
milestone: client-ruler-openings-bridge
milestone_status: accepted
agent_type: worker
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: Root retained measurement integration while nine fresh blind readers supplied independent scoring context.
repo: treejar
branch: codex/tj-vz7o-corpus-bridge
base_branch: main
base_commit: 426e77cbeb6f8aa8a6fd4abe0ca14cd09e025100
worktree: /home/me/code/treejar
write_zone:
  - scripts/e2e_acceptance/score_raw_convention.py
  - scripts/e2e_acceptance/prepare_map_free_panel.py
  - scripts/corpus_bridge/
  - tests/test_e2e_acceptance_score_raw_convention.py
  - tests/test_prepare_map_free_panel.py
  - tests/test_corpus_bridge_response_metrics.py
  - tests/test_corpus_bridge_freeze_opening_scenarios.py
  - .codex/goals/tj-vz7o/
  - .codex/stages/tj-vz7o-openings/
  - .codex/handoff.md
  - docs/reports/2026-08-10-the-map-free-reread-and-real-openings.md
success_criteria:
  - 53 stored packets over 19 scenarios have 106 map-free reads with exactly 15 criteria and no applicability fields
  - response coverage and first-reply time exist for 1400 human dialogues and 53 bot packets with clustered intervals
  - seed 20260810 freezes 20 natural openings and a no-call stored-human baseline without corpus text entering Git
  - owner and client decision texts are drafted but unsent while the exact 53-call authority gate remains open
selected_docs:
  - AGENTS.md
  - .codex/orchestrator.toml
  - .codex/handoff.md
  - docs/superpowers/specs/2026-08-10-the-clients-ruler-and-the-corpus-bridge-spec.md
  - protected corpus explanatory note
selected_skills:
  - orchestrator-stage
  - superpowers:subagent-driven-development
  - superpowers:test-driven-development
selected_agents:
  - nine fresh default blind-reader agents
catalog_candidates:
  - none
parallel_group: map-free-blind-readers
depends_on_streams:
  - none
parallel_decision: parallel
status: accepted
delivery_method: manual integration
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: Reader sessions completed; they created no child worktree or branch, and only protected evidence retained by the contract remains outside Git.
risk_level: high
verification_tier: integration
risk_tags:
  - data
affected_surfaces:
  - data
invariants:
  - test-matrix
docs_impact: behavior
docs_reviewed: updated
docs_review_notes: Report, current-state handoff, stage summary, public integer-only manifest, and unsent drafts were added or refreshed; no external versioned docs or Graphify boundary applies.
verification:
  - focused TDD RED for map-free score parsing and schema rejection: passed
  - focused TDD GREEN tests/test_e2e_acceptance_score_raw_convention.py: passed with 16 tests
  - focused TDD RED and GREEN for protected panel preparation: passed with 1 test
  - focused TDD RED and GREEN for response metrics: passed with 1 test
  - focused TDD RED and GREEN for opening-set freeze: passed with 1 test
  - focused corpus guard and bridge set: passed with 24 tests
  - protected map-free contract validation: passed with 53 packets, 106 reads, 9 readers, 1590 criteria, and no applicability fields
  - protected corpus continuity reconciliation: passed with exact 478 and 922 dialogue counts over 1400 dialogues
  - uv run ruff check src/ tests/ scripts/: passed
  - uv run ruff format --check src/ tests/ scripts/: passed with 427 files formatted
  - uv run mypy src/: passed with 168 source files
  - bash scripts/orchestration/run_process_verification.sh: passed
changed_files:
  - .codex/orchestrator.toml
  - .codex/handoff.md
  - .codex/goals/tj-vz7o/scope-criterion-snapshot.json
  - .codex/stages/tj-vz7o-openings/
  - .codex/stages/tj-ee5f/traceability-manifest.json
  - docs/reports/2026-08-10-the-map-free-reread-and-real-openings.md
  - scripts/e2e_acceptance/score_raw_convention.py
  - scripts/e2e_acceptance/prepare_map_free_panel.py
  - scripts/corpus_bridge/response_metrics.py
  - scripts/corpus_bridge/freeze_opening_scenarios.py
  - tests/test_e2e_acceptance_score_raw_convention.py
  - tests/test_prepare_map_free_panel.py
  - tests/test_corpus_bridge_response_metrics.py
  - tests/test_corpus_bridge_freeze_opening_scenarios.py
explicit_defers:
  - tj-vz7o.4 requires authority for exactly 53 paid claude-haiku-4.5 calls and the client evaluator prompt; tj-vz7o.5 remains dependent
  - tj-vz7o.8 and tj-vz7o.9 are drafted but unsent and remain decision tasks
---

# Summary

Removed the applicability-map confound with a nine-reader map-free panel,
measured response coverage and first-reply time on both sides, and froze a
seeded real-opening set plus its already-stored human baseline. The private
corpus and all transcript-bearing derived files remain under git-common-dir.

# Scope / Routing

Root owned integration, Beads, protected corpus access, tracked files, manual
transcript review, and final acceptance. Nine fresh-context agents each read
only their own sanitized 11-12 packet input and the raw rubric. Their protected
write zones did not overlap. No paid, live, remote, or production action ran.

# Verification

Focused red-green evidence is recorded above. The root-owned repository gates
and stage closeout run once at the cohesive acceptance boundary.

# Delivery / Cleanup

Local branch only. No push, deploy, merge, live action, or child worktree
cleanup applies.

# Risks / Follow-ups / Explicit Defers

The judge confound remains until the exact paid-call grant and evaluator prompt
boundary are resolved. The no-call opening baseline is the client's stored
human raw score, not a Noor build baseline. Response coverage means a later
substantive reply, not resolution, quality, causality, or an outcome.
