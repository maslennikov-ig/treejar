# Stage tj-order-cutover: Full Order/Quote Flow Cutover

Updated: 2026-06-15
Status: delivered to production; live E2E passed; GitHub #49-#52 closed
Branch: `codex/tj-order-cutover-rework`
Worktree: `/home/me/code/treejar/.worktrees/tj-order-cutover-rework`
Beads: `tj-order-cutover`

docs-reviewed: updated - `docs/specs/dialogue-state-kernel.md` now documents
`order_runtime.pending_question_frame`, lifecycle, snapshot preservation, trace
fields, the no-assistant-prose quote recovery rule, and #52 `point(s)` quantity
parsing / durable quote-frame resume behavior.
graph-reviewed: no-change-needed - Graphify is not configured in this worktree;
no `graphify-out/GRAPH_REPORT.md` exists.

## Goal

Finish the local order/quote cutover so #40-#52 class regressions cannot return
through legacy metadata, recent-history-only matching, assistant-prose quote
recovery, or commercial-policy phrases misread as order quantities.

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
- Added #52 rework on top of `origin/main` `d0b5dda`: `point` and `points` are
  accepted as explicit trailing unit-count words for `CH 615 NEW black 6 point`
  style phrases, while `NEW` is no longer misread as an alpha SKU prefix.
- Preserved deterministic quote-frame creation for bot-owned selection
  confirmations before quote details are requested. The #52 replay now stores
  `order_runtime.quote_frame` on the confirmation turn, so compact customer
  details resume the frame and ask only for missing quote fields instead of
  hitting the saved-frame repair branch.
- Added compact slash-labeled quote-detail extraction for replies such as
  `Name company GHP / Address - 2 street / +79137704837`.
- Added bounded order-runtime trace persistence for `frame_id`, `frame_status`,
  resolved/unresolved line counts, and legacy migration read status.
- Updated customer facts documentation so facts/memory consume typed runtime
  snapshots rather than model/prose item facts.
- Added a production hotfix for commercial blockers: discount/payment terms are
  blocked from deterministic order selection, classified as high-risk service
  policy before product routing, and same-turn name capture no longer prevents
  verified-policy handoff. Normal low-risk showroom questions still use the
  static showroom answer.

## Delivery

- Rework commit `28453cf4ffd12de9605428b72d99f34082917c4e` deployed in CI run
  `27533938721`.
- Hotfix commit `4bcab4d1d9e91a7cfcc69ff940acec68ac54b913` deployed in CI run
  `27535297609`; deploy job `81383375571`.
- Production release marker read back from `/opt/noor` reads
  `.release-sha=4bcab4d1d9e91a7cfcc69ff940acec68ac54b913` and
  `.release-run-id=27535297609`. Public `/.release-sha` and
  `/.release-run-id` return `404`, so the canonical proof path is SSH
  readback plus API smoke.
- Production API smoke passed:
  `uv run python scripts/verify_api.py --base-url https://noor.starec.ai` ->
  8 passed, 0 failed.
- GitHub issues #49, #50, #51, and #52 were closed with production evidence
  comments.

## Live WhatsApp E2E

- #52 parse/stock path:
  `+79262810921#tj-order-cutover-gh52-20260615T083802Z` parsed
  `CH 615 NEW black 6 point` as qty 6, resolved CH 615 black, and hit a real
  stock-shortage path instead of an item/quantity loop.
- #52 quote resume:
  `+79262810921#tj-order-cutover-gh52quote-20260615T083802Z` resolved
  `CH 615 NEW black 1 point` as qty 1, then compact details
  `Name company GHP / Address - 2 street / +79137704837` resumed
  `order_runtime.quote_frame.status=collecting_details` and asked only for the
  missing email.
- #42 original phrase:
  `+79262810921#tj-order-cutover-gh42-20260615T083802Z` returned catalog
  options because production has two live SK 45 white products; no quantity
  clarification loop occurred.
- #42 production-valid equivalent:
  `+79262810921#tj-order-cutover-gh42exact-20260615T083802Z` asked for quantity
  for SK 45 white, consumed bare `2`, and stayed in selection confirmation
  rather than a generic opener.
- #49/#50/#51 combined flow:
  `+79262810921#tj-order-cutover-gh50-20260615T083802Z` preserved
  `2 x SKYLAND NOVO 2400 Meeting Table` plus unresolved `4 x CH 616 chairs`,
  accepted `CH 616 NEW black`, collected details, and created quotation
  `Fr3389`. DB readback shows `order_runtime.quote_frame.status=quoted`, two
  quote lines, details `Lilia / GHP / live-order-cutover@example.com /
  2 street Dubai`, and no consecutive duplicate assistant replies.
