# Order-State Runtime Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace scattered product/quantity order parsing with a typed order-state runtime that feeds engine selection, customer facts, and memory consistently.

**Architecture:** Use the existing LangGraph/Pydantic stack. `src/dialogue/order_state.py` defines the typed contract; `src/dialogue/order_runtime.py` runs a small graph that loads legacy metadata, extracts order intent, reduces state, and decides whether product-selection handling is valid. Existing Zoho/PDF/WhatsApp side effects remain in `src/llm/engine.py`.

**Tech Stack:** Python 3.12, Pydantic v2, LangGraph, pytest, Ruff, mypy.

---

### Task 1: Regression Coverage

**Files:**
- Modify: `tests/test_dialogue_catalog_refs.py`
- Modify: `tests/test_llm_engine.py`
- Modify: `tests/test_fact_extractor.py`
- Modify: `tests/test_customer_memory_service.py`
- Create: `tests/test_dialogue_order_state.py`
- Create: `tests/test_dialogue_order_runtime.py`

- [x] Add RED coverage for multi-item order text, `position` quantity phrases, repeatable `order.items`, order memory snapshot replacement, legacy metadata hydration, and LangGraph order runtime routing.
- [x] Run targeted tests and confirm failures before code changes.

### Task 2: Typed Contract And Runtime

**Files:**
- Create: `src/dialogue/order_state.py`
- Create: `src/dialogue/order_runtime.py`
- Modify: `src/dialogue/catalog_refs.py`

- [x] Add Pydantic `OrderLine`, `OrderIntent`, `OrderState`, `OrderDecision`, and `QuoteDetails`.
- [x] Add `OrderState.from_legacy_metadata()` for `pending_quote_selection` and `quote_customer_details`.
- [x] Improve catalog reference extraction to avoid `AND-4` false positives and handle `position` quantity phrases.
- [x] Build a LangGraph order runtime with `load_state -> extract_intent -> apply_reducer -> decide`.

### Task 3: Integration

**Files:**
- Modify: `src/llm/engine.py`
- Modify: `src/llm/fact_extractor.py`
- Modify: `src/services/customer_memory.py`

- [x] Route purchase-selection parsing through `run_order_runtime()`.
- [x] Emit repeatable `order.items` snapshots for multi-line order facts.
- [x] Treat current-order `order.items` as a replaceable accepted snapshot instead of a conflict.

### Task 4: Docs And Closeout

**Files:**
- Modify: `docs/specs/dialogue-state-kernel.md`
- Modify: `docs/specs/customer-facts-layer.md`
- Modify: `.codex/project-index.md`
- Create: `.codex/stages/tj-order-state/summary.md`
- Create: `.codex/stages/tj-order-state/artifacts/*.md`

- [x] Document why the runtime uses existing LangGraph/Pydantic/PydanticAI stack and keeps Rasa/Parlant as references only.
- [x] Run reviewer subagents.
- [x] Run full verification gates and stage closeout.

### Task 5: Review Follow-Ups

**Files:**
- Modify: `src/dialogue/order_state.py`
- Modify: `src/dialogue/order_runtime.py`
- Modify: `src/llm/engine.py`
- Modify: `tests/test_dialogue_order_runtime.py`
- Modify: `tests/test_llm_engine.py`
- Modify: `docs/specs/dialogue-state-kernel.md`

- [x] Add bounded `OrderRuntimeTrace` with route, source, reason codes, line count, total latency, and per-node phase latency.
- [x] Persist order runtime traces under `metadata_["order_runtime"]["traces"]` when existing dialogue kernel tracing is enabled.
- [x] Move plain static purchase selection before FAQ/behavior-rule retrieval while preserving quote and service-policy gates.
- [x] Localize exact-quote missing-details copy for Arabic customer flows.
- [x] Add RED/GREEN tests for trace shape, pre-retrieval static selection, and Arabic missing-details copy.
- [x] Run full local repository verification after follow-ups (`1335 passed, 19 skipped`).
