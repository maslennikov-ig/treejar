# Stage tj-order-state: Full Order-State Runtime Refactor

Updated: 2026-06-08
Status: closed locally; follow-up implementation and stage closeout verification passed
Branch: `codex/tj-order-state-refactor`
Base: `main` at `5c85a5b46d28320a1790196b48651ad6bc01a41f`
Beads: `tj-order-state` with children `tj-order-state.1` through
`tj-order-state.9.6`

docs-reviewed: updated - dialogue kernel spec, customer facts spec, project
index, plan file, stage artifacts, and handoff now describe the typed
order-state runtime, bounded runtime trace, inquiry guard, deterministic
`order.items` ownership, prompt privacy boundary, Arabic exact-quote
missing-details copy, and external framework decision.
graph-reviewed: no-change-needed - Graphify is not configured; no
`graphify-out/GRAPH_REPORT.md` or `[knowledge_graph]` configuration exists.
project-index: updated - `src/dialogue/` now names the typed order-state runtime
as a stable subsystem.

## Goal

Replace scattered product/quantity and order-item parsing with a typed
LangGraph/Pydantic order runtime that feeds engine purchase selection, customer
facts, and customer memory consistently. This stage covers GitHub #49 and #50
without adding a new heavy conversation framework.

## Current State

- `src/dialogue/order_state.py` defines `OrderLine`, `OrderIntent`,
  `OrderState`, `OrderDecision`, and `QuoteDetails`.
- `src/dialogue/order_runtime.py` compiles a small `StateGraph`:
  `load_state -> extract_intent -> apply_reducer -> decide`.
- `src/dialogue/order_guards.py` centralizes price, stock, availability, and
  discovery blockers so runtime, engine, and fact extraction agree on
  inquiry-vs-selection behavior.
- `extract_catalog_references()` now rejects connector false positives such as
  `AND-4`, `OR-4`, and `BUT-8`, and handles quantity phrases such as
  `4 position CH 616 chairs` and `SKYLAND NOVO 2400 2 position`.
- `_extract_purchase_selection()` now consumes the order runtime for complete
  item/quantity lines while preserving existing product-discovery blockers and
  the old guard for bare `6 CH 616` without product-selection context. It also
  rejects partially resolved mixed quantity lists so unresolved product lines
  stay on the product path.
- Plain static purchase selection runs before FAQ/behavior retrieval only when
  no quote, pending quote selection, exact-quote follow-up, or quote-intent
  frame is active.
- The order runtime emits a bounded `order_runtime` trace with route, source,
  reason codes, line count, total latency, and phase latency; raw customer text,
  product names, and source fragments are not stored in the trace.
- Exact-quote missing-details gates now use Arabic customer-facing copy for
  Arabic conversations while keeping the same required-field safety gate.
- `extract_customer_facts()` emits a repeatable `order.items` snapshot for
  single-line and multi-line runtime-backed order requests, and customer memory
  accepts `order.items` only from deterministic, valid snapshots. New accepted
  snapshots supersede the previous current-order view rather than creating a
  conflict.
- Customer-facts fast-model prompts redact contact PII, fast-model
  `order.items` are dropped before merge, and the main prompt labels customer
  facts memory as untrusted customer-provided data.
- Compact quote-detail replies can combine slash-separated name/company/address
  details with item corrections; product-looking segments and confirmation
  words are not accepted as company names.
- Zoho, quotation PDF, WhatsApp media, Telegram, and manager escalation side
  effects remain legacy-owned.

## External Runtime Decision

Official docs and repository research support reusing the current stack:

- LangGraph Graph API documents shared state, nodes, edges, and reducers:
  https://docs.langchain.com/oss/python/langgraph/graph-api
- LangGraph persistence documents threads/checkpoints for durable state:
  https://docs.langchain.com/oss/python/langgraph/persistence
- PydanticAI structured output supports typed validation/retry patterns:
  https://pydantic.dev/docs/ai/core-concepts/output/
- Rasa CALM flows and patterns are useful flow/repair references:
  https://rasa.com/docs/pro/build/writing-flows/
- Parlant journeys reinforce conversation flow vs tool/business-logic
  separation:
  https://www.parlant.io/docs/concepts/customization/journeys/

Decision: do not add Rasa or Parlant runtime dependency in this stage.

## Parallel Decomposition Matrix

| Stream | Beads | Goal | Owner | Write zone | Dependencies | Verification | Decision | Reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A | `tj-order-state.1` | External docs/runtime decision | `docs_researcher` read-only | none | none | source links | parallel | Independent docs sidecar |
| B | `tj-order-state.2-.4` | Contract, catalog extraction, order graph | local | `src/dialogue/`, dialogue tests | none | targeted tests, mypy | local/sequential | Defines API for downstream streams |
| C | `tj-order-state.5` | Engine adapter | local | `src/llm/engine.py` | B | engine purchase-selection tests | sequential | Tight coupling with B |
| D | `tj-order-state.6` | Facts/memory alignment | local | `src/llm/fact_extractor.py`, `src/services/customer_memory.py` | B | facts/memory tests | sequential | Small write scope; shares API with B |
| E | `tj-order-state.7` | Regression suite | local | tests | B-D | targeted pytest | sequential | TDD driver for implementation |
| F | `tj-order-state.8` | Docs, review, closeout | local + reviewers | docs/stage files | B-E | review + closeout | sequential final | Depends on implementation result |

