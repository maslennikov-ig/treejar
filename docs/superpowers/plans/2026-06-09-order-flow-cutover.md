# Order/Quote Flow Cutover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the migration from legacy order/quote branch logic to one typed runtime that owns item selection, quantities, pending questions, quote details, quote creation, and post-quote hold state.

**Architecture:** Use the existing LangGraph, Pydantic, PydanticAI, SQLAlchemy, pytest, Ruff, and mypy stack. Do not add Rasa, Parlant, or a new flow engine. `src/dialogue/order_runtime.py` becomes the policy owner; `src/llm/engine.py` becomes a side-effect adapter for runtime decisions and a fallback for non-order domains.

**Tech Stack:** Python 3.12, Pydantic v2, LangGraph `StateGraph`, PydanticAI structured extraction/test doubles, SQLAlchemy async session, pytest, Ruff, mypy.

---

## Current Root Cause

The current code has the right building blocks, but not the final cutover. `order_runtime` exists, `QuoteFrame` exists, and #49/#50/#51 have targeted coverage. The remaining systemic risk is mixed ownership:

- `pending_product_reference_quantity` plus recent assistant wording owns bare quantity replies.
- `pending_quote_selection` still exists as a writable mirror in several quote paths.
- `quote_customer_details` still exists as a legacy compatibility field.
- assistant-prose recovery can recreate quote state.
- `engine.py` still decides order/quote routing through branch order instead of one typed decision.

The cutover is complete only when these legacy keys are read-only migration or rollback inputs, and a typed frame drives all order/quote customer-visible behavior.

## File Map

- Modify `src/dialogue/order_state.py`: final Pydantic contracts for `OrderFrame`, `OrderLine`, `PendingQuestionFrame`, `QuoteFrame`, `QuoteDetails`, `OrderDecision`, and migration readers.
- Modify `src/dialogue/order_runtime.py`: LangGraph nodes and reducers for load, extract, resolve, reduce, decide, and trace.
- Create `src/dialogue/order_decisions.py`: small typed decision and response/side-effect enums if keeping them separate makes `order_runtime.py` smaller.
- Create `src/dialogue/order_migration.py`: legacy metadata readers and optional rollback mirrors.
- Modify `src/dialogue/catalog_refs.py`: catalog-backed parsing only where needed; avoid broad SKU regex growth.
- Modify `src/llm/engine.py`: replace order/quote branch ownership with one runtime adapter.
- Modify `src/llm/fact_extractor.py`: emit order facts from runtime snapshots only.
- Modify `src/services/customer_memory.py`: treat runtime `order.items` snapshots as replaceable current-order state.
- Modify `src/dialogue/runner.py` and `src/dialogue/state.py`: align expected-answer frames with runtime frames.
- Modify tests: `tests/test_dialogue_order_runtime.py`, `tests/test_dialogue_order_state.py`, `tests/test_llm_engine.py`, `tests/test_fact_extractor.py`, `tests/test_customer_memory_service.py`, `tests/test_dialogue_state.py`, and replay/eval fixtures.
- Modify docs: `docs/specs/dialogue-state-kernel.md`, `docs/specs/customer-facts-layer.md`, `.codex/stages/tj-order-cutover/summary.md`, `.codex/handoff.md`.

## Beads

- Epic: `tj-order-cutover`
- Children: `tj-order-cutover.1` through `tj-order-cutover.8`

## Parallel Decomposition Matrix

| Stream | Goal | Owner | Write Zone | Dependencies | Verification | Decision | Reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A | RED replay/invariants | `qa_expert` or local | tests only | none | targeted failing tests | parallel | Can start before implementation. |
| B | Contract/migration | `python_pro` | `src/dialogue/order_state.py`, migration tests | A scenarios inform edge cases | contract tests | parallel after A starts | Isolated typed model work. |
| C | Runtime reducers/decisions | `ai_engineer`/`python_pro` | `src/dialogue/order_runtime.py`, optional `order_decisions.py` | B contract | runtime tests | sequential after B | Depends on final contract. |
| D | Engine adapter/removal | `backend_developer` | `src/llm/engine.py` | C runtime decisions | engine regression tests | sequential | High-conflict file, one owner. |
| E | Facts/kernel alignment | `ai_engineer`/`python_pro` | facts, memory, dialogue state | B/C snapshot contract | facts and state tests | parallel with D after B | Mostly disjoint write zone. |
| F | Reviews/observability/docs | reviewers/docs | docs, traces, stage artifacts | D/E implementation | review reports, closeout | sequential after D/E | Must review actual code. |

The next orchestrator should spawn visible subagents for A/B/E and read-only reviews when runtime supports it. Keep D local or in one dedicated worker because `src/llm/engine.py` is a high-conflict write zone.

