---
schema_version: orchestration-artifact/v1
artifact_type: local-stream
task_id: tj-memory.6
stage_id: tj-memory
agent_type: n/a
subagent_model: n/a
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: Focused regression tests were added locally after the interfaces stabilized.
repo: /home/me/code/treejar
branch: codex/tj-memory-customer-facts-layer
base_branch: origin/main
base_commit: d49abcfc0606102b2098880245723e6fda999193
worktree: /home/me/code/treejar
write_zone:
  - tests/test_customer_memory_models.py
  - tests/test_customer_memory_service.py
  - tests/test_fact_extractor.py
  - tests/test_llm_engine_customer_facts.py
  - tests/test_services_chat_batch.py
  - tests/test_dialogue_config.py
success_criteria:
  - Multi-field customer replies are extracted and persisted.
  - Past-order lookup is answered from memory and does not call the normal model.
  - Past-order reuse remains confirmation-required.
  - Price objections, source message id propagation, and memory fail-open behavior are covered.
  - No live model call is needed for tests.
selected_docs:
  - docs/specs/customer-facts-layer.md
selected_skills:
  - orchestrator-stage
  - superpowers:test-driven-development
  - superpowers:verification-before-completion
selected_agents:
  - none - focused local regression pass
catalog_candidates:
  - none - installed repo assets were sufficient
parallel_group: F
depends_on_streams:
  - C
  - E
parallel_decision: sequential
status: accepted
delivery_method: manual integration
accepted_by_orchestrator: yes
cleanup_status: not_applicable
cleanup_notes: Local stream on current branch.
risk_level: medium
docs_impact: tests-only
docs_reviewed: updated
docs_review_notes: Stage summary records the focused coverage; full replay remains rollout work.
verification:
  - OPENROUTER_API_KEY=dummy uv run pytest tests/test_customer_memory_service.py tests/test_fact_extractor.py tests/test_llm_engine_customer_facts.py tests/test_services_chat_batch.py -v --tb=short: passed, 46 passed
  - env DYLD_FALLBACK_LIBRARY_PATH="${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}" OPENROUTER_API_KEY=dummy uv run pytest tests/ -v --tb=short: passed, 1271 passed, 19 skipped
  - uv run ruff check targeted files: passed
  - uv run ruff format --check targeted files: passed
  - uv run mypy src/: passed
changed_files:
  - tests/test_customer_memory_models.py
  - tests/test_customer_memory_service.py
  - tests/test_fact_extractor.py
  - tests/test_llm_engine_customer_facts.py
  - tests/test_services_chat_batch.py
  - tests/test_dialogue_config.py
explicit_defers:
  - tj-memory.7 - broad production E2E/evidence remains pending.
---

# Summary

Added focused regression coverage for the new facts layer. The suite covers DB
shape, merge policy, extractor behavior, compact name parsing, prompt injection,
enforce-mode persistence, deterministic past-order lookup, source message id
propagation, price-objection handling, and savepoint-backed fail-open behavior.

# Scope / Routing

This was kept local because the tests depend on the integrated contracts from
the previous streams.

# Verification

The targeted 46-test set and the full local pytest suite passed with no live
OpenRouter calls.

# Delivery / Cleanup

Accepted locally on the current branch. No child worktree cleanup was needed.

# Risks / Follow-ups / Explicit Defers

Broad replay and production E2E evidence remain tracked in `tj-memory.7`.
