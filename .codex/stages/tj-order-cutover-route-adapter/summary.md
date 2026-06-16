# Stage tj-order-cutover-route-adapter: Order/Quote Route Adapter Extraction

Updated: 2026-06-16
Status: stage-closeout passed, delivery pending
Branch: `codex/tj-order-route-adapter`
Worktree: `/home/me/code/treejar/.worktrees/tj-order-route-adapter`
Beads: `tj-order-cutover.10` closed

docs-reviewed: no-change-needed - refactor preserves documented customer-facing
runtime ownership; the live-E2E bare ordinal repair is internal route parsing
for an already asked SKU option question; no public API, operator workflow,
deployment contract, integration contract, or durable doc contract changed.
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
- Stage closeout:
  - `scripts/orchestration/run_stage_closeout.py --stage tj-order-cutover-route-adapter`
    passed: artifact validation OK, process verification OK, project-index/docs
    review OK, debt marker scan OK, full code-change verification OK, and stage
    closeout verification OK.
  - Post-bare-ordinal-fix closeout passed again with the same stage command.

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
the quantity-preservation gap above. Third delivery is pending: commit, push to
`main`, GitHub Actions/deploy monitoring, production marker/smoke, live
order/quote E2E retry, and synthetic data cleanup.

## Explicit Defers

- None for `tj-order-cutover.10` acceptance after local verification.
- GitHub issue #42 second-occurrence production evidence comment remains
  externally visible and was not separately authorized; no GitHub issue comment
  was added.