## Verification

RED evidence:

- New targeted regression command initially failed 7/7, proving current defects:
  `AND-4`, missing `position` quantities, missing SKYLAND line, and no
  repeatable `order.items`.
- `tests/test_customer_memory_service.py::test_current_order_items_snapshot_updates_without_conflict`
  initially failed with `status='conflict'`.
- `tests/test_dialogue_order_state.py` initially failed on missing
  `OrderState.from_legacy_metadata`.
- `tests/test_dialogue_order_runtime.py` initially failed on missing
  `src.dialogue.order_runtime`.
- Review RED cases later failed on `order.items` rendering as `item`, old
  accepted `order.items` snapshots not being superseded, inactive
  `quantity_clarification`, inquiry turns being saved as order facts, and
  partial mixed selections entering `selection-confirmation`.
- Review-fix RED command later failed 22/22 selected tests, covering `OR-4`,
  mixed complete/missing lines, localized inquiries, single-line `order.items`,
  fast-model PII leakage, model-origin `order.items`, untrusted memory prompt
  text, and slash quote-details/item correction.

GREEN evidence:

- `OPENROUTER_API_KEY=dummy uv run pytest tests/test_dialogue_catalog_refs.py::test_extract_catalog_references_preserves_multi_item_quantities tests/test_dialogue_catalog_refs.py::test_extract_catalog_references_accepts_position_quantity_phrases tests/test_fact_extractor.py::test_deterministic_extracts_repeatable_order_items_snapshot tests/test_llm_engine.py::test_extract_purchase_selection_preserves_mixed_model_and_sku_items tests/test_llm_engine.py::test_extract_purchase_selection_accepts_position_quantity_phrases -v --tb=short`
  -> `7 passed`.
- `OPENROUTER_API_KEY=dummy uv run pytest tests/test_dialogue_order_state.py -v --tb=short`
  -> `2 passed`.
- `OPENROUTER_API_KEY=dummy uv run pytest tests/test_dialogue_order_runtime.py -v --tb=short`
  -> `2 passed`.
- `OPENROUTER_API_KEY=dummy uv run pytest tests/test_dialogue_catalog_refs.py tests/test_dialogue_order_state.py tests/test_dialogue_order_runtime.py tests/test_fact_extractor.py tests/test_customer_memory_service.py tests/test_llm_engine.py -v --tb=short -k "catalog_ref or order_state or order_runtime or order_item or order.items or purchase_selection or quote_customer_details or pending_quote_selection or name_gate"`
  -> `73 passed, 222 deselected`.
- Updated high-signal regression pack:
  `OPENROUTER_API_KEY=dummy uv run pytest tests/test_dialogue_catalog_refs.py tests/test_dialogue_order_state.py tests/test_dialogue_order_runtime.py tests/test_fact_extractor.py tests/test_customer_memory_service.py tests/test_llm_engine.py -v --tb=short -k "catalog_ref or order_state or order_runtime or order_item or order.items or purchase_selection or quote_customer_details or pending_quote_selection or name_gate or stock_and_price or stock_price_inquiries or partially_resolved_mixed_quantity_list"`
  -> `86 passed, 222 deselected`.
- `uv run ruff check src/ tests/` -> `All checks passed!`.
- `uv run ruff format --check src/ tests/` -> `293 files already formatted`.
- `uv run mypy src/` -> `Success: no issues found in 157 source files`.
- `env DYLD_FALLBACK_LIBRARY_PATH="${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}" OPENROUTER_API_KEY=dummy uv run pytest tests/ -v --tb=short`
  -> `1309 passed, 19 skipped`.
- `scripts/orchestration/run_stage_closeout.py --stage tj-order-state`
  -> `stage closeout verification OK`.
- Review-fix targeted suite:
  `OPENROUTER_API_KEY=dummy uv run pytest tests/test_dialogue_catalog_refs.py tests/test_dialogue_order_runtime.py tests/test_fact_extractor.py tests/test_customer_memory_service.py tests/test_llm_engine.py -v --tb=short -k "connector_or or mixed_complete_and_missing or incidental or localized or single_runtime_order_item or item_only or comparison_or_localized or fast_extractor_prompt_redacts or fast_extractor_drops or deterministic_valid_shape or marks_customer_facts_as_untrusted or only_model_position"`
  -> `22 passed, 307 deselected`.
