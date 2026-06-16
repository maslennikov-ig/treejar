# Stage tj-order-adapter-hardening: Order/Quote Side-Effect Adapter

Updated: 2026-06-16
Status: pushed to `main`; deployed to production; production smoke passed
Branch: `codex/tj-order-sideeffect-adapter`
Worktree: `/home/me/code/treejar/.worktrees/tj-order-sideeffect-adapter`
Beads: `tj-order-cutover.5`; follow-up `tj-order-cutover.10`

docs-reviewed: no-change-needed - this is an internal refactor of deterministic
quote side-effect ownership; no customer-facing behavior, API contract,
operator workflow, or durable state contract changed.
graph-reviewed: no-change-needed - Graphify is not configured in this worktree;
no `graphify-out/GRAPH_REPORT.md` exists.
project-index: reviewed-no-change - no stable entrypoints, routes, directories,
integrations, or verification commands changed.

## Goal

Close the P0 hardening defer by ensuring deterministic order/quote quotation
side effects are executed through one adapter instead of direct
`process_message` calls to `create_quotation`.

## Implemented

- Added `OrderQuoteSideEffectPlan` and `_execute_order_quote_side_effect`.
- Routed deterministic sales-order quote, sales-order resume, exact quote,
  exact quote repair resume, and normal quote resume creation through the
  adapter.
- Preserved the existing `create_quotation` tool for the Zoho/PDF/WhatsApp
  side effect implementation.
- Added `test_order_quote_create_quotation_calls_are_adapter_owned`, an AST
  regression proving `create_quotation(...)` is called only inside the adapter.
- Split the broader behavior-preserving extraction of remaining
  `process_message` route-selection branches into Beads task
  `tj-order-cutover.10`.

## Verification

- RED:
  - `OPENROUTER_API_KEY=test uv run pytest tests/test_llm_engine.py::test_order_quote_create_quotation_calls_are_adapter_owned -q`
    failed before implementation because direct call owners were
    `process_message`.
- GREEN:
  - `OPENROUTER_API_KEY=test uv run pytest tests/test_llm_engine.py::test_order_quote_create_quotation_calls_are_adapter_owned -q`
    -> 1 passed.
  - `OPENROUTER_API_KEY=test uv run pytest tests/test_llm_engine.py -k "order_quote_create_quotation_calls_are_adapter_owned or sales_order_request_creates_multi_item_quotation or sales_order_unresolved_followup_resumes_quote or sales_order_resolved_followup_then_brief_creates_quote or exact_quote_unresolved_followup_resolves_sku_and_quantity or order_cutover_gh52_customer_details_resume_after_point_selection_confirmation or order_cutover_quote_details_resume_creates_quote_from_canonical_frame" -q`
    -> 6 passed.
  - `OPENROUTER_API_KEY=test uv run pytest tests/test_dialogue_order_runtime.py tests/test_llm_engine.py -q`
    -> 327 passed.
  - `OPENROUTER_API_KEY=test uv run ruff check src/ tests/` -> passed.
  - `OPENROUTER_API_KEY=test uv run ruff format --check src/ tests/` ->
    293 files already formatted.
  - `OPENROUTER_API_KEY=test uv run mypy src/` -> passed, no issues in 157
    source files.
  - `OPENROUTER_API_KEY=test env DYLD_FALLBACK_LIBRARY_PATH="${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}" uv run pytest tests/ -v --tb=short`
    -> 1396 passed, 19 skipped.

## Delivery

- Commit: `8bce80194cd3640d30a8a5c25e66cc85c3eeadff`.
- Pushed to `origin/main`.
- Push-triggered GitHub Actions run `27602099718` passed changes, lint, test,
  type-check, and deploy.
- Deploy job: `81605605844`.
- A duplicate manual workflow_dispatch run `27602134953` was cancelled before
  delivery to avoid double-deploying the same SHA.
- Production API smoke passed:
  `OPENROUTER_API_KEY=test uv run python scripts/verify_api.py --base-url https://noor.starec.ai`
  -> 8 passed, 0 failed.
- Local SSH alias `noor` did not resolve in this environment, so release marker
  readback could not be repeated locally; CI deploy evidence plus public smoke
  are the delivery evidence for this stage.

## Explicit Defers

- `tj-order-cutover.10`: extract the remaining deterministic order/quote
  route-selection branches from `process_message` into a dedicated adapter in a
  separate behavior-preserving refactor.
- `tj-gh21` waits for approved Wazzup WABA templates.
