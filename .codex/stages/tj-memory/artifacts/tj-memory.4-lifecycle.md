---
schema_version: orchestration-artifact/v1
artifact_type: local-stream
task_id: tj-memory.4
stage_id: tj-memory
agent_type: n/a
subagent_model: n/a
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: Sequential service/engine lifecycle work after DB and extractor interfaces returned.
repo: /home/me/code/treejar
branch: codex/tj-memory-customer-facts-layer
base_branch: origin/main
base_commit: d49abcfc0606102b2098880245723e6fda999193
worktree: /home/me/code/treejar
write_zone:
  - src/services/customer_memory.py
  - src/llm/engine.py
  - tests/test_customer_memory_service.py
  - tests/test_llm_engine_customer_facts.py
success_criteria:
  - Sent quotation creates quoted snapshot without closing the order.
  - Accepted/refused quote status can close quoted snapshot into history.
  - Price objections do not close a quoted snapshot as refused.
  - Past-order references remain confirmation-required and do not mutate current order.
selected_docs:
  - docs/specs/customer-facts-layer.md
selected_skills:
  - orchestrator-stage
  - superpowers:test-driven-development
  - superpowers:verification-before-completion
selected_agents:
  - none - sequential central integration
catalog_candidates:
  - none - installed repo assets were sufficient
parallel_group: D
depends_on_streams:
  - B
parallel_decision: sequential
status: accepted
delivery_method: manual integration
accepted_by_orchestrator: yes
cleanup_status: not_applicable
cleanup_notes: Local stream on current branch.
risk_level: medium
docs_impact: behavior
docs_reviewed: updated
docs_review_notes: Stage summary and project index updated.
verification:
  - OPENROUTER_API_KEY=dummy uv run pytest tests/test_customer_memory_models.py tests/test_customer_memory_service.py tests/test_fact_extractor.py tests/test_llm_engine_customer_facts.py tests/test_dialogue_config.py -v --tb=short: passed
  - uv run mypy src/: passed
changed_files:
  - src/services/customer_memory.py
  - src/llm/engine.py
  - tests/test_customer_memory_service.py
  - tests/test_llm_engine_customer_facts.py
explicit_defers:
  - tj-memory.7 - production shadow/evidence remains pending.
---

# Summary

Implemented v1 order-memory lifecycle boundaries: quotations can create a
`quoted_snapshot`, accepted/refused quote status can close that snapshot, price
objections stay inside the current order flow, and past-order references stay
confirmation-required.

# Scope / Routing

This was kept local and sequential because it shares `src/llm/engine.py` with
the central integration path.

# Verification

Targeted model/service/extractor/engine/config tests passed, and `uv run mypy
src/` passed.

# Delivery / Cleanup

Accepted locally on the current branch. No child worktree cleanup was needed.

# Risks / Follow-ups / Explicit Defers

Production rollout and broad E2E evidence remain tracked in `tj-memory.7`.
