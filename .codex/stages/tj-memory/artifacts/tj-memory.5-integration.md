---
schema_version: orchestration-artifact/v1
artifact_type: local-stream
task_id: tj-memory.5
stage_id: tj-memory
agent_type: n/a
subagent_model: n/a
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: Central `src/llm/engine.py` routing work stayed sequential to avoid conflicting behavior changes.
repo: /home/me/code/treejar
branch: codex/tj-memory-customer-facts-layer
base_branch: origin/main
base_commit: d49abcfc0606102b2098880245723e6fda999193
worktree: /home/me/code/treejar
write_zone:
  - src/core/config.py
  - src/llm/engine.py
  - tests/test_llm_engine_customer_facts.py
  - tests/test_dialogue_config.py
success_criteria:
  - `customer_facts_mode=disabled|shadow|enforce` exists and defaults to disabled.
  - Enforce mode extracts/persists accepted facts before legacy route decisions.
  - Compact facts context is added to prompt without treating past orders as current.
  - Layer fails open to legacy behavior without poisoning the DB session.
  - Inbound message id reaches extracted facts when Wazzup provides one.
selected_docs:
  - docs/specs/customer-facts-layer.md
selected_skills:
  - orchestrator-stage
  - superpowers:test-driven-development
  - superpowers:verification-before-completion
selected_agents:
  - none - central routing file required local sequential work
catalog_candidates:
  - none - installed repo assets were sufficient
parallel_group: E
depends_on_streams:
  - B
  - C
  - D
parallel_decision: sequential
status: accepted
delivery_method: manual integration
accepted_by_orchestrator: yes
cleanup_status: not_applicable
cleanup_notes: Local stream on current branch.
risk_level: high
docs_impact: api-contract
docs_reviewed: updated
docs_review_notes: Stage summary and project index updated.
verification:
  - OPENROUTER_API_KEY=dummy uv run pytest tests/test_llm_engine_customer_facts.py tests/test_dialogue_config.py -v --tb=short: passed
  - uv run mypy src/: passed
changed_files:
  - src/core/config.py
  - src/llm/engine.py
  - src/services/chat.py
  - tests/test_llm_engine_customer_facts.py
  - tests/test_services_chat_batch.py
  - tests/test_dialogue_config.py
explicit_defers:
  - tj-memory.7 - production config remains disabled until approved.
---

# Summary

Integrated the Customer Facts Layer into `process_message` behind its own
feature mode. Enforce mode persists facts, feeds compact context to the prompt,
answers past-order lookup deterministically, records inbound source message ids
when available, isolates optional DB writes in a savepoint, and keeps default
behavior disabled.

# Scope / Routing

This was kept local and sequential because `src/llm/engine.py` is the central
message-routing file and concurrent edits would be risky.

# Verification

Targeted engine/config tests passed, ruff targeted checks passed, and `uv run
mypy src/` passed.

# Delivery / Cleanup

Accepted locally on the current branch. No child worktree cleanup was needed.

# Risks / Follow-ups / Explicit Defers

Production config remains disabled until `tj-memory.7`.
