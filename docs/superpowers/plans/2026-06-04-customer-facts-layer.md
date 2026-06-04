# Customer Facts Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a durable facts layer that separates persistent customer profile, current order state, and past order history, then feeds compact known/missing facts into Noor before response generation.

**Architecture:** Add focused persistence for customer profiles, order memories, and normalized facts. Run deterministic extraction first and a fast structured model only for ambiguous facts. Roll out in `disabled` -> `shadow` -> `enforce`, with legacy response generation as fallback until production evidence proves the layer is safer.

**Tech Stack:** Python 3.12/3.13, FastAPI, SQLAlchemy, Alembic, PostgreSQL JSON, Pydantic models, PydanticAI/OpenRouter fast model, pytest, Beads.

---

## File Structure

- Create `src/models/customer_memory.py`: SQLAlchemy models for `CustomerProfile`, `CustomerOrderMemory`, and `CustomerFact`.
- Create Alembic migration under `migrations/versions/`: add new tables and indexes without destructive changes.
- Create `src/services/customer_memory.py`: profile/order lookup, fact merge policy, order lifecycle transitions, compact context builder.
- Create `src/llm/fact_extractor.py`: deterministic extraction plus fast structured extractor boundary.
- Modify `src/core/config.py`: add `customer_facts_mode`, `customer_facts_trace_enabled`, and fast-extractor safety knobs.
- Modify `src/llm/engine.py`: call extractor at the start of customer turns, persist accepted facts, and add compact context to dependencies/runtime directives.
- Modify `src/dialogue/state.py` and `src/dialogue/runner.py` only if needed to mirror fact slots into the dialogue kernel.
- Add tests:
  - `tests/test_customer_memory_models.py`
  - `tests/test_customer_memory_service.py`
  - `tests/test_fact_extractor.py`
  - `tests/test_llm_engine_customer_facts.py`
  - fixture updates under `tests/fixtures/dialogue/`
- Update docs/artifacts:
  - `docs/specs/customer-facts-layer.md`
  - `.codex/stages/tj-memory/*`
  - `.codex/project-index.md` after stable modules exist.

## Parallel Decomposition Matrix

| Stream | Beads | Goal | Owner | Write zone | Dependencies | Verification | Model/reasoning | Decision | Reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A | `tj-memory.1` | Spec and eval contract | local | `docs/specs/customer-facts-layer.md`, plan, stage summary | none | artifact/process verification | inherited | local | Simple orchestration/docs, already in this branch |
| B | `tj-memory.2` | DB schema and memory service skeleton | db-migration-specialist or worker | `src/models/customer_memory.py`, migration, model/service tests | A | model + migration tests | high | parallel after A | Disjoint from extractor and engine integration |
| C | `tj-memory.3` | Deterministic + fast structured extractor | worker | `src/llm/fact_extractor.py`, extractor tests | A | extractor unit tests | high | parallel after A | Disjoint from DB if it returns pure Pydantic facts |
| D | `tj-memory.4` | Order lifecycle transitions | worker | `src/services/customer_memory.py`, lifecycle tests | B service interface | service tests | high | parallel after B interface | Can own lifecycle in service layer |
| E | `tj-memory.5` | `process_message` and prompt integration | orchestrator sequential | `src/llm/engine.py`, prompt/context tests | B+C+D | targeted LLM tests | high | sequential | Central routing file; avoid concurrent edits |
| F | `tj-memory.6` | Regression/eval suite | worker or local | `tests/fixtures/dialogue/*`, replay and E2E-style tests | C+E | replay + engine tests | medium/high | parallel after interfaces | Test-only stream can run after interfaces stabilize |
| G | `tj-memory.7` | Rollout, production evidence, issue closeout | orchestrator/deploy specialist | config/docs/artifacts, deploy evidence | full green | full gates, smoke, E2E | high | sequential final | External delivery and production evidence are serialized |

## Task 1: Config And Models

**Files:**
- Modify: `src/core/config.py`
- Create: `src/models/customer_memory.py`
- Modify: `src/models/__init__.py`
- Create: `migrations/versions/<revision>_add_customer_memory.py`
- Test: `tests/test_customer_memory_models.py`

- [ ] **Step 1: Add RED model tests**