## Task 1: RED Replay Matrix And Invariants

**Files:**
- Modify: `tests/test_llm_engine.py`
- Modify: `tests/test_dialogue_order_runtime.py`
- Create if useful: `tests/fixtures/order_cutover_replays.py`

- [ ] Add a replay table for GitHub #40-#51. Include: issue number, customer turns, required model suffix/route, required metadata invariant, and forbidden text.
- [ ] Add a RED test for the second #42 occurrence:
  - Turn 1: `SK 45 White`
  - Expected response: product quantity clarification and a durable runtime quantity frame.
  - Turn 2: `2`
  - Expected response: selection confirmation or valid next quote step, never generic opener.
- [ ] Add invariant tests:
  - active frame with resolved lines must not ask for item/quantity again;
  - active unresolved frame must ask only for unresolved SKU/model;
  - compact quote details fill existing frame;
  - quoted frame is not resumable for new quote creation.
- [ ] Run targeted tests before implementation.

Commands:

```bash
uv run pytest tests/test_llm_engine.py -k "order_cutover or gh42 or gh49 or gh50 or gh51" -q
uv run pytest tests/test_dialogue_order_runtime.py -q
```

Expected before implementation: at least one new test fails on current mixed-ownership behavior.

## Task 2: Final Typed Contract

**Files:**
- Modify: `src/dialogue/order_state.py`
- Create: `src/dialogue/order_migration.py`
- Modify: `tests/test_dialogue_order_state.py`

- [ ] Add a frame model for pending quantity questions. It must store `frame_id`, `status`, product refs, source refs, asked turn/message id when available, max customer turns, and expiry.
- [ ] Extend quote frames to store resolved lines, unresolved SKU candidates, quote details, lifecycle status, source refs, and idempotency keys for quote side effects.
- [ ] Move legacy readers into `order_migration.py`. Supported legacy inputs: `pending_product_reference_quantity`, `pending_quote_selection`, `quote_customer_details`, and old `dialogue_kernel.state.expected_answer_frames`.
- [ ] Add tests for valid metadata, invalid metadata, legacy migration, quoted-frame non-resume, and stale frame expiry.

Commands:

```bash
uv run pytest tests/test_dialogue_order_state.py -q
uv run ruff check src/dialogue/order_state.py src/dialogue/order_migration.py tests/test_dialogue_order_state.py
```

Expected after task: contract tests pass and no order/quote runtime code writes legacy keys directly.

## Task 3: Runtime-Owned Quantity Frames

**Files:**
- Modify: `src/dialogue/order_runtime.py`
- Modify: `src/dialogue/catalog_refs.py`
- Modify: `tests/test_dialogue_order_runtime.py`
- Modify: `tests/test_llm_engine.py`

- [ ] Update the LangGraph runtime so missing-quantity detection creates an active typed quantity frame.
- [ ] Match bare numeric/word replies against the active frame from metadata, not against exact assistant prose.
- [ ] Keep stale-frame protection with explicit expiry/turn counters rather than "last assistant contained quantity".
- [ ] Add tests for compressed/missing recent history, stale frame non-consumption, multi-product quantity prompts, and localized Arabic quantity replies if supported.

Commands:

```bash
uv run pytest tests/test_dialogue_order_runtime.py -q
uv run pytest tests/test_llm_engine.py -k "pending_quantity or bare_quantity or product_quantity_clarify or gh42" -q
```

Expected after task: `SK 45 White` -> `2` is handled from durable runtime state and cannot reset to a generic opener.

## Task 4: Runtime-Owned Quote Selection And SKU Repair

**Files:**
- Modify: `src/dialogue/order_runtime.py`
- Modify: `src/llm/engine.py`
- Modify: `tests/test_dialogue_order_runtime.py`
- Modify: `tests/test_llm_engine.py`

- [ ] Move multi-item purchase selection into runtime reducers.
- [ ] Store unresolved candidates as typed frame entries with quantity and original item candidate.
- [ ] Resolve follow-up exact SKU/model text against unresolved candidates and preserve already resolved lines.
- [ ] Ensure complete frames collect quote details or create quotations; they must not ask again for exact item(s) and quantity.

Commands:

```bash
uv run pytest tests/test_llm_engine.py -k "quote_request_with_multiple_items or selection_unresolved_followup or quote_resume or exact_quote or gh49 or gh50 or gh51" -q
```

Expected after task: #49/#50/#51 scenarios pass through runtime frame state, not assistant-prose recovery.

## Task 5: Engine Adapter And Legacy Branch Removal

**Files:**
- Modify: `src/llm/engine.py`
- Modify: `tests/test_llm_engine.py`

