# Stage tj-order-cutover: Full Order/Quote Flow Cutover

Updated: 2026-06-09
Status: local implementation verified; deploy/live E2E deferred pending explicit
approval
Branch: `codex/tj-order-flow-cutover-plan`
Worktree: `/home/me/code/treejar/.worktrees/tj-gh51-order-quote-cutover`
Beads: `tj-order-cutover`

docs-reviewed: updated - `docs/specs/dialogue-state-kernel.md` now documents
`order_runtime.pending_question_frame`, lifecycle, snapshot preservation, trace
fields, and the no-assistant-prose quote recovery rule.
graph-reviewed: no-change-needed - Graphify is not configured in this worktree;
no `graphify-out/GRAPH_REPORT.md` exists.

## Goal

Finish the local order/quote cutover so #40-#51 class regressions cannot return
through legacy metadata, recent-history-only matching, or assistant-prose quote
recovery. Live WhatsApp E2E, deploy, push, and production mutations remain
blocked without explicit approval.

## Implemented

- Added canonical `order_runtime.pending_question_frame` with source refs,
  order-line snapshot, lifecycle status, `turns_seen`, optional expiry, and
  bounded trace fields.
- Routed missing quantity prompts and bare quantity answers through typed
  runtime state, including the second #42 occurrence:
  `SK 45 White` -> quantity prompt -> `2`.
- Preserved mixed complete + missing order lines across quantity clarification
  turns so #50-style multi-item selections do not lose already resolved lines.
- Added deterministic frame aging: non-answer turns increment `turns_seen`, and
  exhausted or expired frames cannot consume later bare numbers.
- Stopped new writes to `pending_product_reference_quantity` on quantity-frame
  paths; new paths persist typed runtime metadata first.
- Disabled assistant-prose quote item recovery. When customer quote details
  arrive without a saved quote frame, the bot now asks for product/quantity
  confirmation instead of resolving SKUs or creating a quotation from assistant
  text.
- Added bounded order-runtime trace persistence for `frame_id`, `frame_status`,
  resolved/unresolved line counts, and legacy migration read status.
- Updated customer facts documentation so facts/memory consume typed runtime
  snapshots rather than model/prose item facts.

## Review Gate

- `code_mapper` and `qa_expert` mapped the order/quote conflict zones and replay
  risks before implementation.
- `correctness_reviewer` found two must-fix issues:
  mixed complete + missing quantity line loss, and stale typed quantity frames.
  Both were fixed and covered by tests.
- `improvement_reviewer` found no blocking improvement findings. Accepted
  improvements fixed in this stage: trace fields are persisted, frame lifecycle
  is enforced, and snapshot context reduces pending-quantity ownership drift.

## Verification

- RED replay checks were run before implementation:
  - `tests/test_dialogue_order_runtime.py -k "typed_quantity_frame or bare_quantity_consumes_typed_frame"` failed on missing typed frames.
  - `tests/test_llm_engine.py -k "order_cutover_gh42_second_occurrence or order_cutover_quote_details_do_not_recover_items_from_assistant_prose"` failed on generic opener / assistant-prose quote recovery.
  - review RED checks later failed for mixed complete+missing line loss and
    non-aging quantity frames.
- GREEN verification:
  - `OPENROUTER_API_KEY=test uv run pytest tests/test_dialogue_order_runtime.py -q` -> 13 passed.
  - `OPENROUTER_API_KEY=test uv run pytest tests/test_llm_engine.py -k "order_cutover or quote_resume or exact_quote or product_quantity_clarify or pending_quantity or quote_request_with_multiple_items or selection_unresolved_followup or gh49 or gh50 or gh51" -q` -> 51 passed.
  - `OPENROUTER_API_KEY=test uv run pytest tests/test_dialogue_order_state.py tests/test_fact_extractor.py tests/test_customer_memory_service.py tests/test_dialogue_state.py -q` -> 65 passed.
  - `OPENROUTER_API_KEY=test uv run ruff check src/ tests/` -> passed.
  - `OPENROUTER_API_KEY=test uv run ruff format --check src/ tests/` -> 293 files already formatted.
  - `OPENROUTER_API_KEY=test uv run mypy src/` -> passed.
  - `OPENROUTER_API_KEY=test env DYLD_FALLBACK_LIBRARY_PATH="${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}" uv run pytest tests/ -v --tb=short` -> 1382 passed, 19 skipped.

## Explicit Defers

- No deploy, push, production mutation, or live WhatsApp E2E was run.
- Full architectural removal of every remaining order/quote-specific branch in
  `src/llm/engine.py` remains a follow-up hardening task. The implemented stage
  blocks the requested regression class with typed metadata, replay coverage,
  and quote-prose recovery removal.
- `tj-gh21` remains blocked on approved Wazzup WABA EN/AR templates.
