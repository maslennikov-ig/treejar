---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-ee5f/stage-manifest.json
stream_owner: model_battle_remediation
orchestration_level: integration
scope_kind: product_slice
immediate_consumer: tj-ee5f integration owner
public_facade: scripts/model_battle.py
bounded_acceptance: isolated synthetic model selection without runtime mutation
non_goals:
  - paid model execution, production configuration changes, deploy, or live side effects
evidence:
  - none
task_id: tj-ee5f.13
epic_id: tj-ee5f
stage_id: tj-ee5f
session_id: tj-ee5f.13-model-battle-remediation
milestone: cohesive-vertical-slice
milestone_status: accepted
agent_type: worker
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: cross-module harness behavior with cost and evidence gates
repo: treejar
branch: codex/tj-ee5f-model-battle
base_branch: origin/main
base_commit: f831e6c4edf8f50ec168db745f79ea3a1683f553
worktree: /home/me/code/treejar/.worktrees/tj-ee5f-model-battle
write_zone:
  - scripts/model_battle.py
  - scripts/model_battle_cases.py
  - tests/test_scripts_model_battle.py
  - .codex/stages/tj-ee5f/artifacts/tj-ee5f.13-model-battle.md
success_criteria:
  - separate sealed core and background profiles preserve legacy profiles
  - first-party pinned minimal payloads and staged survivor execution are deterministic
  - all attempts contribute tokens, cache, cost, latency, model, provider, and endpoint evidence
  - blind scores are sealed before reveal and evaluator disagreement blocks selection
selected_docs:
  - docs/superpowers/specs/2026-08-03-noor-e2e-remediation-and-model-comparison-spec.md
selected_skills:
  - orchestrator-stage
  - superpowers:test-driven-development
selected_agents:
  - model_battle_remediation
catalog_candidates:
  - none
parallel_group: model-battle
depends_on_streams:
  - tj-ee5f.7
  - tj-ee5f.8
  - tj-ee5f.12
parallel_decision: parallel
status: returned
delivery_method: n/a
accepted_by_orchestrator: no
cleanup_status: pending
cleanup_notes: integration owner must review and integrate the committed branch
risk_level: medium
verification_tier: delta
risk_tags:
  - retry
  - state-transition
  - data
affected_surfaces:
  - backend
invariants:
  - test-matrix
  - state-transition
docs_impact: behavior
docs_reviewed: updated
docs_review_notes: this artifact records the isolated harness behavior and paid-run boundary
verification:
  - uv run pytest tests/test_scripts_model_battle.py -q --tb=short: passed
  - uv run ruff check scripts/model_battle.py scripts/model_battle_cases.py tests/test_scripts_model_battle.py: passed
  - uv run ruff format --check scripts/model_battle.py scripts/model_battle_cases.py tests/test_scripts_model_battle.py: passed
  - git diff --check: passed
changed_files:
  - scripts/model_battle.py
  - scripts/model_battle_cases.py
  - tests/test_scripts_model_battle.py
  - .codex/stages/tj-ee5f/artifacts/tj-ee5f.13-model-battle.md
explicit_defers:
  - paid OpenRouter runs require current explicit owner authority after integration gates
---

# Summary

The existing synthetic harness now has isolated hard profiles for the main chat
and background tasks. It runs a one-attempt round zero, repeats only safe
survivors, keeps the two winner decisions separate, and does not mutate Noor or
any external business system.

# Scope / Routing

Only the assigned harness, fixtures, focused tests, and this artifact changed.
Legacy profiles remain available. Exact hard-scenario text lives in fixture
data, not product logic or the product prompt.

# Verification

Focused RED first failed during import because the new profiles did not exist.
The final focused suite, scoped Ruff checks, formatting check, and whitespace
check pass. No model or external service call was made.

# Delivery / Cleanup

Returned as one isolated commit for orchestrator review and integration.

# Risks / Follow-ups / Explicit Defers

The paid run remains intentionally blocked. Immediately before it, the
orchestrator must use the free metadata preflight, inspect the calculated caps,
and obtain current authority for paid OpenRouter calls.