- Commercial blocker hotfix:
  `+79262810921#tj-order-cutover-blocker2-20260615T090126Z` returned
  `z-ai/glm-5|verified-policy` with `escalation_status=pending` for
  `20 percent discount and net 30 payment terms`; no bogus `20 x` selection.

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
  - 2026-06-15 #52 RED: `test_order_runtime_accepts_point_as_trailing_unit_count`
    failed with `quantity_clarification`; `CH 615 NEW black 6 point(s)` engine
    parser cases returned `None`; and the process replay returned
    `product-quantity-clarify` instead of `selection-confirmation`.
- GREEN verification:
  - `OPENROUTER_API_KEY=test uv run pytest tests/test_dialogue_order_runtime.py::test_order_runtime_accepts_point_as_trailing_unit_count tests/test_llm_engine.py::test_extract_purchase_selection_accepts_position_quantity_phrases tests/test_llm_engine.py::test_order_cutover_gh52_customer_details_resume_after_point_selection_confirmation -q` -> 8 passed.
  - `OPENROUTER_API_KEY=test uv run pytest tests/test_dialogue_order_runtime.py tests/test_llm_engine.py -q` -> 325 passed.
  - `OPENROUTER_API_KEY=test uv run pytest tests/test_dialogue_order_runtime.py -q` -> 13 passed.
  - `OPENROUTER_API_KEY=test uv run pytest tests/test_llm_engine.py -k "order_cutover or quote_resume or exact_quote or product_quantity_clarify or pending_quantity or quote_request_with_multiple_items or selection_unresolved_followup or gh49 or gh50 or gh51" -q` -> 51 passed.
  - `OPENROUTER_API_KEY=test uv run pytest tests/test_dialogue_order_state.py tests/test_fact_extractor.py tests/test_customer_memory_service.py tests/test_dialogue_state.py -q` -> 65 passed.
  - `OPENROUTER_API_KEY=test uv run ruff check src/ tests/` -> passed.
  - `OPENROUTER_API_KEY=test uv run ruff format --check src/ tests/` -> 293 files already formatted.
  - `OPENROUTER_API_KEY=test uv run mypy src/` -> passed: no issues in 157 source files.
  - First full pytest attempt failed because the fresh worktree lacked
    `frontend/admin/node_modules` and Node could not import `esbuild`.
    After local `npm ci` in `frontend/admin`, the canonical full test command
    passed.
  - `OPENROUTER_API_KEY=test env DYLD_FALLBACK_LIBRARY_PATH="${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}" uv run pytest tests/ -v --tb=short` -> 1394 passed, 19 skipped.
  - Hotfix RED/GREEN:
    `tests/test_llm_engine.py::test_process_message_payment_terms_percent_words_do_not_become_order_selection`
    first failed before the fix, then passed.
  - Hotfix targeted regression:
    `OPENROUTER_API_KEY=test uv run pytest tests/test_llm_engine.py::test_process_message_payment_terms_still_use_manager_handoff tests/test_llm_engine.py::test_process_message_payment_terms_percent_words_do_not_become_order_selection tests/test_llm_engine.py::test_process_message_name_only_reply_after_name_gate_does_not_escalate tests/test_llm_engine.py::test_process_message_missing_low_risk_hands_off_without_agent_run tests/test_llm_engine.py::test_process_message_first_turn_service_handoff_gets_opening -q` -> 5 passed.
  - Hotfix classifier regression:
    `OPENROUTER_API_KEY=test uv run pytest tests/test_verified_answers.py -k "payment_terms or discount or showroom or office" -q` -> 6 passed.
  - Hotfix rework regression:
    `OPENROUTER_API_KEY=test uv run pytest tests/test_llm_engine.py -k "payment_terms or verified_policy or order_cutover or quote_resume or gh49 or gh50 or gh51" -q` -> 9 passed.
  - Final local gates after hotfix:
    `OPENROUTER_API_KEY=test uv run ruff check src/ tests/` -> passed;
    `OPENROUTER_API_KEY=test uv run ruff format --check src/ tests/` ->
    293 files already formatted;
    `OPENROUTER_API_KEY=test uv run mypy src/` -> passed;
    `OPENROUTER_API_KEY=test env DYLD_FALLBACK_LIBRARY_PATH="${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}" uv run pytest tests/ -v --tb=short` ->
    1395 passed, 19 skipped.
  - GitHub Actions run `27535297609` passed: changes, lint, test,
    type-check, deploy.

## Explicit Defers

- The P0 side-effect adapter hardening was delivered in follow-up stage
  `tj-order-adapter-hardening` (`8bce801`). Remaining behavior-preserving route
  selection extraction from `process_message` is tracked as
  `tj-order-cutover.10`.
- `tj-gh21` remains blocked on approved Wazzup WABA EN/AR templates.
