# Stage tj-gh51-order-quote-cutover: GH #51 Order/Quote Frame Cutover

Updated: 2026-06-09
Status: delivered to main, deployed, and live WhatsApp E2E passed on approved
personal number
Branch: `codex/tj-gh51-order-quote-cutover`
Base: `origin/main` at `f41aba6`
Beads: `tj-oq7a`

docs-reviewed: updated - durable specs already cover canonical quote frames;
this stage summary and `.codex/handoff.md` now record delivery, deploy, smoke,
and the live-test stop condition.
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
- After delivery approval, pushed and merged the stage to `main`, then deployed
  through GitHub Actions.
- Added post-deploy regression fixes for live-test discoveries:
  `a21db4f` strips synthetic test markers before runtime parsing and `7049107`
  preserves multi-item quote requests on the first turn by routing them through
  the existing purchase-selection resolver instead of the exact-quote single
  item path.
- Added post-live regression fixes for the approved personal-number retest:
  `1aa4769` blocks quote-detail prompts while selection confirmation still has
  unresolved items, and `c78309d` lets `selection_confirmation` unresolved-item
  follow-ups resume the quote path.
- Latest live retest on deployed `c78309d` still failed on the second step:
  `CH 616 NEW black` returned `quote-resume-missing-items`. Prod metadata showed
  canonical `order_runtime.quote_frame` had `status=repair_required` but did not
  store the unresolved `4 x CH 616 chairs` candidate, so frame-first reading hid
  the legacy mirror.
- Added typed `QuoteUnresolvedLine` / `QuoteFrame.unresolved_items`, updated
  frame writers for selection confirmation, sales-order quote, and exact-quote
  repair, and kept a migration fallback from legacy unresolved metadata for
  already-created old conversations.

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

Post-delivery verification:

- `uv run pytest tests/test_llm_engine.py::test_process_message_quote_request_with_multiple_items_keeps_all_lines tests/test_llm_engine.py::test_process_message_strips_synthetic_marker_before_order_runtime_layers tests/test_llm_engine.py::test_process_message_exact_quote_missing_details_returns_gate_without_escalation tests/test_llm_engine.py::test_extract_purchase_selection_preserves_mixed_model_and_sku_items tests/test_llm_engine.py::test_process_message_quoted_frame_same_details_does_not_restart_items -q`
  (`5 passed`)
- `uv run pytest tests/test_llm_engine.py -k "exact_quote or selection_confirmation or quote_request_with_multiple_items or synthetic_marker or quoted_frame or post_quotation" -q`
  (`53 passed`)
- `uv run ruff check src/ tests/`
- `uv run ruff format --check src/ tests/`
- `uv run mypy src/`
- `env DYLD_FALLBACK_LIBRARY_PATH="${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}" uv run pytest tests/ -v --tb=short`
  (`1368 passed, 19 skipped`)
- GitHub Actions run `27200937145` passed `changes`, `lint`, `test`,
  `type-check`, and `deploy`; deploy job `80304760664` succeeded for
  `7049107ad04fa67513efb559a6fb2a00115eb9ce`.
- Production API smoke after deploy passed: `scripts/verify_api.py --base-url
  https://noor.starec.ai` reported `8 passed, 0 failed`.
- Latest local post-live fix verification:
  - `uv run pytest tests/test_llm_engine.py::test_store_pending_quote_selection_writes_quote_frame_unresolved_items tests/test_llm_engine.py::test_process_message_selection_unresolved_followup_resumes_from_canonical_quote_frame -q`
    (`2 passed`, RED before fix)
  - `uv run pytest tests/test_llm_engine.py -k "quote_frame or pending_quote_selection or selection_unresolved_followup or quote_resume or exact_quote or selection_confirmation" -q`
    (`58 passed`)
  - `uv run ruff check src/ tests/`
  - `uv run ruff format --check src/ tests/`
  - `uv run mypy src/`
  - `env DYLD_FALLBACK_LIBRARY_PATH="${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}" uv run pytest tests/ -v --tb=short`
    (`1372 passed, 19 skipped`)
- GitHub Actions run `27203026681` passed `changes`, `lint`, `test`,
  `type-check`, and `deploy`; deploy job `80311779370` succeeded for
  `785ad1a21b8b5f3fd16d7b5e75bcbdbef15521ba`.
- Production release marker after deploy:
  `.release-sha=785ad1a21b8b5f3fd16d7b5e75bcbdbef15521ba`,
  `.release-run-id=27203026681`.
- Production API smoke after latest deploy passed: `scripts/verify_api.py
  --base-url https://noor.starec.ai` reported `8 passed, 0 failed`.

Live E2E status:

- Full live WhatsApp E2E was authorized and passed on the approved personal
  phone ending `0921`.
- Core GH51 flow with suffix `tj-gh51-live-multi-20260609T113051Z`:
  - Step 1 confirmed `2 x SKYLAND NOVO 2400 Meeting Table` and asked for exact
    SKU for `4 x CH 616 chairs`; no premature quote-details request.
  - Step 2 `CH 616 NEW black` returned `quote-resume-missing-details`; no
    repeated “exact item(s) and quantity” loop.
  - Step 3 compact details `Lilia / Test company / 2 Street Dubai /
    live-test@example.com` returned `quote-resume` and created quotation
    `Fr3368` / sale order id `378603000022442270`.
  - Prod metadata confirmed `quote_frame.status=quoted`, two quote lines, and
    `unresolved_items=[]`.
- Additional live edge checks passed:
  - `tj-gh51-live-direct-20260609T113051Z`: direct `4 position CH 616 NEW black`
    returned `exact-quote-missing-details`.
  - `tj-gh51-live-qtyrepair-20260609T113051Z`: missing quantity prompt followed
    by `Only SKYLAND NOVO 2400 2 position` returned valid selection summary.
  - `tj-gh51-live-blocker-20260609T113051Z`: discount/payment terms request
    escalated safely with `verified-policy` and `escalation_status=pending`.
