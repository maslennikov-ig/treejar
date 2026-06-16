# Stage tj-order-cutover-route-adapter: Order/Quote Route Adapter Extraction

Updated: 2026-06-16
Status: delivered to production; live E2E and synthetic cleanup complete
Branch: `codex/tj-order-route-adapter`
Worktree: `/home/me/code/treejar/.worktrees/tj-order-route-adapter`
Beads: `tj-order-cutover.10` closed

docs-reviewed: no-change-needed - refactor preserves documented customer-facing
runtime ownership; the live-E2E bare ordinal and quantity-frame repairs are
internal route parsing/state preservation for already asked order questions, and
the single stock-option quote-resume repair preserves existing affirmative quote
resume behavior; no public API, operator workflow, deployment contract,
integration contract, or durable doc contract changed.
graph-reviewed: no-change-needed - Graphify is not configured in this worktree;
no `graphify-out/GRAPH_REPORT.md` exists.
project-index: reviewed-no-change - no stable entrypoints, routes, directories,
integrations, or verification commands changed.

## Goal

Complete Beads `tj-order-cutover.10` by extracting the remaining deterministic
order/quote route-selection families from `src/llm/engine.py::process_message`
into a dedicated runtime adapter function without changing customer-facing
behavior.

## Scope

- Added `_order_quote_route_for_turn` as the order/quote route adapter.
- Kept `process_message` responsible for turn preparation, policy/FAQ setup,
  and fallback LLM handling, but removed direct deterministic handling for:
  - sales-order quote extraction and unresolved-item resume;
  - exact-quote SKU repair and unresolved follow-up;
  - selection confirmation;
  - quote-detail resume and missing-detail quote resume;
  - missing quantity/reference clarification.
- Preserved `_pending_reference_route_for_turn` and routed its result through the
  broader adapter so the existing pending quantity/reference path remains typed
  and behavior-compatible.
- Preserved `create_quotation` ownership: direct calls still exist only inside
  `_execute_order_quote_side_effect`.
- During first production E2E after `ab865b3`, bare `2` after a numbered SKU
  option list fell through to `verified-policy-clarify`. Added a context-gated
  bare-ordinal parser path that only activates when the last assistant message
  contains numbered SKU options.
- During second production E2E after `32baf76`, the same route stayed in
  `selection-confirmation` but lost the original quantity after name-gate and
  defaulted to quantity 1. Added a prompt-quantity fallback from the last
  numbered SKU option prompt.
- During third production E2E after `8fb39cb`, the pending quantity/reference
  path failed when the quantity prompt came from `dialogue-kernel|product_selection`:
  the response asked for quantity but stored no canonical
  `order_runtime.pending_question_frame`, so the follow-up `2` fell through to
  `verified-policy-clarify`. Added `_store_kernel_quantity_prompt_frame` so
  kernel product-selection quantity prompts persist the deterministic order
  runtime frame before returning.
- During fourth production E2E after `4d68f78`, short affirmative follow-up
  after a single stock/price option lost the quote context: the first turn
  returned `z-ai/glm-5|stock-price-options`, but `Yes prepare the quotation`
  fell through to `z-ai/glm-5|proposal-clarify`. Added a single-option
  stock/price parser and quote-resume storage path gated by an explicit
  assistant offer to prepare/send a quote.

## Verification

- RED:
  - `OPENROUTER_API_KEY=test uv run pytest tests/test_llm_engine.py::test_process_message_order_quote_route_selection_is_adapter_owned -q`
    failed because `_order_quote_route_for_turn` did not exist and
    `process_message` still called deterministic route helpers directly.
  - `OPENROUTER_API_KEY=test uv run pytest tests/test_llm_engine.py::test_process_message_confirms_bare_ordinal_from_prior_sku_options -q`
    failed with `mock-model|verified-policy-clarify`, matching the production
    E2E gap for `2` after numbered SKU options.
  - `OPENROUTER_API_KEY=test uv run pytest tests/test_llm_engine.py::test_process_message_bare_ordinal_keeps_option_prompt_quantity_after_name_gate -q`
    failed because the route stayed in `selection-confirmation` but returned
    quantity 1 instead of the option prompt's quantity 2.
  - `OPENROUTER_API_KEY=test uv run pytest tests/test_llm_engine.py::test_process_message_kernel_quantity_prompt_stores_order_runtime_frame -q`
    failed with `KeyError: 'order_runtime'`, matching production conversation
    `b228ac0e-ecbd-4d12-9a1f-671286733bba` where
    `dialogue-kernel|product_selection` asked for quantity without storing a
    pending frame and the next `2` returned `verified-policy-clarify`.
  - `OPENROUTER_API_KEY=test uv run pytest tests/test_llm_engine.py::test_stock_price_single_option_is_quote_resume_candidate tests/test_llm_engine.py::test_process_message_short_quote_followup_uses_single_stock_price_option -q`
    failed because the stock/price option prose produced no quote candidate and
    the follow-up route fell through to `mock-model|proposal-clarify`.
