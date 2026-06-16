# Order Route Module Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the order/quote route adapter out of `src/llm/engine.py` into a focused module without changing runtime behavior.

**Architecture:** `process_message` remains the orchestration entrypoint in `src/llm/engine.py`, but order/quote deterministic routing is owned by `src/llm/order_quote_routes.py`. The moved module must avoid import-time circular dependencies with `engine.py`; if helper extraction is too broad for one stage, dependencies are kept explicit and the stage remains behavior-preserving.

**Tech Stack:** Python 3.12, FastAPI runtime, PydanticAI, pytest, ruff, mypy, Beads orchestration.

---

### Task 1: Structural RED Test

**Files:**
- Modify: `tests/test_llm_engine.py`

- [ ] Add a structural test importing `src.llm.order_quote_routes`.
- [ ] Assert the new module defines `_order_quote_route_for_turn`.
- [ ] Assert `src/llm/engine.py` no longer defines `_order_quote_route_for_turn`.
- [ ] Run the targeted test and verify it fails before production code changes.

Command:

```bash
OPENROUTER_API_KEY=test uv run pytest tests/test_llm_engine.py::test_order_quote_route_adapter_is_in_dedicated_module -q
```

Expected RED failure: `ModuleNotFoundError` for `src.llm.order_quote_routes` or a failed assertion that `engine.py` still defines the adapter.

### Task 2: Extract Adapter Module

**Files:**
- Create: `src/llm/order_quote_routes.py`
- Modify: `src/llm/engine.py`
- Modify: `tests/test_llm_engine.py`

- [ ] Move `_order_quote_route_for_turn` and its route-local side-effect helpers into the new module.
- [ ] Keep `process_message` calling `_order_quote_route_for_turn` through the imported module symbol.
- [ ] Preserve all customer-facing text, metadata keys, route suffixes, trace fields, and quote creation semantics.
- [ ] Ensure `create_quotation` remains the only tool that performs quotation side effects, with direct calls limited to the adapter side-effect wrapper.

Targeted GREEN command:

```bash
OPENROUTER_API_KEY=test uv run pytest tests/test_llm_engine.py::test_order_quote_route_adapter_is_in_dedicated_module tests/test_llm_engine.py::test_order_quote_create_quotation_calls_are_adapter_owned tests/test_llm_engine.py::test_process_message_order_quote_route_selection_is_adapter_owned -q
```

Expected GREEN result: all selected structural tests pass.

### Task 3: Regression Gates And Closeout

**Files:**
- Modify: `.codex/project-index.md`
- Modify: `.codex/handoff.md`
- Create/update: `.codex/stages/tj-order-route-module-extract/summary.md`
- Create/update: `.codex/stages/tj-order-route-module-extract/artifacts/tj-kk3y.md`

- [ ] Run focused order/quote tests that cover the old repeated tester failures.
- [ ] Run full local gates from `.codex/orchestrator.toml`.
- [ ] Run stage closeout.
- [ ] Close Beads task `tj-kk3y` only after verification evidence is recorded.

Full local commands:

```bash
OPENROUTER_API_KEY=test uv run ruff check src/ tests/
OPENROUTER_API_KEY=test uv run ruff format --check src/ tests/
OPENROUTER_API_KEY=test uv run mypy src/
OPENROUTER_API_KEY=test env DYLD_FALLBACK_LIBRARY_PATH="${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}" uv run pytest tests/ -v --tb=short
scripts/orchestration/run_stage_closeout.py --stage tj-order-route-module-extract
```
