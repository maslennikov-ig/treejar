---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-ee5f/stage-manifest.json
stream_owner: tj_ee5f_r07
orchestration_level: slice_acceptance
scope_kind: product_slice
immediate_consumer: tj-ee5f orchestrator
public_facade: n/a
bounded_acceptance: R-03, R-04, R-08, R-16 and current-turn search allowance
non_goals:
  - dialogue, evaluator, model-battle, model configuration, deploy, and production access
evidence:
  - none
task_id: tj-ee5f.7
epic_id: tj-ee5f
stage_id: tj-ee5f
session_id: n/a
milestone: cohesive-vertical-slice
milestone_status: in_progress
agent_type: worker
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: inherited for a bounded critical review-remediation stream
repo: treejar
branch: codex/tj-ee5f-r07-review-remediation
base_branch: codex/tj-ee5f-quality-model-battle
base_commit: d58e321
worktree: /home/me/code/treejar/.worktrees/tj-ee5f-r07-review-remediation
write_zone:
  - src/llm/engine.py
  - src/llm/prompts.py
  - directly relevant tests under tests/
  - .codex/stages/tj-ee5f/artifacts/tj-ee5f.7-review-remediation.md
success_criteria:
  - model-owned catalog answer survives verified-fact repair with separate text provenance
  - one SKU exposes one authoritative stock number per turn
  - product-search prompt does not contradict the runtime family-derived allowance
  - partial catalog selection retains solved families and records an exact typed coverage gap
selected_docs:
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
cleanup_notes: orchestrator owns post-acceptance cleanup
risk_level: high
verification_tier: delta
risk_tags:
  - data
  - state-transition
affected_surfaces:
  - backend
  - user-flow
invariants:
  - state-transition
  - test-matrix
docs_impact: behavior
docs_reviewed: updated
docs_review_notes: this artifact records only behavior proved by the focused tests
verification:
  - "RED prompt: numeric search rules remained in the built prompt (1 failed)"
  - "RED current-turn allowance: accumulated three-family state returned 6 instead of 2 (1 failed)"
  - "RED partial solver: one under-covered family returned None (1 failed)"
  - "RED stock search: catalog stock 30 was exposed instead of Zoho 7 or unconfirmed (2 failed)"
  - "RED materializer: deterministic replacement made only one model call (1 failed)"
  - "RED decision: incomplete coverage was rejected despite an exact typed gap (1 failed after interface scaffold)"
  - "RED per-turn stock: get_stock replaced the existing 7-item snapshot with 25 (1 failed)"
  - "uv run pytest tests/test_llm_engine.py tests/test_llm_catalog_decision.py tests/test_llm_prompts.py -q --tb=short: 759 passed"
  - "uv run pytest tests/test_llm_engine.py -k 'catalog or product_search_limit' -q --tb=short: 166 passed, 577 deselected"
  - "uv run mypy src/llm/engine.py src/llm/prompts.py: passed"
  - "uv run ruff check changed files: passed"
  - "uv run ruff format --check changed files: passed"
  - "uv run python scripts/orchestration/validate_artifact.py .codex/stages/tj-ee5f/artifacts/tj-ee5f.7-review-remediation.md: blocked until the orchestrator lists this new artifact in the stage manifest"
changed_files:
  - src/llm/engine.py
  - src/llm/prompts.py
  - tests/test_llm_catalog_decision.py
  - tests/test_llm_engine.py
  - tests/test_llm_prompts.py
  - .codex/stages/tj-ee5f/artifacts/tj-ee5f.7-review-remediation.md
explicit_defers:
  - none
---

# Summary

Catalog remediation now preserves model ownership through a constrained repair pass,
tracks response-text provenance independently from provider usage, sources live stock
from one per-turn snapshot, and keeps a typed partial plan with its numeric gap. The
static product prompt shrank and no longer hardcodes a conflicting search-call count.

# Scope / Routing

Only the assigned engine, prompt, tests, and stream artifact were changed. No frozen
acceptance fixture or digest changed, and no scenario transcript entered product code.

# Verification

Every behavioral change was introduced by a focused failing test before its minimal
implementation. The combined engine/prompt/decision surface passes 759 tests.

# Delivery / Cleanup

Ready for orchestrator review and cherry-pick. No push, deploy, paid call, model-config
change, production readback, or production side effect occurred.

# Risks / Follow-ups / Explicit Defers

`text_provenance` is now explicit on `LLMResponse`; persisting that new dimension into
the versioned runtime-evidence schema is outside this stream's write zone. No in-scope
behavioral defer remains. The orchestrator must list this artifact in the stage
manifest before the artifact validator can pass.
