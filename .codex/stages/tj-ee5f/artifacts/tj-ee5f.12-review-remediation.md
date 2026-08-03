---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-ee5f/stage-manifest.json
stream_owner: tj-ee5f-r12-review-remediation
orchestration_level: slice_acceptance
scope_kind: product_slice
immediate_consumer: tj-ee5f.13 model battle and tj-ee5f.1 acceptance
public_facade: deterministic quality score and owner-facing final quality review
bounded_acceptance: focused evaluator, persistence-job, and Telegram report regressions
non_goals:
  - Beads mutation, model battle, model configuration, paid calls, push, deploy, or production access
evidence:
  - none
task_id: tj-ee5f.12-review-remediation
epic_id: tj-ee5f
stage_id: tj-ee5f
session_id: tj-ee5f-r12-review-remediation
milestone: R-06 and R-07 quality-score publication remediation
milestone_status: accepted
agent_type: worker
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: deterministic score arithmetic and owner-facing aggregate semantics required focused boundary reasoning
repo: treejar
branch: codex/tj-ee5f-r12-review-remediation
base_branch: codex/tj-ee5f-quality-model-battle
base_commit: d58e321ab57105ded04a47deea9a9a3340dbb07b
worktree: /home/me/code/treejar/.worktrees/tj-ee5f-r12-review-remediation
write_zone:
  - src/quality/
  - src/services/notifications.py
  - tests/test_quality_evaluator.py
  - tests/test_telegram_notifications.py
  - .codex/stages/tj-ee5f/artifacts/tj-ee5f.12-review-remediation.md
success_criteria:
  - collapsed rule or block coverage cannot inflate a result to an excellent score
  - low coverage is blocking, remains represented in aggregate scoring, and is visible in the owner report
  - block breakdown uses normalized denominators and renders wholly inapplicable blocks as not applicable
selected_docs:
  - AGENTS.md
  - .codex/orchestrator.toml
  - .codex/handoff.md
  - docs/superpowers/specs/2026-08-03-noor-e2e-remediation-and-model-comparison-spec.md
selected_skills:
  - superpowers:test-driven-development
selected_agents:
  - none
catalog_candidates:
  - none
parallel_group: tj-ee5f-review-remediation
depends_on_streams:
  - none
parallel_decision: parallel
status: returned
delivery_method: cherry-pick
accepted_by_orchestrator: no
cleanup_status: pending
cleanup_notes: parent orchestrator owns integration and worktree cleanup
risk_level: medium
verification_tier: delta
risk_tags:
  - data
  - user-flow
affected_surfaces:
  - backend
  - user-flow
invariants:
  - test-matrix
docs_impact: behavior
docs_reviewed: updated
docs_review_notes: this artifact records the bounded behavior change; stage summary and handoff remain parent-owned
verification:
  - focused RED for one covered block: failed with 30.0 instead of 6.0
  - focused RED for one rule in every block: failed with 30.0 instead of 8.3
  - focused RED for diagnostics: low coverage remained partial and had no blocking reason
  - focused RED for owner report: rendered 7.5/6, 0.0/6, and a normal 6.0/30 score
  - uv run pytest tests/test_quality_evaluator.py tests/test_quality_job.py tests/test_telegram_notifications.py -q --tb=short: passed 99
  - git diff --check: passed
changed_files:
  - src/quality/schemas.py
  - src/services/notifications.py
  - tests/test_quality_evaluator.py
  - tests/test_telegram_notifications.py
  - .codex/stages/tj-ee5f/artifacts/tj-ee5f.12-review-remediation.md
explicit_defers:
  - tj-ee5f.13 owns isolated model comparison and its evidence
  - tj-ee5f.1 owns integration/release gates, delivery, deploy, and production acceptance
---

# Summary

Low evaluator coverage now uses nominal block weights and the full rule count
inside each covered block. A four-rule profile spanning all four blocks therefore
aggregates as `8.3`, not `30.0`; a fully covered opening block aggregates as
`6.0`, not a renormalized `30.0`. The scenario stays present through
`excluded_from_aggregate=false`, while diagnostics automatically mark
`unexpected_low_coverage` as blocking.

The owner-facing final review publishes rule/block coverage beside the score.
For low coverage it suppresses the normal `/30` presentation and states that
the evaluator coverage failed. Applicable blocks render points against their
normalized weights; wholly inapplicable blocks render `н/д`.

# Scope / Routing

The change is confined to deterministic quality scoring, final-review
presentation, and their focused tests. Persistence retains the conservative
`total_score`, so existing aggregate queries keep the scenario without a schema
change. No product prompt, dialogue engine, model-battle code, external system,
or runtime configuration was touched.

# Verification

TDD reproduced both reviewed defects before implementation. The final focused
set passed all 99 evaluator, quality-job, and Telegram notification tests.

# Delivery / Cleanup

Return this branch commit for parent-orchestrator cherry-pick. The parent owns
acceptance, integration, and safe worktree cleanup.

# Risks / Follow-ups / Explicit Defers

No in-scope technical debt remains. Broad release verification and all external
actions remain outside this delegated stream.
