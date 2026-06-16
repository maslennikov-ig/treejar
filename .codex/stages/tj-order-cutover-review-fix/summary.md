# Stage tj-order-cutover-review-fix: Order/Quote Cutover Review And Fix

Updated: 2026-06-16
Status: delivered to main, deployed, smoke-tested, E2E-tested, and cleaned up
Branch: `codex/tj-order-cutover-review-fix`
Worktree: `/home/me/code/treejar/.worktrees/tj-order-cutover-review-fix`
Beads: `tj-s1qi`, `tj-1ha9`, `tj-hqsa`, `tj-v2k9` are closed;
`tj-order-cutover.10` remains open only for the broader P2 extraction.

docs-reviewed: no-change-needed - fixes tighten existing documented runtime
ownership, make bounded diagnostics functional, harden webhook batch handling,
and update a frontend lockfile; no public API, operator workflow, deployment
contract, or durable doc contract changed. Handoff and stage docs were updated
with delivery/E2E evidence.
graph-reviewed: no-change-needed - Graphify is not configured in this worktree;
no `graphify-out/GRAPH_REPORT.md` exists.
project-index: reviewed-no-change - no stable entrypoints, routes, directories,
integrations, or verification commands changed.

## Goal

Independently review the order/quote cutover on `origin/main`, verify the
#40-#52 class behavior, fix accepted in-scope risks, and leave explicit tracked
follow-ups for larger improvements.

## Review Streams

- `correctness_reviewer` (`019ecf88-1b15-7430-85c8-136c6e7d5377`) found one
  must-fix quantity-side legacy leak and one trace observability improvement.
- `improvement_reviewer` (`019ecf88-6d11-7742-a5a4-6a0dd16b6041`) found one
  must-fix quote-side invalid canonical frame leak and several high-value
  improvements.
- `architect_reviewer` (`019ecf88-bbb1-7a51-9ae1-c4790514dc3f`) returned
  Conditional Pass and confirmed the route-selection extraction follow-up.
- Local orchestrator review verified GitHub issue evidence, commit stats, code,
  docs, and target tests.

## Accepted Findings Fixed

- Fixed quote-side legacy leakage when `order_runtime.quote_frame` exists but is
  invalid or has no valid lines. Canonical frame presence now prevents fallback
  to stale legacy `pending_quote_selection`; active quote helpers also block
  caller-supplied legacy selection in that state.
- Fixed quantity-side legacy leakage when a non-answerable typed
  `pending_question_frame` coexists with stale
  `pending_product_reference_quantity`. The legacy key is cleared and suppressed
  for that turn instead of reviving an expired product reference.
- Fixed `legacy_migration_read` trace observability. Runtime load now sets the
  bounded boolean when legacy quote/customer metadata is read.
- Added typed ownership for unresolved-only quote repair. Canonical
  `order_runtime.quote_frame` now remains active for valid unresolved repair
  items, so legacy `pending_quote_selection` is a compatibility mirror rather
  than the only source of truth.
- Extracted pending quantity/reference route selection from `process_message`
  into `_pending_reference_route_for_turn`, with a structural regression test
  preventing the low-level stale legacy helpers from moving back into
  `process_message`.
- Added deterministic bounded quote frame IDs and non-PII bounded
  `order_runtime.quote_effect_traces` for quote side-effect attempts/results.
- Resolved the frontend admin audit findings by updating the package lock to
  Vite `8.0.16` / esbuild `0.28.1`. `npm audit` now reports zero
  vulnerabilities. The package engine remains `>=22.12.0 <23`; the local
  Node `24.16.0` warning is an environment mismatch, not a policy change.
- Hardened inbound webhook batch completion when the generated bot reply cannot
  be sent through Wazzup. The failed outbound send is logged and audited, but
  the inbound batch remains successful so the worker does not retry stale
  context indefinitely.
