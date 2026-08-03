---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-ee5f/stage-manifest.json
stream_owner: engine_remediation
orchestration_level: integration
scope_kind: product_slice
immediate_consumer: tj-ee5f.13 model battle
public_facade: Noor catalog recommendation and quotation flow
bounded_acceptance: focused local dialogue-state, quote-consent, catalog-decision, and engine regressions
non_goals:
  - evaluator, model battle, deployment, paid calls, Beads updates, or live side effects
evidence:
  - none
task_id: tj-ee5f.7-.8
epic_id: tj-ee5f
stage_id: tj-ee5f
session_id: tj-ee5f-engine-remediation
milestone: catalog and quote-state remediation
milestone_status: accepted
agent_type: worker
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: typed state transitions and catalog materialization require focused integration verification
repo: treejar
branch: codex/tj-ee5f-engine
base_branch: origin/main
base_commit: f831e6c4edf8f50ec168db745f79ea3a1683f553
worktree: /home/me/code/treejar/.worktrees/tj-ee5f-engine
write_zone:
  - src/dialogue/order_state.py
  - src/dialogue/reducer.py
  - src/dialogue/runner.py
  - src/dialogue/state.py
  - src/llm/engine.py
  - tests/test_dialogue_order_state.py
  - tests/test_dialogue_runner.py
  - tests/test_dialogue_state.py
  - tests/test_llm_engine.py
  - tests/test_llm_catalog_decision.py
success_criteria:
  - quote consent and lifecycle are versioned, backward-readable, and reconciled from confirmed facts
  - decline and defer interrupt detail collection, while details require explicit quote consent
  - impossible customer slot combinations are removed before routing
  - catalog decisions use one authoritative Zoho stock snapshot per SKU and validate coverage and budget
  - product search budget derives from requested product-family count
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
parallel_group: engine-state-catalog
depends_on_streams:
  - none
parallel_decision: parallel
status: returned
delivery_method: cherry-pick
accepted_by_orchestrator: no
cleanup_status: pending
cleanup_notes: parent orchestrator owns integration and worktree cleanup
risk_level: high
verification_tier: delta
risk_tags:
  - state-transition
  - idempotency
  - data
  - user-flow
affected_surfaces:
  - backend
  - user-flow
invariants:
  - state-transition
  - idempotency
  - test-matrix
docs_impact: behavior
docs_reviewed: updated
docs_review_notes: this artifact records the behavior delta; release documentation remains with tj-ee5f.1
verification:
  - focused import RED for quote workflow and catalog decision types: failed as expected
  - focused slot-conflict RED: failed as expected
  - focused dialogue and catalog pytest set: passed 47
  - focused affected engine pytest set: passed 75
  - targeted Ruff check and format check: passed
  - targeted Mypy: passed
  - git diff check: passed
changed_files:
  - src/dialogue/order_state.py
  - src/dialogue/reducer.py
  - src/dialogue/runner.py
  - src/dialogue/state.py
  - src/llm/engine.py
  - tests/test_dialogue_order_state.py
  - tests/test_dialogue_runner.py
  - tests/test_dialogue_state.py
  - tests/test_llm_engine.py
  - tests/test_llm_catalog_decision.py
  - .codex/stages/tj-ee5f/artifacts/tj-ee5f.7-8-quality-remediation.md
explicit_defers:
  - tj-ee5f.13 owns isolated model comparison and its evidence
  - tj-ee5f.1 owns full release gates, deployment, and production acceptance
---

# Summary

Added a backward-readable typed quote workflow and reconciled it from confirmed
customer facts. Quote details and quotation side effects now require explicit
consent; decline, defer, correction, and delivery intents interrupt collection.
Impossible slot combinations such as budget-as-address and company-as-individual
are removed before routing.

Catalog recommendations now materialize a typed decision with authoritative
Zoho stock snapshots. The validator rejects inconsistent stock, incomplete
coverage, excess family SKU count, and over-budget configurations before a
customer response is rendered. Search allowance is derived from product-family
count, and complete configurations prefer fewer SKUs before price.

# Scope / Routing

This stream owns only the local dialogue, quotation-state, and catalog-decision
slice. It does not change external REST/webhook contracts, database schema, or
the product system prompt. Exact scenario transcripts remain in tests only.

# Verification

Focused TDD demonstrated the missing types and slot-conflict behavior before
implementation. The final bounded acceptance passed 47 dialogue/catalog tests
and 75 affected engine tests, plus targeted Ruff, format, Mypy, and diff checks.

# Delivery / Cleanup

Return by cherry-pick from `codex/tj-ee5f-engine`. The parent orchestrator owns
acceptance, integration, and safe worktree cleanup.

# Risks / Follow-ups / Explicit Defers

The full release suite and model-battle/production evidence were intentionally
not run in this bounded stream. Legacy quote metadata is still read for
compatibility, while only the versioned workflow is written by new paths.
