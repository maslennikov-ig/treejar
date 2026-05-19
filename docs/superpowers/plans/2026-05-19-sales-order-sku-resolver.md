# Sales Order SKU Resolver Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix GitHub #38 by resolving explicit sales-order item lists deterministically before the LLM, without expanding prompts.

**Architecture:** Keep PydanticAI tools unchanged. Add deterministic parsing and catalog-backed SKU/name matching before guarded agent runs in `process_message`; unresolved or ambiguous items become pending quote clarification, not manager escalation. Suppress product media after exact-quote fail-closed or handoff responses.

**Tech Stack:** Python 3.12, PydanticAI `RunContext[SalesDeps]`, SQLAlchemy 2 async `AsyncSession.execute(select(...))`, pytest, Beads `tj-gh17`.

---

## Parallel Decomposition Matrix

| Stream | Goal | Agent | Write Zone | Dependencies | Verification | Decision | Reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| parser/resolver | Parse `#38` multi-item sales order and resolve via catalog aliases/name tokens | local | `src/llm/engine.py`, `tests/test_llm_engine.py` | none | targeted parser + process_message tests | sequential local | central routing and tests are tightly coupled |
| media leak audit | Find paths that can leak product media after fail-closed/handoff | explorer | read-only | none | report exact lines and test gaps | parallel | independent read-only risk discovery |
| catalog match audit | Review SKU/name matching edge cases for Treejar formats | explorer | read-only | none | report exact parser/resolver gaps | parallel | independent read-only review |
| closeout | Gates, Beads, GitHub readiness | local | `.codex/stages/tj-gh17/*`, Beads | implementation | targeted/full gates | sequential local | depends on final code |

## Task 1: RED Tests For #38 Parser

**Files:**
- Modify: `tests/test_llm_engine.py`

- [ ] Add a test proving `_extract_sales_order_quote_items("Can I have sales order ? I need 2 SKYLAND LUMA 9719-4 and 3 TORR Cabinet")` returns two candidates:
  - `2 x SKYLAND LUMA 9719-4`, SKU hint `9719-4`
  - `3 x TORR Cabinet`, SKU hint `None`
- [ ] Add a regression proving `extract_exact_quote_candidate()` does not swallow the whole multi-item list as one item.
- [ ] Run: `OPENROUTER_API_KEY=dummy uv run pytest tests/test_llm_engine.py -k "sales_order_items or exact_quote_candidate" -q`
- [ ] Expected before implementation: new test fails on current parser behavior.

## Task 2: Deterministic Parser And Catalog Resolver

**Files:**
- Modify: `src/llm/engine.py`
- Modify: `tests/test_llm_engine.py`

- [ ] Add parser logic that splits sales-order bodies by explicit quantity-start segments and existing item-before-quantity segments.
- [ ] Prefer catalog-backed SKU/name resolution:
  - exact SKU match
  - SKU alias match after removing spaces/hyphens
  - unique token overlap match on SKU, name, description, and `treejar_slug`
- [ ] Do not invent SKU prefixes from product names. `SKYLAND LUMA 9719-4` may expose `9719-4` as an anchor, but must not become `LUMA-9719`.
- [ ] If no unique product is found, store unresolved item in pending quote context and ask a targeted clarification.
- [ ] Run targeted tests from Task 1 plus process-message sales-order tests.

## Task 3: Media Suppression Guard

**Files:**
- Modify: `src/llm/engine.py`
- Modify: `tests/test_llm_engine.py`

- [ ] Add regression for exact-quote fail-closed where an LLM pass queues `pending_product_media`; final `LLMResponse.deferred_product_media` must be empty.
- [ ] Add regression for verified-policy handoff if the audit finds a leak path.
- [ ] Ensure all exact-quote static responses after fail-closed/handoff call `_build_static_response(..., allow_product_media=False)` or equivalent.

## Task 4: Verification And Closeout

**Files:**
- Modify: `.codex/stages/tj-gh17/summary.md`
- Modify: `.codex/stages/tj-gh17/artifacts/*.md` if delegated artifacts are recorded.

- [ ] Run targeted tests:
  - `OPENROUTER_API_KEY=dummy uv run pytest tests/test_llm_engine.py -k "sales_order or exact_quote or product_media" -q`
- [ ] Run canonical gates:
  - `uv run ruff check src/ tests/`
  - `uv run ruff format --check src/ tests/`
  - `uv run mypy src/`
  - `env DYLD_FALLBACK_LIBRARY_PATH="${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}" uv run pytest tests/ -v --tb=short`
  - `scripts/orchestration/run_process_verification.sh`
  - `scripts/orchestration/run_stage_closeout.py --stage tj-gh17`
- [ ] Do not comment on or close GitHub #38 until deploy/live verification is separately authorized or explicitly deferred.
