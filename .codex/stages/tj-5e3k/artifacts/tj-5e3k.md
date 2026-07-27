---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-5e3k/stage-manifest.json
stream_owner: model-battle-stage-owner
orchestration_level: release
scope_kind: product_slice
immediate_consumer: Noor model-routing decision
public_facade: n/a
bounded_acceptance: four-candidate synthetic model battle for both Noor routes
non_goals:
  - production model switch, customer traffic, Zoho/Wazzup mutations
evidence:
  - route-decisions
  - decision-report
task_id: tj-5e3k
epic_id: n/a
stage_id: tj-5e3k
session_id: n/a
milestone: cohesive-vertical-slice
milestone_status: accepted
agent_type: worker
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: Root owns the shared benchmark; anonymous sales scoring uses context isolation.
repo: treejar
branch: main
base_branch: main
base_commit: 8f73c4e
worktree: /home/me/code/treejar
write_zone:
  - benchmark profile, tests, tracked evidence, report, Beads, and stage documentation
success_criteria:
  - Compare all accepted candidates reproducibly and record strict and practical route decisions without production mutation.
selected_docs:
  - docs/superpowers/specs/2026-07-27-noor-glm52-v4pro-model-battle-design.md
  - docs/superpowers/plans/2026-07-27-noor-glm52-v4pro-model-battle.md
selected_skills:
  - orchestrator-stage
  - brainstorming
  - writing-plans
  - test-driven-development
  - prompt-authoring
  - verification-before-completion
selected_agents:
  - qa_expert for context-isolated anonymous sales review
catalog_candidates:
  - none; installed workflows cover the stage
parallel_group: noor-extended-model-battle
depends_on_streams:
  - none
parallel_decision: sequential inference followed by isolated read-only scoring
status: accepted
delivery_method: manual integration
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: No stage worktree or branch was created; reviewers left no runtime tail, and unrelated untracked user files remain untouched.
risk_level: high
verification_tier: release
risk_tags:
  - api
affected_surfaces:
  - backend
invariants:
  - test-matrix
  - structured-output
  - production-unchanged
docs_impact: behavior
docs_reviewed: updated
docs_review_notes: Durable report, design, plan, stage summary, and handoff record the final evidence and qualified route decisions.
verification:
  - uv run pytest tests/test_scripts_model_battle.py -q -p no:cacheprovider: passed with 56 tests
  - uv run ruff check src/ tests/: passed
  - uv run ruff format --check src/ tests/: passed over 302 files
  - uv run mypy src/: passed over 162 source files
  - uv run pytest tests/ -v --tb=short: passed with 1588 passed and 19 skipped
  - score-only regeneration from preserved raw evidence: passed
  - benchmark evidence integrity: passed for 96 sales and 192 system rows
  - canonical release closeout: passed, including 133 integration checks
changed_files:
  - scripts/model_battle.py
  - tests/test_scripts_model_battle.py
  - .codex/stages/tj-5e3k/results/
  - .codex/stages/tj-5e3k/review.md
  - .codex/stages/tj-5e3k/review-delta.md
  - docs/reports/model-battle-glm52-v4pro-2026-07-27.md
explicit_defers:
  - Production adoption and deployment remain separately gated.
---

# Summary

## Delivered

- Four-candidate, two-repeat comparison for both Noor model routes.
- Ninety-six sales and 192 structured/system calls, all synthetic and
  sequential.
- Counterbalanced anonymous A/B/C/D sales review completed before reveal.
- Provider capability, raw response, latency, retry, reasoning-control,
  JSON/schema, semantic, tool-argument, and hard-gate evidence.
- Review fixes for negated claims, suite/matrix provenance, punctuation,
  reasoning diagnostics, and balanced blinding, including final P3 hardening.
- Durable decision report and reproducible raw/derived artifacts.

# Verification

- Focused benchmark suite: `56 passed`.
- Full release gates: Ruff and Ruff format passed; Mypy passed over 162 source
  files; Pytest passed with `1588 passed, 19 skipped`.
- Targeted correctness delta-review disposition: `merge`.

# Risks / Follow-ups

- Sales strict winner is `z-ai/glm-5` at `93.975`.
- Fast/system strict outcome is `no_safe_replacement`; DeepSeek V4 Pro is only
  the practical hardening target at `85.353`.
- `docs-reviewed: updated` — final evidence, limitations, and follow-up
  boundary are recorded.
- `project-index: reviewed-no-change` — no stable application entrypoint,
  route, API, integration, or ownership boundary changed.
- `graph-reviewed: no-change-needed` — Graphify is not configured and no graph
  report exists.
- Production adoption and deployment remain separately gated under `tj-j13d`.
