---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-rt7w-measured-round/stage-manifest.json
stream_owner: tj-rt7w.7-root-measurement
orchestration_level: slice_acceptance
scope_kind: product_slice
immediate_consumer: the owner's decision on the cleanup
public_facade: docs/reports/2026-08-11-the-round-after-the-cleanup.md
bounded_acceptance: 20/20 coverage, language and evaluations; critical-failure count
non_goals:
  - fixing anything the round finds
  - any absolute score level or cross-judge comparison
evidence:
  - none
task_id: tj-rt7w.7
epic_id: tj-rt7w
stage_id: tj-rt7w-measured-round
session_id: cut-back-the-over-complication
milestone: cohesive-vertical-slice
milestone_status: accepted
agent_type: n/a
subagent_model: inherit_orchestrator
reasoning_effort: high
model_reasoning_rationale: judging twenty replies against a fifteen-criterion rubric
repo: treejar
branch: main
base_branch: main
base_commit: 33c8f1f
worktree: /home/me/code/treejar
write_zone:
  - scripts/corpus_bridge/real_opening_acceptance.py
  - tests/test_corpus_bridge_real_opening_acceptance.py
  - docs/reports/2026-08-11-the-round-after-the-cleanup.md
  - AGENTS.md
success_criteria:
  - exactly 20 Luna calls and no unauthorized paid call
  - 20/20 responses, evaluations and language
  - critical-failure count reported, not averaged away
  - no opening text, company or amount inside the repository
selected_docs:
  - none
selected_skills:
  - orchestration-bridge:orchestrator-stage
selected_agents:
  - none
catalog_candidates:
  - none
parallel_group: n/a
depends_on_streams:
  - none
parallel_decision: local
status: accepted
delivery_method: merge
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: protected round evidence kept outside Git at modes 0700/0600
risk_level: high
verification_tier: integration
risk_tags:
  - privacy
affected_surfaces:
  - backend
invariants:
  - test-matrix
docs_impact: behavior
docs_reviewed: updated
docs_review_notes: round report added; AGENTS.md and the handoff carry the judge rule
verification:
  - uv run ruff check src/ tests/ scripts/: passed
  - uv run ruff format --check src/ tests/ scripts/: passed
  - uv run mypy src/: passed
  - uv run pytest tests/test_corpus_bridge_real_opening_acceptance.py tests/test_corpus_stays_outside_the_repository.py tests/test_quality_evaluator.py -q: passed
  - real_opening_acceptance preflight/run/ingest-judgment: passed, 20 Luna calls, 0 judging calls
changed_files:
  - scripts/corpus_bridge/real_opening_acceptance.py
  - tests/test_corpus_bridge_real_opening_acceptance.py
  - docs/reports/2026-08-11-the-round-after-the-cleanup.md
  - AGENTS.md
  - .codex/handoff.md
  - .codex/stages/tj-rt7w-measured-round
explicit_defers:
  - tj-riim: the unverified recruitment commitment this round found; a fix owes a measured round under R5
  - tj-vz7o.12: three findings reproduced unchanged, out of this stage's scope
  - tj-rt7w.14: the R2 bound has no semantic half
---

# Summary

One measured round at `33c8f1f` on the frozen seed-`20260810` twenty. The owner
authorised 20 Luna + 20 GLM and then chose to drop the paid second reader, so
the round is 20 Luna calls and zero judging calls, $0.004661, judged by the
orchestrator reading blind.

Coverage, evaluations and language are 20/20. **One critical failure in 1/20**,
so the round does not pass its own fourth criterion. It is `tj-riim`, and it is
not attributable to this epic.

What the round was for is answered: the cleanup changed nothing it did not mean
to, `tj-rt7w.1` holds in the live path, and the three known out-of-scope defects
reproduce unchanged.

# Scope / Routing

Root-owned on `main`; `delegation.inline_subagents_allowed = false`. The owner's
standing judge rule was made executable rather than documented: the harness
defaults to the root judge and `--second-reader` is the thing you have to ask
for.

# Verification

Gates pass. The protected round evidence lives outside Git at modes 0700/0600.
No opening text, client company or amount entered the repository; the report
carries `dialog_id`s, integers, and Noor's own sentences only.

No paired score delta is reported, because the judge changed and the project
forbids comparing across judges.

# Delivery / Cleanup

Accepted in the root worktree, one local commit. No push, PR, deploy,
production or staging mutation, model-configuration change, or real-user
message. Paid calls: 20, within the owner's authorisation given in this session.

# Risks / Follow-ups / Explicit Defers

`tj-riim` is open and P1. `tj-vz7o.12` is annotated with what this round showed
about each of its four findings. The next measured round is the first one
comparable with this one, because the judge is now fixed by default.
