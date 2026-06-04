---
schema_version: orchestration-artifact/v1
artifact_type: delegated-stream
task_id: tj-memory.3
stage_id: tj-memory
agent_type: worker
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: Bounded pure extractor implementation with local TDD; no model override needed.
repo: /home/me/code/treejar
branch: codex/tj-memory-customer-facts-layer
base_branch: origin/main
base_commit: d49abcfc0606102b2098880245723e6fda999193
worktree: /home/me/code/treejar
write_zone:
  - src/llm/fact_extractor.py
  - tests/test_fact_extractor.py
  - .codex/stages/tj-memory/artifacts/tj-memory.3-extractor.md
success_criteria:
  - Pydantic contracts for extracted customer facts and extraction result exist.
  - Deterministic extraction covers compact quote details, contact facts, order item basics, preferences, quote status, and past-order references.
  - Price objections are extracted as objections, not terminal quote refusals.
  - Fast extractor boundary is injectable and passes settings.openrouter_model_fast in requests.
  - Fast extractor failure returns deterministic facts plus bounded trace failure instead of raising.
  - Tests avoid live OpenRouter calls.
selected_docs:
  - docs/specs/customer-facts-layer.md
  - docs/superpowers/plans/2026-06-04-customer-facts-layer.md
selected_skills:
  - orchestrator-stage
  - superpowers:test-driven-development
  - superpowers:verification-before-completion
selected_agents:
  - worker
catalog_candidates:
  - none - installed repo skills were sufficient
parallel_group: C
depends_on_streams:
  - tj-memory.1
parallel_decision: local
status: accepted
delivery_method: manual integration
accepted_by_orchestrator: yes
cleanup_status: not_applicable
cleanup_notes: Shared worktree stream; no child worktree or branch cleanup performed.
risk_level: medium
docs_impact: api-contract
docs_reviewed: no-change-needed
docs_review_notes: Existing spec and implementation plan describe this extractor boundary; orchestrator later updated project index for stable navigation.
verification:
  - "OPENROUTER_API_KEY=dummy uv run pytest tests/test_fact_extractor.py -v --tb=short": passed
  - "uv run ruff check src/llm/fact_extractor.py tests/test_fact_extractor.py": passed
  - "uv run ruff format --check src/llm/fact_extractor.py tests/test_fact_extractor.py": passed
changed_files:
  - src/llm/fact_extractor.py
  - tests/test_fact_extractor.py
  - .codex/stages/tj-memory/artifacts/tj-memory.3-extractor.md
explicit_defers:
  - none
---

# Summary

Implemented the pure customer fact extractor boundary for `tj-memory.3`.
The new boundary returns Pydantic fact/result contracts, deterministic facts,
and an injectable fast-model extraction request using
`settings.openrouter_model_fast`.

# Scope / Routing

Work stayed inside the assigned write zone. The extractor is independent from
DB models, memory services, `src/llm/engine.py`, migrations, prompts, and
delivery docs.

The deterministic layer covers emails, phones, labeled and compact customer
details, company/customer type/address facts, SKU and quantity basics,
delivery/assembly/color/budget preferences, quote agreement/refusal, price
objections, and past-order query/reuse references. Past-order reuse is marked
`needs_confirmation=true`; price concerns such as "too expensive" remain
`quote.objection=price` unless paired with an explicit refusal.

The fast-model boundary is an async injectable callable. The default
PydanticAI/OpenRouter runner is lazy and bounded; unit tests inject fake
callables and do not call live OpenRouter. Fast-model exceptions are converted
to a bounded trace marker while deterministic facts are still returned.

# Verification

- `OPENROUTER_API_KEY=dummy uv run pytest tests/test_fact_extractor.py -v --tb=short`: passed, 10 tests.
- `uv run ruff check src/llm/fact_extractor.py tests/test_fact_extractor.py`: passed.
- `uv run ruff format --check src/llm/fact_extractor.py tests/test_fact_extractor.py`: passed.

# Delivery / Cleanup

Worker stream returned for orchestrator review. No separate child worktree was
created, so no cleanup was needed.

# Risks / Follow-ups / Explicit Defers

No explicit defers. Remaining integration risk belongs to later stage tasks:
service merge policy and `process_message` integration must decide when to run
the fast extractor and how to persist/merge accepted versus proposed facts.
