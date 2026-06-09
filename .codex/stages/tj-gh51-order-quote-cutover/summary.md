# Stage tj-gh51-order-quote-cutover: GH #51 Order/Quote Frame Cutover

Updated: 2026-06-09
Status: local implementation and stage closeout green; delivery pending approval
Branch: `codex/tj-gh51-order-quote-cutover`
Base: `origin/main` at `f41aba6`
Beads: `tj-oq7a`

docs-reviewed: updated - `docs/specs/dialogue-state-kernel.md` now defines
`order_runtime.quote_frame`, active vs quoted frame lifecycle, and expected-frame
gating; `docs/specs/customer-facts-layer.md` now forbids legacy singular
`order.item` extraction.
graph-reviewed: no-change-needed - Graphify is not configured; no
`graphify-out/GRAPH_REPORT.md` or `[knowledge_graph]` configuration exists.

## Goal

Fix GitHub #51 and related recurring regressions where Noor shows a complete
order summary with item quantities, asks for quote details, then later says it
still needs exact items and quantities. The durable fix is to make the typed
order runtime own a canonical quote frame and make legacy quote metadata only a
migration/rollback fallback.

## Implementation

- Added Pydantic `QuoteLine` and `QuoteFrame` contracts under
  `src/dialogue/order_state.py`.
- Added canonical metadata helpers for `metadata_["order_runtime"]["quote_frame"]`
  with read-only migration from `pending_quote_selection` and
  `quote_customer_details`.
- Updated quote selection writers in `src/llm/engine.py` to write canonical quote
  frames for selection confirmation, sales-order quotes, exact quotes, and
  assistant-prose repair.
- Updated quote-details resume logic to prefer quote-frame items over legacy
  pending selections.
- Made quote-frame lifecycle status-aware: `collecting_details` and
  `repair_required` are active, while `quoted` remains stored for audit/post-
  quotation context but is non-resumable.
- Cleared stale canonical quote frames when unresolved-only or empty quote
  writes have no durable resolved lines.
- Made quote customer details frame-first while mirroring legacy
  `quote_customer_details` for rollback.
- Kept legacy quote-frame migration read-only: quote-detail writes update an
  existing canonical frame but no longer materialize a canonical frame from
  legacy fallback, preserving unresolved sales-order follow-up candidates.
- Ensured stale legacy `pending_quote_selection.unresolved_items` cannot
  override a complete active canonical quote frame, and stale legacy pending
  selections cannot resurrect a `quoted` canonical frame.
- Updated canonical-only quote detail replies to resume from `QuoteFrame` even
  when the assistant prose/history is compacted or unavailable.
- Prevented `quote_details` expected-answer frames from being created from
  assistant prose alone; frames now require durable quote items and carry
  quote-line source refs.
- Cleaned assistant-prose repair candidates so summary prices/totals do not
  pollute SKU resolution.
- Removed deterministic and fast-model `order.item` fact creation; facts now
  use runtime-owned repeatable `order.items`.
- Updated `DialogueState.from_conversation` to import selected items from the
  active canonical quote frame before legacy pending selection, and to map
  `quoted` frames into `post_quotation_hold` instead of `quote_details`.
- Completed read-only review streams: `code_mapper`, `correctness_reviewer`,
  `improvement_reviewer`, `llm_architect`, `qa_expert`, `docs_reviewer`, and
  `architect_reviewer`; accepted must-fix findings were implemented locally.

## Verification

Passed:

- `uv run --extra dev pytest tests/test_llm_engine.py::test_capture_expected_answer_frames_from_customer_facing_questions tests/test_llm_engine.py::test_quote_details_expected_frame_requires_durable_quote_items tests/test_llm_engine.py::test_store_pending_quote_selection_writes_canonical_quote_frame tests/test_llm_engine.py::test_process_message_quote_details_after_bullet_summary_recovers_quote_frame_without_missing_items -q`
- `uv run --extra dev pytest tests/test_llm_engine.py -k "quote_details or pending_quote_selection or quote_resume or unlabeled_quote_brief or sales_order_quote or exact_quote" -q`
- `uv run --extra dev pytest tests/test_fact_extractor.py -q`
- `uv run --extra dev pytest tests/test_dialogue_state.py -q`
- `uv run --extra dev pytest tests/test_dialogue_order_state.py -q`
- `uv run --extra dev pytest tests/test_dialogue_order_state.py tests/test_dialogue_state.py tests/test_fact_extractor.py tests/test_llm_engine.py -k "quote_details or pending_quote_selection or quote_resume or unlabeled_quote_brief or sales_order_quote or exact_quote or quote_frame" -q`
- `uv run --extra dev pytest tests/test_llm_engine.py::test_capture_expected_answer_frames_from_customer_facing_questions tests/test_llm_engine.py::test_process_message_canonical_only_quote_frame_resumes_without_assistant_prose tests/test_llm_engine.py::test_process_message_quoted_quote_frame_blocks_stale_legacy_pending_quote tests/test_llm_engine.py::test_process_message_quote_details_after_bullet_summary_recovers_quote_frame_without_missing_items tests/test_dialogue_state.py::test_dialogue_state_treats_quoted_quote_frame_as_post_quotation_hold -q`
- `uv run --extra dev ruff check src/dialogue/order_state.py src/dialogue/state.py src/llm/engine.py src/llm/fact_extractor.py tests/test_llm_engine.py tests/test_fact_extractor.py tests/test_dialogue_state.py tests/test_dialogue_order_state.py`
- `uv run --extra dev ruff format --check src/dialogue/order_state.py src/dialogue/state.py src/llm/engine.py src/llm/fact_extractor.py tests/test_llm_engine.py tests/test_fact_extractor.py tests/test_dialogue_state.py tests/test_dialogue_order_state.py`
- `uv run pytest tests/test_llm_engine.py::test_process_message_sales_order_unresolved_followup_resumes_quote -q`
- `uv run pytest tests/test_admin_dashboard_frontend.py -q`
- `uv run ruff check src/ tests/`
- `uv run ruff format --check src/ tests/`
- `uv run mypy src/`
- `env DYLD_FALLBACK_LIBRARY_PATH="${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}" uv run pytest tests/ -v --tb=short`
  (`1357 passed, 19 skipped`)

Pending after closeout:

- Delivery approval for push/merge/deploy and any live WhatsApp/prod E2E.