- Added deterministic extraction for `Customer:` / `Customer name:` labels, so
  first-turn quote requests with customer details no longer fall back to the
  name gate solely because the label wording differs from `my name is`.

## Rejected Or Deferred Findings

- No rejected material findings.
- `tj-order-cutover.10` remains intentionally deferred for the full
  behavior-preserving extraction of the remaining deterministic route families
  from `process_message`: sales-order quote extraction/resume, exact quote SKU
  repair, selection confirmation, and quote-detail resume. This branch only
  lands the lower-risk pending quantity/reference extraction slice.

## GitHub Evidence

- Direct `gh issue view 40..52` showed #40-#52 closed.
- #49-#52 have production evidence comments for deployed SHA `4bcab4d`, CI/deploy
  run `27535297609`, production smoke, and live WhatsApp E2E.
- #42 contains a later "Second occurrence" comment after its original close; the
  local code and stage evidence cover the `SK 45 White -> 2` regression, but the
  issue itself does not have a separate production evidence comment for that
  second occurrence. No GitHub comment was added in this local pass.
- `gh pr list --search "order quote cutover"` returned no matching PR rows; the
  prior delivery appears to have been direct-to-main per stage evidence.

## Verification

- RED:
  - `PYTHONDONTWRITEBYTECODE=1 PYTEST_ADDOPTS="-p no:cacheprovider" OPENROUTER_API_KEY=test uv run pytest tests/test_llm_engine.py::test_canonical_quote_frame_presence_blocks_invalid_frame_legacy_leak -q`
    failed before the quote leak fix because stale `STALE-SKU` legacy metadata
    was returned.
  - `PYTHONDONTWRITEBYTECODE=1 PYTEST_ADDOPTS="-p no:cacheprovider" OPENROUTER_API_KEY=test uv run pytest tests/test_llm_engine.py::test_process_message_expired_quantity_frame_blocks_legacy_pending_reference -q`
    failed before the quantity leak fix with `mock-model|selection-confirmation`.
  - `PYTHONDONTWRITEBYTECODE=1 PYTEST_ADDOPTS="-p no:cacheprovider" OPENROUTER_API_KEY=test uv run pytest tests/test_dialogue_order_runtime.py::test_order_runtime_trace_records_legacy_migration_read -q`
    failed before the trace fix because the flag stayed false.