Write tests that import the new models and assert table names, required columns,
and enum-like status values. Include a test that a `CustomerOrderMemory` can be
linked to a `Conversation` and that `CustomerFact.value` stores JSON.

- [ ] **Step 2: Run the RED tests**

Run:

```bash
OPENROUTER_API_KEY=dummy uv run pytest tests/test_customer_memory_models.py -v --tb=short
```

Expected: fail because the models do not exist.

- [ ] **Step 3: Implement models and config**

Add settings:

```python
customer_facts_mode: str = "disabled"
customer_facts_trace_enabled: bool = True
customer_facts_fast_extractor_enabled: bool = True
customer_facts_max_context_orders: int = 3
```

Create focused SQLAlchemy models with these stable names:

- `CustomerProfile`
- `CustomerOrderMemory`
- `CustomerFact`

Use string status fields for compatibility with existing model style.

- [ ] **Step 4: Add Alembic migration**

Create non-destructive tables and indexes:

- unique index on `customer_profiles.canonical_phone`;
- index on `customer_order_memories.customer_profile_id, status`;
- index on `customer_facts.customer_profile_id, scope, key, status`;
- index on `customer_facts.source_message_id`.

- [ ] **Step 5: Verify**

Run:

```bash
OPENROUTER_API_KEY=dummy uv run pytest tests/test_customer_memory_models.py -v --tb=short
uv run ruff check src/models/customer_memory.py tests/test_customer_memory_models.py
uv run ruff format --check src/models/customer_memory.py tests/test_customer_memory_models.py
```

Expected: pass.

## Task 2: Memory Service And Merge Policy

**Files:**
- Create: `src/services/customer_memory.py`
- Test: `tests/test_customer_memory_service.py`

- [ ] **Step 1: Add RED service tests**

Cover:

- profile lookup/creation by canonical phone;
- accepted high-confidence profile fact save;
- lower-confidence conflict creates `proposed` fact, not overwrite;
- current order fact remains scoped to active order;
- quoted snapshot does not close the order;
- accepted/refused/no-response closes current order into history;
- past order reuse returns a confirmation-required payload.

- [ ] **Step 2: Run RED service tests**

Run:

```bash
OPENROUTER_API_KEY=dummy uv run pytest tests/test_customer_memory_service.py -v --tb=short
```

Expected: fail because the service does not exist.

- [ ] **Step 3: Implement service APIs**

Expose small async functions:

```python
async def get_or_create_customer_profile(db, *, phone: str, conversation=None) -> CustomerProfile: ...
async def get_or_create_active_order(db, *, profile: CustomerProfile, conversation) -> CustomerOrderMemory: ...
async def apply_extracted_facts(db, *, profile, order, message, facts) -> FactMergeResult: ...
async def mark_order_quoted(db, *, order, snapshot: dict) -> CustomerOrderMemory: ...
async def close_order(db, *, order, status: str, snapshot: dict | None = None) -> CustomerOrderMemory: ...
async def build_customer_facts_context(db, *, profile, active_order, max_past_orders: int) -> CustomerFactsContext: ...
```

- [ ] **Step 4: Verify service tests**

Run:

```bash
OPENROUTER_API_KEY=dummy uv run pytest tests/test_customer_memory_service.py -v --tb=short
```

Expected: pass.

## Task 3: Fact Extractor

**Files:**
- Create: `src/llm/fact_extractor.py`
- Test: `tests/test_fact_extractor.py`

- [ ] **Step 1: Add RED extractor tests**

Cover deterministic extraction:

- `Lili, individual, 1 Dubai, lili@example.com`;
- `company is LLD, delivery address 2 Business Bay`;
- `same as last time`;
- `same as last time but 8 chairs`;
- `I need 6 CH 616`;
- Arabic agreement/refusal phrases if existing language helpers support them.

- [ ] **Step 2: Add fast-model boundary tests**

Use a fake function/model result. Assert the extractor requests
`settings.openrouter_model_fast`, returns structured facts, and does not call the
main sales model.

- [ ] **Step 3: Implement Pydantic contracts**

Define:

```python
class ExtractedCustomerFact(BaseModel):
    scope: Literal["persistent_profile", "current_order", "past_order_reference"]
    key: str
    value: Any
    confidence: Literal["high", "medium", "low"]
    source: Literal["deterministic", "fast_model"]
    evidence: str
    needs_confirmation: bool = False
    conflicts_with: str | None = None
```