- GREEN / targeted:
  - `OPENROUTER_API_KEY=test uv run pytest tests/test_llm_engine.py::test_process_message_order_quote_route_selection_is_adapter_owned -q`
    -> 1 passed.
  - `OPENROUTER_API_KEY=test uv run pytest tests/test_llm_engine.py::test_process_message_pending_reference_route_is_adapter_owned tests/test_llm_engine.py::test_process_message_order_quote_route_selection_is_adapter_owned tests/test_llm_engine.py::test_process_message_exact_quote_unresolved_item_clarifies_without_escalation tests/test_llm_engine.py::test_process_message_unresolved_only_canonical_quote_frame_resumes_without_legacy tests/test_llm_engine.py::test_process_message_sales_order_request_creates_multi_item_quotation tests/test_llm_engine.py::test_process_message_selection_unresolved_followup_resumes_from_canonical_quote_frame tests/test_llm_engine.py::test_process_message_exact_quote_unresolved_followup_resolves_sku_and_quantity tests/test_llm_engine.py::test_process_message_sales_order_unresolved_followup_resumes_quote tests/test_llm_engine.py::test_process_message_sales_order_resolved_followup_then_brief_creates_quote tests/test_llm_engine.py::test_process_message_quote_details_reply_clears_stale_name_gate_request tests/test_llm_engine.py::test_process_message_quote_details_blocks_proceed_with_units_recovery tests/test_llm_engine.py::test_process_message_active_quote_repair_bypasses_dialogue_kernel_product_selection tests/test_llm_engine.py::test_process_message_expired_quantity_frame_blocks_legacy_pending_reference -q`
    -> 13 passed.
  - `OPENROUTER_API_KEY=test uv run pytest tests/test_dialogue_order_runtime.py tests/test_llm_engine.py -q`
    -> 339 passed.
  - `OPENROUTER_API_KEY=test uv run pytest tests/test_llm_engine.py::test_process_message_confirms_bare_ordinal_from_prior_sku_options tests/test_llm_engine.py::test_process_message_confirms_ordinal_selection_from_prior_sku_options tests/test_llm_engine.py::test_ordinal_option_from_reply_supports_more_than_two_options -q`
    -> 3 passed after the bare-ordinal fix.
  - `OPENROUTER_API_KEY=test uv run pytest tests/test_llm_engine.py::test_process_message_bare_ordinal_keeps_option_prompt_quantity_after_name_gate tests/test_llm_engine.py::test_process_message_confirms_bare_ordinal_from_prior_sku_options tests/test_llm_engine.py::test_process_message_confirms_ordinal_selection_from_prior_sku_options tests/test_llm_engine.py::test_ordinal_option_from_reply_supports_more_than_two_options -q`
    -> 4 passed after the quantity preservation fix.
  - `OPENROUTER_API_KEY=test uv run pytest tests/test_llm_engine.py::test_process_message_kernel_quantity_prompt_stores_order_runtime_frame tests/test_llm_engine.py::test_process_message_missing_quantity_reference_then_bare_number_resolves_selection tests/test_llm_engine.py::test_process_message_pending_quantity_descriptor_followup_resolves_novo_table tests/test_llm_engine.py::test_process_message_pending_reference_route_is_adapter_owned tests/test_llm_engine.py::test_process_message_order_quote_route_selection_is_adapter_owned tests/test_llm_engine.py::test_process_message_bare_ordinal_keeps_option_prompt_quantity_after_name_gate tests/test_llm_engine.py::test_process_message_confirms_bare_ordinal_from_prior_sku_options tests/test_llm_engine.py::test_process_message_confirms_ordinal_selection_from_prior_sku_options tests/test_llm_engine.py::test_ordinal_option_from_reply_supports_more_than_two_options -q`
    -> 9 passed after the dialogue-kernel quantity-frame fix.
  - `OPENROUTER_API_KEY=test uv run pytest tests/test_llm_engine.py::test_stock_price_single_option_is_quote_resume_candidate tests/test_llm_engine.py::test_process_message_short_quote_followup_uses_single_stock_price_option -q`
    -> 2 passed after the single stock-option quote-resume fix.
  - `OPENROUTER_API_KEY=test uv run pytest tests/test_llm_engine.py::test_process_message_short_quote_followup_uses_single_stock_price_option tests/test_llm_engine.py::test_stock_price_single_option_is_quote_resume_candidate tests/test_llm_engine.py::test_process_message_quote_confirmation_blocks_availability_offer_recovery tests/test_llm_engine.py::test_process_message_quote_details_blocks_proceed_with_units_recovery -q`
    -> 4 passed, confirming generic availability/proceed prose is still blocked.