- GREEN:
  - `PYTHONDONTWRITEBYTECODE=1 PYTEST_ADDOPTS="-p no:cacheprovider" OPENROUTER_API_KEY=test uv run pytest tests/test_llm_engine.py::test_canonical_quote_frame_presence_blocks_invalid_frame_legacy_leak -q`
    -> 1 passed.
  - `PYTHONDONTWRITEBYTECODE=1 PYTEST_ADDOPTS="-p no:cacheprovider" OPENROUTER_API_KEY=test uv run pytest tests/test_llm_engine.py::test_process_message_expired_quantity_frame_blocks_legacy_pending_reference -q`
    -> 1 passed.
  - `PYTHONDONTWRITEBYTECODE=1 PYTEST_ADDOPTS="-p no:cacheprovider" OPENROUTER_API_KEY=test uv run pytest tests/test_dialogue_order_runtime.py::test_order_runtime_trace_records_legacy_migration_read -q`
    -> 1 passed.
  - `PYTHONDONTWRITEBYTECODE=1 PYTEST_ADDOPTS="-p no:cacheprovider" OPENROUTER_API_KEY=test uv run pytest tests/test_llm_engine.py -k "canonical_quote_frame or quoted_quote_frame or quote_details_do_not_recover_items_from_assistant_prose or quote_details_after_bullet_summary_requires_saved_quote_frame or quote_frame_blocks" -q`
    -> 9 passed.
  - `PYTHONDONTWRITEBYTECODE=1 PYTEST_ADDOPTS="-p no:cacheprovider" OPENROUTER_API_KEY=test uv run pytest tests/test_llm_engine.py -k "pending_quantity or pending_question_frame or product_quantity_clarify or order_cutover_gh42 or gh52_customer_details" -q`
    -> 6 passed.
  - `PYTHONDONTWRITEBYTECODE=1 PYTEST_ADDOPTS="-p no:cacheprovider" OPENROUTER_API_KEY=test uv run pytest tests/test_dialogue_order_runtime.py -q`
    -> 15 passed.
  - `PYTHONDONTWRITEBYTECODE=1 PYTEST_ADDOPTS="-p no:cacheprovider" OPENROUTER_API_KEY=test uv run pytest tests/test_dialogue_order_runtime.py tests/test_llm_engine.py -q`
    -> 330 passed.
  - `OPENROUTER_API_KEY=test uv run ruff check src/ tests/` -> passed.
  - `OPENROUTER_API_KEY=test uv run ruff format --check src/ tests/` ->
    293 files already formatted.
  - `OPENROUTER_API_KEY=test uv run mypy src/` -> passed, no issues in 157
    source files.
  - First stage-closeout attempt failed because the fresh worktree lacked
    `frontend/admin/node_modules` and Node could not import `esbuild`.
  - `npm ci` in `frontend/admin` completed, with an existing engine warning
    because local Node is `v24.16.0` while the package declares `>=22.12.0 <23`;
    npm also reported 2 high severity audit findings.
  - `scripts/orchestration/run_stage_closeout.py --stage tj-order-cutover-review-fix`
    reran the canonical gates through full pytest after `npm ci`; full pytest
    passed: 1399 passed, 19 skipped.
  - Final `scripts/orchestration/run_stage_closeout.py --stage tj-order-cutover-review-fix`
    passed: artifact validation OK, process verification OK, stage closeout
    verification OK.
- Follow-up hardening RED/GREEN:
  - `OPENROUTER_API_KEY=dummy uv run pytest tests/test_llm_engine.py::test_process_message_exact_quote_unresolved_item_clarifies_without_escalation tests/test_llm_engine.py::test_process_message_unresolved_only_canonical_quote_frame_resumes_without_legacy tests/test_llm_engine.py::test_process_message_sales_order_request_creates_multi_item_quotation -v --tb=short`
    failed before the hardening because unresolved-only repair had no canonical
    frame, canonical-only repair did not resume, and quote side-effect traces
    were absent.
  - `OPENROUTER_API_KEY=dummy uv run pytest tests/test_llm_engine.py::test_process_message_pending_reference_route_is_adapter_owned tests/test_llm_engine.py::test_process_message_exact_quote_unresolved_item_clarifies_without_escalation tests/test_llm_engine.py::test_process_message_unresolved_only_canonical_quote_frame_resumes_without_legacy tests/test_llm_engine.py::test_process_message_sales_order_request_creates_multi_item_quotation tests/test_llm_engine.py::test_process_message_selection_unresolved_followup_resumes_from_canonical_quote_frame tests/test_llm_engine.py::test_process_message_exact_quote_unresolved_followup_resolves_sku_and_quantity tests/test_llm_engine.py::test_process_message_sales_order_unresolved_followup_resumes_quote tests/test_llm_engine.py::test_process_message_sales_order_resolved_followup_then_brief_creates_quote -v --tb=short`
    -> 8 passed.
  - `PYTHONDONTWRITEBYTECODE=1 PYTEST_ADDOPTS="-p no:cacheprovider" OPENROUTER_API_KEY=test uv run pytest tests/test_dialogue_order_runtime.py tests/test_llm_engine.py -q`
    -> 332 passed.
  - `OPENROUTER_API_KEY=test uv run ruff check src/ tests/` -> passed.
  - `OPENROUTER_API_KEY=test uv run mypy src/` -> passed, no issues in 157
    source files.
  - `npm audit --json` in `frontend/admin` -> 0 vulnerabilities.
  - `npm run lint` in `frontend/admin` -> passed.
  - `npm run build` in `frontend/admin` -> passed.