- [ ] Introduce one adapter function in `engine.py`, for example `_handle_order_runtime_decision(...)`, that maps typed runtime decisions to existing static responses and side effects.
- [ ] Route order/quote turns through the adapter before FAQ/RAG and generic LLM calls when the runtime handles them.
- [ ] Remove or disable writable authority from these old branches: `pending_product_reference_quantity`, direct `pending_quote_selection` writes, quote-details resume from assistant prose, and exact quote repair branches that bypass the runtime.
- [ ] Keep legacy fallback only for non-order domains, explicit rollback, or migration reads.

Commands:

```bash
uv run pytest tests/test_llm_engine.py -k "order_cutover or quote_resume or exact_quote or product_quantity_clarify or selection_confirmation or post_quotation" -q
uv run ruff check src/llm/engine.py tests/test_llm_engine.py
```

Expected after task: `src/llm/engine.py` is still the side-effect integration point, but no longer owns order/quote state policy through branch order.

## Task 6: Facts, Memory, And Dialogue Kernel Alignment

**Files:**
- Modify: `src/llm/fact_extractor.py`
- Modify: `src/services/customer_memory.py`
- Modify: `src/dialogue/runner.py`
- Modify: `src/dialogue/state.py`
- Modify: `tests/test_fact_extractor.py`
- Modify: `tests/test_customer_memory_service.py`
- Modify: `tests/test_dialogue_state.py`

- [ ] Make deterministic `order.items` facts originate from runtime snapshots only.
- [ ] Drop fast-model `order.items` and all `order.item` facts as authoritative input.
- [ ] Generate `quote_details` expected-answer frames from runtime frames with source refs.
- [ ] Ensure quoted frames become post-quotation hold state, not new quote-detail collection.

Commands:

```bash
uv run pytest tests/test_fact_extractor.py tests/test_customer_memory_service.py tests/test_dialogue_state.py -q
```

Expected after task: facts/memory can summarize order state but cannot override runtime-owned item and quantity lines.

## Task 7: Observability And Review-Fix Gate

**Files:**
- Modify: `src/dialogue/order_runtime.py`
- Modify: `src/llm/engine.py`
- Create/modify: `.codex/stages/tj-order-cutover/artifacts/review-*.md`

- [ ] Persist bounded non-PII runtime traces with `frame_id`, status, decision, reason codes, resolved/unresolved counts, and legacy migration read flag.
- [ ] Run read-only review streams: `correctness_reviewer`, `improvement_reviewer`, `llm_architect`, `architect_reviewer`, `qa_expert`, `risk_manager`, and `docs_reviewer`.
- [ ] Accept/reject each finding explicitly. Fix accepted must-fix findings before delivery; track justified defers in Beads and handoff.

Commands:

```bash
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy src/
```

Expected after task: review reports are persisted and no accepted must-fix finding remains open.

## Task 8: Full Verification, Delivery, And Live E2E

**Files:**
- Modify: `.codex/stages/tj-order-cutover/summary.md`
- Modify: `.codex/handoff.md`
- Modify: docs touched by implementation

- [ ] Run full local gates:

```bash
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy src/
env DYLD_FALLBACK_LIBRARY_PATH="${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}" uv run pytest tests/ -v --tb=short
scripts/orchestration/run_stage_closeout.py --stage tj-order-cutover
```

- [ ] Only after explicit approval, push/merge/deploy.
- [ ] After deploy, run production API smoke:

```bash
uv run python scripts/verify_api.py --base-url https://noor.starec.ai
```

- [ ] Only after explicit approval, run live WhatsApp E2E. Required matrix:
  - second #42 occurrence: `SK 45 White` -> `2`;
  - #50: `I need 2 SKYLAND NOVO 2400 Meeting Table and 4 CH 616 chairs`;
  - unresolved repair: `CH 616 NEW black`;
  - #49/#51 compact details after full summary;
  - `Only SKYLAND NOVO 2400 2 position`;
  - direct SKU+quantity quote;
  - discount/payment/human handoff blocker;
  - duplicate-message check: no repeated identical bot message for one customer turn.

Expected after task: production evidence proves the cutover, and `.codex/handoff.md` points to the deployed SHA/run/live E2E evidence.

## Self-Review

- Spec coverage: covers root cause, contract, runtime, engine adapter, facts/memory/kernel, tests, review, delivery, and live E2E.
- Unfinished-marker scan: no unfinished markers are intentionally left.
- Type consistency: plan uses `OrderFrame` as the target umbrella frame and `QuoteFrame` for quote-specific substate; implementation may keep the existing `QuoteFrame` name but must expose one runtime-owned active frame to the engine.