- Review-fix high-signal suite:
  `OPENROUTER_API_KEY=dummy uv run pytest tests/test_dialogue_catalog_refs.py tests/test_dialogue_order_state.py tests/test_dialogue_order_runtime.py tests/test_fact_extractor.py tests/test_customer_memory_service.py tests/test_llm_engine.py -v --tb=short -k "catalog_ref or order_state or order_runtime or order_item or order.items or purchase_selection or quote_customer_details or pending_quote_selection or name_gate or stock_and_price or stock_price_inquiries or partially_resolved_mixed_quantity_list or connector_or or incidental or localized or deterministic_valid_shape or untrusted"`
  -> `107 passed, 225 deselected`.
- Full changed-module suite:
  `OPENROUTER_API_KEY=dummy uv run pytest tests/test_dialogue_catalog_refs.py tests/test_dialogue_order_state.py tests/test_dialogue_order_runtime.py tests/test_fact_extractor.py tests/test_customer_memory_service.py tests/test_llm_engine.py -v --tb=short`
  -> `332 passed`.
- Review-fix final gates:
  - `uv run ruff check src/ tests/` -> `All checks passed!`
  - `uv run ruff format --check src/ tests/` -> `293 files already formatted`
  - `uv run mypy src/` -> `Success: no issues found in 157 source files`
  - `env DYLD_FALLBACK_LIBRARY_PATH="${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}" OPENROUTER_API_KEY=dummy uv run pytest tests/ -v --tb=short`
    -> `1333 passed, 19 skipped`
- Review-fix stage closeout:
  `scripts/orchestration/run_stage_closeout.py --stage tj-order-state`
  -> `stage closeout verification OK`, including `artifact validation OK`,
  `stage tj-order-state ready`, and `process verification OK`.
- Follow-up RED command:
  `OPENROUTER_API_KEY=dummy uv run pytest tests/test_dialogue_order_runtime.py::test_order_runtime_trace_is_bounded_and_records_phase_latency tests/test_llm_engine.py::test_process_message_ch616_selection_confirms_without_manager_handoff tests/test_llm_engine.py::test_process_message_exact_quote_missing_details_uses_arabic_gate -v --tb=short`
  -> failed on missing trace, missing metadata trace, and English-only Arabic
  quote copy.
- Follow-up GREEN command:
  same command -> `3 passed`.
- Exact-quote resume guard regression:
  `OPENROUTER_API_KEY=dummy uv run pytest tests/test_llm_engine.py::test_process_message_name_only_reply_resumes_pending_exact_quote_request tests/test_llm_engine.py::test_process_message_exact_named_item_second_consultative_pass_resolves_to_catalog_sku -v --tb=short`
  -> `2 passed`.
- Follow-up changed-module suite:
  `OPENROUTER_API_KEY=dummy uv run pytest tests/test_dialogue_catalog_refs.py tests/test_dialogue_order_state.py tests/test_dialogue_order_runtime.py tests/test_fact_extractor.py tests/test_customer_memory_service.py tests/test_llm_engine.py -v --tb=short`
  -> `334 passed`.
- Follow-up quality gates:
  - `uv run ruff check src/ tests/` -> `All checks passed!`
  - `uv run ruff format --check src/ tests/` -> `293 files already formatted`
  - `uv run mypy src/` -> `Success: no issues found in 157 source files`
- Follow-up full local repository pytest:
  `env DYLD_FALLBACK_LIBRARY_PATH="${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}" OPENROUTER_API_KEY=dummy uv run pytest tests/ -v --tb=short`
  -> `1335 passed, 19 skipped`.
- Follow-up stage closeout:
  `scripts/orchestration/run_stage_closeout.py --stage tj-order-state`
  -> `stage closeout verification OK`; included `ruff`, `format --check`,
  `mypy`, full pytest `1335 passed, 19 skipped`, artifact validation, stage
  readiness, process verification, docs review, and debt marker scan. Repo E2E
  command is not configured, so live/API E2E was skipped by closeout.

## Review Findings

- `correctness_reviewer`: fixed stock/price questions incorrectly becoming
  `PurchaseSelection`; fixed `catalog_ref` item rendering; fixed mixed
  complete/missing order-line partial selection.
- `improvement_reviewer`: fixed `order.items` superseding, item rendering,
  single-line `order.items`, deterministic-only merge, and active
  missing-quantity lines/`quantity_clarification`.
- `security_auditor` and `responsible_ai_reviewer`: fixed fast-model PII
  prompt exposure, model-origin `order.items`, broad raw order evidence, and
  missing untrusted-data prompt boundary.
- `docs_reviewer`: fixed order-runtime docs vs dialogue-kernel decision-contract
  ambiguity and aligned stage/handoff docs for review-fix status.
- `prompt_regression_tester` and `llm_architect`: fixed facts path storing
  inquiries as accepted order facts and added runtime/fact/engine regressions.
- Orchestrator triage is recorded in
  `.codex/stages/tj-order-state/artifacts/review-fix-triage.md`.

## Explicit Defers

- No explicit `tj-order-state` code defers remain.
- Live WhatsApp/API E2E, deployment, GitHub issue closure, and production
  mutation were not run without explicit approval.