- [ ] **Step 4: Implement deterministic first, fast fallback second**

Keep deterministic helpers pure. Fast model calls must be bounded and skipped in
`disabled` mode. If the fast model fails, return deterministic facts plus trace
failure, not a customer-visible error.

- [ ] **Step 5: Verify extractor tests**

Run:

```bash
OPENROUTER_API_KEY=dummy uv run pytest tests/test_fact_extractor.py -v --tb=short
```

Expected: pass.

## Task 4: Engine Integration

**Files:**
- Modify: `src/llm/engine.py`
- Possibly modify: `src/llm/context.py`, `src/llm/prompts.py`
- Test: `tests/test_llm_engine_customer_facts.py`

- [ ] **Step 1: Add RED engine tests**

Cover:

- after name gate, `Lili, individual, 1 Dubai, lili@example.com` stores all facts
  and resumes prior request;
- quote-details prompt, all details in one message asks only for still-missing
  facts;
- known profile name is not asked again;
- past order question returns past-order summary, not current-order mutation;
- `same as last time` asks confirmation before quote creation;
- no manager escalation is created for these flows.

- [ ] **Step 2: Integrate extraction before route decisions**

At the start of a customer turn:

1. load/create profile and active order;
2. run extractor in configured mode;
3. persist accepted/proposed facts;
4. build compact facts context;
5. add facts context to runtime directives or dependency context.

Do not move quotation/PDF/Zoho side effects into the extractor.

- [ ] **Step 3: Preserve legacy fallback**

If extraction fails, log bounded trace, keep legacy behavior, and avoid blocking
the customer reply.

- [ ] **Step 4: Verify targeted engine tests**

Run:

```bash
OPENROUTER_API_KEY=dummy uv run pytest tests/test_llm_engine_customer_facts.py tests/test_llm_engine.py::test_process_message_bare_name_resume_repairs_duplicate_name_prompt_generically -v --tb=short
```

Expected: pass.

## Task 5: Regression And Replay Suite

**Files:**
- Modify/create fixtures under `tests/fixtures/dialogue/`
- Test: `tests/test_dialogue_replay_fixtures.py`
- Test: `tests/test_llm_engine_customer_facts.py`

- [ ] **Step 1: Add fixtures**

Add replay cases for #36, #37, #39, #40, #48, multi-field detail replies,
past-order lookup, and past-order reuse confirmation.

- [ ] **Step 2: Add assertions**

Each fixture must assert:

- accepted facts;
- proposed facts;
- current order status;
- past order status;
- customer-visible route;
- no unexpected escalation.

- [ ] **Step 3: Verify replay suite**

Run:

```bash
OPENROUTER_API_KEY=dummy uv run pytest tests/test_dialogue_replay_fixtures.py tests/test_llm_engine_customer_facts.py -v --tb=short
```

Expected: pass.

## Task 6: Docs, Closeout, And Delivery

**Files:**
- Modify: `.codex/project-index.md`
- Modify: `.codex/handoff.md`
- Modify/create: `.codex/stages/tj-memory/*`

- [ ] **Step 1: Update stable navigation docs**

After modules exist, add customer memory modules to `.codex/project-index.md`.

- [ ] **Step 2: Run full local gates**

Run:

```bash
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy src/
env DYLD_FALLBACK_LIBRARY_PATH="${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}" OPENROUTER_API_KEY=dummy uv run pytest tests/ -v --tb=short
scripts/orchestration/run_process_verification.sh
scripts/orchestration/run_stage_closeout.py --stage tj-memory
```

- [ ] **Step 3: Shadow deployment only after authorization**

Deploy only with explicit current approval. First production mode should be
`customer_facts_mode=shadow` unless local and replay evidence justify enforce.

## Plan Self-Review

- Spec coverage: each spec section maps to tasks for schema, merge policy,
  extraction, lifecycle, integration, tests, and rollout.
- Placeholder scan: no unfinished placeholder markers are present.
- Type consistency: model and service names are stable across tasks.
- Scope check: this is one coherent layer, but implementation streams are
  separable after the spec and service interfaces are stable.
