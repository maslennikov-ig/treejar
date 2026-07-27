---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-0j7o/stage-manifest.json
stream_owner: model-battle-stage-owner
orchestration_level: release
scope_kind: product_slice
immediate_consumer: Noor model-routing decision
public_facade: n/a
bounded_acceptance: two-route synthetic model battle and decision report
non_goals:
  - production model switch, customer traffic, Zoho/Wazzup mutations, cost optimization
evidence:
  - route-decisions
  - decision-report
task_id: tj-0j7o
epic_id: n/a
stage_id: tj-0j7o
session_id: n/a
milestone: cohesive-vertical-slice
milestone_status: accepted
agent_type: worker
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: Root owned one scoring contract and sequential provider timing; specialist agents supplied provider and blinded QA review.
repo: treejar
branch: main
base_branch: main
base_commit: c95a4e0
worktree: /home/me/code/treejar
write_zone:
  - benchmark harness, synthetic cases, tests, tracked evidence, report, Beads, and stage documentation
success_criteria:
  - Reproducibly compare both accepted model pairs, preserve blinded evidence, apply hard gates, and record route recommendations without production mutation.
selected_docs:
  - docs/superpowers/specs/2026-07-27-noor-model-battle-design.md
  - docs/superpowers/plans/2026-07-27-noor-model-battle.md
selected_skills:
  - orchestrator-stage
  - prompt-authoring
  - test-driven-development
  - test-pass
  - verification-before-completion
  - orchestration-closeout
selected_agents:
  - docs_researcher for provider and methodology review
  - qa_expert for context-isolated blinded sales review
catalog_candidates:
  - none; installed workflows covered the task
parallel_group: noor-two-route-model-battle
depends_on_streams:
  - none
parallel_decision: sequential inference with isolated read-only review
status: accepted
delivery_method: manual integration
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: No stage worktree or branch was created; reviewers left no workspace or runtime tail.
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
docs_review_notes: Added durable methodology, results, recommendations, limitations, follow-up Beads, and handoff truth.
verification:
  - uv run pytest tests/test_scripts_model_battle.py -q: passed with 37 tests
  - uv run ruff check src/ tests/: passed
  - uv run ruff format --check src/ tests/: passed over 302 files
  - uv run mypy src/: passed over 162 source files
  - uv run pytest tests/ -v --tb=short: passed with 1569 passed and 19 skipped
  - benchmark scripts Ruff and format checks: passed
  - canonical stage closeout: passed, including 133 integration checks
changed_files:
  - scripts/model_battle.py
  - scripts/model_battle_cases.py
  - tests/test_scripts_model_battle.py
  - docs/reports/model-battle-2026-07-27.md
  - .codex/stages/tj-0j7o/results/
explicit_defers:
  - tj-j13d owns guarded DeepSeek fast-route hardening and production adoption remains separately gated.
  - tj-b93r owns the GLM-5 weak-catalog grounding guard.
---

# Summary

## Delivered

- Reproducible OpenRouter benchmark harness and 36 focused regression tests.
- Twelve sales cases and twenty-four structured/helper cases, each run twice.
- Provider capability preflight with parameter-support enforcement.
- Separate first-pass reliability, retry, schema, semantic, tool, latency, and
  hard-gate accounting.
- Blinded sales review completed before model identity was revealed.
- Raw and derived evidence under `.codex/stages/tj-0j7o/results/`.
- Durable decision report at `docs/reports/model-battle-2026-07-27.md`.

## Accepted findings

- Core sales comparative choice: keep `z-ai/glm-5`.
- Fast/system comparative choice: prefer `deepseek/deepseek-v4-flash` with
  reasoning disabled and structured validation/fallback.
- Strict release-gate outcome: no safe replacement in either battle. Sales had
  one blind critical finding per candidate; both fast candidates missed the
  semantic threshold, and Nex also missed the JSON/schema threshold.
- Production routing was not changed.
- Follow-up Beads: `tj-j13d` (guarded DeepSeek fast-route hardening) and
  `tj-b93r` (GLM-5 weak-catalog grounding).

## Evidence highlights

- Sales GLM-5: weighted `92.879`, blind quality `91.33%`, p95 `11.229s`.
- Sales DeepSeek: weighted `85.395`, blind quality `91.00%`, p95 `21.962s`.
- System DeepSeek: JSON/schema `97.5%`, semantic `71.84%`, p95 `14.804s`.
- System Nex: JSON/schema `72.5%`, semantic `64.08%`, p95 `5.553s`.
- Provider first-pass reliability and tool-argument correctness were `100%` for
  all candidates in the accepted runs.

## Review disposition

The targeted provider/methodology review found no P0. Its P1 findings were
fixed before the accepted run: provider parameter enforcement, transient-only
retry, correct first-pass accounting, negative-claim handling, array-length
scoring, equal case weighting, and a complete hard-gate/winner path. The
blind-review stream wrote only the anonymous score file and did not read the
model key.

# Verification

- Focused TDD suite: `37 passed`.
- Full repository gates passed: Ruff, Ruff format, Mypy over 162 source files,
  and Pytest with 1569 passed and 19 skipped.

# Risks / Follow-ups

- `docs-reviewed: updated` — design, plan, report, stage summary, and handoff
  record the final evidence and boundary.
- `project-index: reviewed-no-change` — no stable application entrypoint or
  product API changed.
- `graph-reviewed: no-change-needed` — Graphify is not configured and no graph
  report exists.
- `tj-j13d` must close semantic fast-route failures before any unguarded model
  adoption.
- `tj-b93r` must close the weak-catalog grounding failure before the sales
  route can pass the strict battle gate.
