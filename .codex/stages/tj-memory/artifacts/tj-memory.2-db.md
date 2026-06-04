---
schema_version: orchestration-artifact/v1
artifact_type: delegated-stream
task_id: tj-memory.2
stage_id: tj-memory
agent_type: db_migration_specialist
subagent_model: inherit_orchestrator
reasoning_effort: high
model_reasoning_rationale: Data migration and durable schema work require careful rollback and integrity checks.
repo: /home/me/code/treejar
branch: codex/tj-memory-customer-facts-layer
base_branch: origin/main
base_commit: d49abcfc0606
worktree: /home/me/code/treejar
write_zone:
  - src/models/customer_memory.py
  - src/models/__init__.py
  - migrations/versions/2026_06_04_add_customer_memory.py
  - src/services/customer_memory.py
  - tests/test_customer_memory_models.py
  - tests/test_customer_memory_service.py
  - .codex/stages/tj-memory/artifacts/tj-memory.2-db.md
success_criteria:
  - SQLAlchemy models for CustomerProfile, CustomerOrderMemory, and CustomerFact match the stage spec.
  - Non-destructive Alembic migration adds tables and useful indexes with reversible downgrade.
  - Memory service exposes profile/order lookup, fact merge, lifecycle, and compact context APIs.
  - Merge policy accepts high-confidence facts, preserves order scope, and prevents silent conflict overwrites.
  - Tests run without live external calls.
selected_docs:
  - docs/specs/customer-facts-layer.md
  - docs/superpowers/plans/2026-06-04-customer-facts-layer.md
selected_skills:
  - orchestrator-stage
  - superpowers:test-driven-development
  - superpowers:verification-before-completion
selected_agents:
  - db_migration_specialist
catalog_candidates:
  - none - installed repo skills and selected specialist were sufficient
parallel_group: B
depends_on_streams:
  - A
parallel_decision: local
status: accepted
delivery_method: manual integration
accepted_by_orchestrator: yes
cleanup_status: not_applicable
cleanup_notes: Shared current branch was used per prompt; no worker worktree cleanup performed.
risk_level: high
docs_impact: migration
docs_reviewed: no-change-needed
docs_review_notes: Existing stage spec and implementation plan document the persistence shape; orchestrator later updated project index for stable navigation.
verification:
  - OPENROUTER_API_KEY=dummy uv run pytest tests/test_customer_memory_models.py tests/test_customer_memory_service.py -v --tb=short: passed
  - uv run ruff check src/models/customer_memory.py src/services/customer_memory.py tests/test_customer_memory_models.py tests/test_customer_memory_service.py: passed
  - uv run ruff format --check src/models/customer_memory.py src/services/customer_memory.py tests/test_customer_memory_models.py tests/test_customer_memory_service.py: passed
  - uv run alembic heads: passed
  - uv run alembic history --verbose | sed -n '1,80p': passed
  - OPENROUTER_API_KEY=dummy uv run pytest tests/test_customer_memory_models.py tests/test_customer_memory_service.py tests/test_migrations.py -v --tb=short: passed
changed_files:
  - src/models/customer_memory.py
  - src/models/__init__.py
  - migrations/versions/2026_06_04_add_customer_memory.py
  - src/services/customer_memory.py
  - tests/test_customer_memory_models.py
  - tests/test_customer_memory_service.py
  - .codex/stages/tj-memory/artifacts/tj-memory.2-db.md
explicit_defers:
  - none
---

# Summary

Implemented the persistence foundation for the Customer Facts and Order Memory Layer.
The schema separates durable customer profile data, active/historical order memory,
and normalized facts. The service layer provides deterministic merge and lifecycle
primitives without touching LLM integration or extractor files.

# Scope / Routing

This stream stayed inside the assigned DB/service write zone. It used the repo-local
customer facts spec and implementation plan; no external Alembic or SQLAlchemy docs
were needed. Another worker appears to own extractor files, so those files were not
read or modified.

Data integrity choices:

- `customer_profiles.canonical_phone` is unique.
- `customer_order_memories` keeps `active` and `quoted_snapshot` rows separate from
  terminal historical statuses.
- `customer_facts` stores profile/order-scoped JSON values with confidence, status,
  source excerpt, and source message id.
- Lower-confidence or conflicting replacements are stored as `conflict` or
  `proposed`; accepted facts are not silently overwritten.
- `past_order_reference` facts are saved as confirmation-required proposed facts and
  do not mutate the active order.

Rollback notes:

- Upgrade only creates new tables and indexes.
- Downgrade drops indexes, then the new fact/order/profile tables.
- No existing table or data is altered.

# Verification

Passed:

- `OPENROUTER_API_KEY=dummy uv run pytest tests/test_customer_memory_models.py tests/test_customer_memory_service.py -v --tb=short`
- `uv run ruff check src/models/customer_memory.py src/services/customer_memory.py tests/test_customer_memory_models.py tests/test_customer_memory_service.py`
- `uv run ruff format --check src/models/customer_memory.py src/services/customer_memory.py tests/test_customer_memory_models.py tests/test_customer_memory_service.py`
- `uv run alembic heads`
- `uv run alembic history --verbose | sed -n '1,80p'`
- `OPENROUTER_API_KEY=dummy uv run pytest tests/test_customer_memory_models.py tests/test_customer_memory_service.py tests/test_migrations.py -v --tb=short`

Alembic currently reports one head: `2026_06_04_customer_memory`, parent
`2026_05_08_bot_behavior_rules`.

# Delivery / Cleanup

Returned for orchestrator review on the current branch. No deployment, production
mutation, GitHub operation, or external live test was run.

# Risks / Follow-ups / Explicit Defers

Residual integration risk remains for later stage tasks: the extractor and
`process_message` integration must pass these service contracts without using
past-order references as direct quote data. No explicit defers for `tj-memory.2`.