- Full local gates:
  - `OPENROUTER_API_KEY=test uv run ruff check src/ tests/` -> passed.
  - `OPENROUTER_API_KEY=test uv run ruff format --check src/ tests/` -> passed.
  - `OPENROUTER_API_KEY=test uv run mypy src/` -> passed, no issues in 157
    source files.
  - First `OPENROUTER_API_KEY=test uv run pytest tests/ -q` failed only because
    fresh `frontend/admin/node_modules` lacked `esbuild`.
  - `npm ci` in `frontend/admin` installed dependencies; npm reported 0
    vulnerabilities and the existing local Node engine warning
    (`v24.16.0` vs package `>=22.12.0 <23`).
  - Final `OPENROUTER_API_KEY=test uv run pytest tests/ -q` passed:
    1413 passed, 19 skipped.
  - Final post-bare-ordinal-fix `OPENROUTER_API_KEY=test uv run pytest tests/ -q`
    passed: 1414 passed, 19 skipped.
  - Final post-quantity-fix `OPENROUTER_API_KEY=test uv run pytest tests/ -q`
    passed: 1415 passed, 19 skipped.
  - Final post-dialogue-kernel-quantity-frame-fix `OPENROUTER_API_KEY=test uv run pytest tests/ -q`
    passed: 1416 passed, 19 skipped.
  - Final post-single-stock-option-quote-resume-fix `OPENROUTER_API_KEY=test uv run pytest tests/ -q`
    passed: 1418 passed, 19 skipped.
- Stage closeout:
  - `scripts/orchestration/run_stage_closeout.py --stage tj-order-cutover-route-adapter`
    passed: artifact validation OK, process verification OK, project-index/docs
    review OK, debt marker scan OK, full code-change verification OK, and stage
    closeout verification OK.
  - Post-bare-ordinal-fix closeout passed again with the same stage command.
  - Post-dialogue-kernel-quantity-frame-fix closeout passed again with the same
    stage command.
  - Post-single-stock-option-quote-resume-fix closeout passed again with the
    same stage command: artifact validation OK, process verification OK,
    project-index/docs review OK, debt marker scan OK, full code-change
    verification OK, and stage closeout verification OK.

## Changed Files

- `src/llm/engine.py`
- `tests/test_llm_engine.py`
- `.codex/handoff.md`
- `.codex/stages/tj-order-cutover-route-adapter/summary.md`
- `.codex/stages/tj-order-cutover-route-adapter/artifacts/tj-order-cutover.10.md`

## Delivery

Initial delivery commit `ab865b3` reached production and passed marker/smoke, but
live E2E found the bare `2` selection-confirmation gap above. Second delivery
commit `32baf76` reached production and passed marker/smoke, but live E2E found
the quantity-preservation gap above. Third delivery commit `8fb39cb` reached
production and passed marker/smoke; live E2E verified name-gate resume, bare
`2` quantity preservation, exact-quote repair/resume, SKU variant, and
all-details first turn, then found the dialogue-kernel pending quantity frame
gap above. Fourth delivery commit `4d68f78` reached production and passed
marker/smoke; live E2E verified the pending quantity/reference fix, then found
the single stock-option short follow-up gap above. Fifth delivery is pending:
commit, push to `main`, GitHub
Actions/deploy monitoring, production marker/smoke, live order/quote E2E retry,
and synthetic data cleanup.

Final delivery commit `ec8dd61` reached production via CI run `27622142673`.
Production marker matched
`ec8dd612dfb0a44eb41104bd198a5936f91c847d`, `/api/v1/health` returned OK,
and `uv run python scripts/verify_api.py --base-url https://noor.starec.ai`
passed 8/0.

Final live E2E run `20260616134948` passed:

- name-gate resume and repeated bare `2` after SKU option prompt:
  conversation `762e0847-7081-4e46-9df6-e6fa2bb08381`, route
  `selection-confirmation`, `CH 616 black`, quantity 2.
- exact-quote SKU repair plus quote-detail resume:
  conversation `e3b0bded-d293-4abc-8812-3a0964eaf10e`, routes
  `exact-quote-clarify-item`, `quote-resume-missing-details`, `quote-resume`,
  quotation `Fr3415`.
- SKU variant all-details quote:
  conversation `d3f121a2-dfba-413a-b33a-a0dc8a74c9ee`, route
  `exact-quote-deterministic`, quotation `Fr3416`.
- all-details first turn:
  conversation `559f649f-4a4f-46a2-9404-fffa460fc743`, route
  `exact-quote-deterministic`, quotation `Fr3417`.
- pending quantity/reference path:
  conversation `c12cbddf-6307-4245-aad1-056ca2610005`, quantity prompt from
  `dialogue-kernel|product_selection`, follow-up `2` returned
  `selection-confirmation`, `CH 140 black`, quantity 2.
- short follow-up after long context:
  conversation `e0f59d01-ae03-4458-a00e-9bb2c4c0126c`, first route
  `stock-price-options`, follow-up `Yes prepare the quotation` returned
  `quote-resume`, quotation `Fr3418`.

Production synthetic cleanup completed after E2E:

- PostgreSQL deleted 22 synthetic conversations, 92 messages, 46 outbound
  audits, 119 customer facts, 22 order memories, 22 customer profiles, and 1
  escalation for phones matching `%tj-route-adapter%` or `+70016416123436`.
- Redis deleted 37 scoped keys matching the same synthetic markers.
- Post-cleanup verification returned 0 matching conversations, customer
  profiles, joined messages, and Redis keys.

## Explicit Defers

- None for `tj-order-cutover.10` acceptance after local verification.
- GitHub issue #42 second-occurrence production evidence comment remains
  externally visible and was not separately authorized; no GitHub issue comment
  was added.