- Delivery retest RED/GREEN:
  - `uv run pytest tests/test_services_chat_batch.py::test_process_incoming_batch_keeps_batch_successful_when_bot_reply_send_fails -q`
    failed before the chat fix because the Wazzup send failure raised
    `RuntimeError` and failed the inbound batch; after the fix it passed.
  - `uv run pytest tests/test_fact_extractor.py::test_deterministic_extracts_customer_label_as_name -q`
    failed before the extractor fix because `Customer: Amina Complete` produced
    no `customer.name`; after the fix it passed.
  - `uv run pytest tests/test_services_chat_batch.py tests/test_outbound_audit.py -q`
    -> 28 passed.
  - `uv run pytest tests/test_fact_extractor.py -q` -> 33 passed.
  - Related engine regressions for first-turn details and quote name-gate resume
    -> 3 passed.
  - Final local full gates after `16a2dfe`: `ruff check`, `ruff format --check`,
    `mypy src/`, and `pytest tests/ -q` -> 1412 passed, 19 skipped.
- CI/deploy/prod verification:
  - GitHub Actions run `27613068608` deployed `03cd075` and passed changes,
    lint, test, type-check, and deploy jobs.
  - GitHub Actions run `27614021694` deployed `16a2dfe` and passed changes,
    lint, test, type-check, and deploy jobs.
  - Production marker after final runtime deploy:
    `.release-sha=16a2dfe8de30b79a81cb53f73279c629eaa70499` and
    `.release-run-id=27614021694`.
  - Production health passed and `uv run python scripts/verify_api.py --base-url https://noor.starec.ai`
    reported 8 passed, 0 failed.
- Live synthetic E2E:
  - Matrix run `0616112830` passed name-gate quote resume, variant quote resume,
    and customer-label first-turn quote scenarios without context loss.
  - Strict all-details first-turn run for `+70016416113202` passed with
    `z-ai/glm-5|exact-quote-deterministic`, manager verification, no name gate,
    and no item clarification.
  - Synthetic PostgreSQL and Redis test data was cleaned after the run; exact
    target conversation count was zero.

## Changed Files

- `frontend/admin/package-lock.json`
- `src/dialogue/order_state.py`
- `src/dialogue/order_runtime.py`
- `src/llm/engine.py`
- `src/llm/fact_extractor.py`
- `src/services/chat.py`
- `tests/test_dialogue_order_runtime.py`
- `tests/test_fact_extractor.py`
- `tests/test_llm_engine.py`
- `tests/test_services_chat_batch.py`
- `.codex/handoff.md`
- `.codex/stages/tj-order-cutover-review-fix/summary.md`
- `.codex/stages/tj-order-cutover-review-fix/artifacts/tj-s1qi.md`
- `.codex/stages/tj-order-cutover-review-fix/artifacts/review-correctness.md`
- `.codex/stages/tj-order-cutover-review-fix/artifacts/review-improvement.md`
- `.codex/stages/tj-order-cutover-review-fix/artifacts/review-architecture.md`

## Delivery

Delivery was explicitly approved by the user and completed through direct push
to `main`. Runtime commits `03cd075` and `16a2dfe` were deployed by GitHub
Actions; final production readback showed release SHA
`16a2dfe8de30b79a81cb53f73279c629eaa70499`. Production smoke and the approved
live synthetic E2E matrix passed after deploy. The final docs/Beads closeout
commit is docs-only and does not change runtime behavior.

## Explicit Defers

- The #42 second-occurrence GitHub issue comment lacks a matching production
  evidence response; updating GitHub is externally visible and was not done.
- `tj-order-cutover.10`: full route-selection extraction from `process_message`
  remains a P2 architecture follow-up; only the pending quantity/reference slice
  is included in this delivery branch.
