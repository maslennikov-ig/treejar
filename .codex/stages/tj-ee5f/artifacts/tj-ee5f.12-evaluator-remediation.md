---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-ee5f/stage-manifest.json
stream_owner: evaluator-remediation
orchestration_level: integration
scope_kind: product_slice
immediate_consumer: tj-ee5f.13
public_facade: internal quality EvaluationResult
bounded_acceptance: focused quality evaluator regressions
non_goals:
  - model-battle judging or EVAL_DISAGREEMENT
  - product dialogue, catalog, prompt, deployment, or live changes
  - Beads, stage manifest, or handoff changes
evidence:
  - focused RED and GREEN commands below
task_id: tj-ee5f.12
epic_id: tj-ee5f
stage_id: tj-ee5f
session_id: evaluator-remediation
milestone: quality-remediation
milestone_status: in_progress
agent_type: python_pro
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: inherited for an isolated typed-evaluator stream
repo: treejar
branch: codex/tj-ee5f-evaluator
base_branch: main
base_commit: f831e6c4edf8f50ec168db745f79ea3a1683f553
worktree: /home/me/code/treejar/.worktrees/tj-ee5f-evaluator
write_zone:
  - src/quality/evaluator.py
  - src/quality/schemas.py
  - tests/test_quality_evaluator.py
  - .codex/stages/tj-ee5f/artifacts/tj-ee5f.12-evaluator-remediation.md
success_criteria:
  - rule applicability uses typed dialogue and runtime facts without language keywords
  - absent blocks are excluded and remaining score weights normalize exactly to /30
  - unexpected low coverage is a blocking diagnostic but remains in aggregates
  - existing REST and database schemas are unchanged
selected_docs:
  - docs/superpowers/specs/2026-08-03-noor-e2e-remediation-and-model-comparison-spec.md
selected_skills:
  - orchestrator-stage
  - test-driven-development
selected_agents:
  - python_pro
catalog_candidates:
  - none
parallel_group: quality-model-remediation
depends_on_streams:
  - none
parallel_decision: parallel
status: returned
delivery_method: cherry-pick
accepted_by_orchestrator: no
cleanup_status: pending
cleanup_notes: parent must review and integrate the commit before cleanup
risk_level: medium
verification_tier: inner_loop
risk_tags:
  - scoring
  - state
  - backwards-compatibility
affected_surfaces:
  - backend
  - quality-evaluation
invariants:
  - score-range
  - aggregate-membership
  - test-matrix
docs_impact: internal
docs_reviewed: updated
docs_review_notes: this artifact records the changed scoring and applicability contract
verification:
  - "RED: 8 selected regressions failed before implementation"
  - "GREEN: uv run --extra dev pytest tests/test_quality_evaluator.py -q: 32 passed"
  - "git diff --check: passed"
changed_files:
  - src/quality/evaluator.py
  - src/quality/schemas.py
  - tests/test_quality_evaluator.py
  - .codex/stages/tj-ee5f/artifacts/tj-ee5f.12-evaluator-remediation.md
explicit_defers:
  - blind-audit EVAL_DISAGREEMENT belongs to tj-ee5f.13
  - integration and full release gates belong to the parent stage
---

# Summary

The evaluator now decides each rule from typed dialogue state, active flow,
filled slots, validated runtime tool traces, quote consent/lifecycle, refusal,
next-step signals, and message roles. It no longer infers EN/AR/RU behavior from
English keyword lists.

# Score and Coverage Contract

If a complete scoring block is not applicable, its nominal weight is removed
from the denominator and the remaining active blocks are normalized exactly to
30 points. Coverage diagnostics record applicable rules and blocks, the typed
signals used, and any blocking state/evidence mismatch. Low-coverage scenarios
remain in aggregate scoring; no exclusion flag can be enabled.

# Compatibility

Conversation metadata is read through the existing `DialogueState` adapter,
including its legacy fallback, while new quote state fields are discovered from
versioned nested mappings. Runtime tool evidence is accepted only after typed
schema validation. The public REST and database schemas were not changed.

# Verification

Focused RED reproduced stale block weights, language-keyword applicability,
quote-decline misclassification, missing runtime evidence, and silent advanced
stage gaps. The owned evaluator test file then passed all 32 tests. No model,
provider, production, database, or other external call was made.

# Integration Seam

The dialogue stream may add fields to `DialogueSlots` or move versioned quote
state within conversation metadata without changing this adapter. The model
battle stream should treat `diagnostics.status == "blocking"` as evaluator
failure and should add its separate blind-audit `EVAL_DISAGREEMENT` result.
