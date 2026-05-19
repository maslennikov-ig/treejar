# Stage tj-gh18: Open Issues SKU Selection and Media Caption Hardening

Updated: 2026-05-19
Status: delivered, deployed, live E2E verified, and GitHub #39/#35 closed
Branch: `codex/tj-gh18-open-issues-hardening`
Base: `origin/main@20bad53c2292`
GitHub issues: `gh-39`, `gh-35`
Beads: `tj-gh18`, `tj-gh18.1`, `tj-gh18.2`, `tj-gh18.3`

## Scope

- `tj-gh18.1` / #39: a customer selecting `I need 6 CH 616` after the bot
  offered `CH 616` must stay on product/quote selection and must not trigger
  verified-policy manager handoff.
- `tj-gh18.2` / #35: deferred product media must be sent without a
  customer-visible caption or separate caption text, while retaining hidden
  caption audit context for product-selection matching.
- `tj-gh18.3`: merge/deploy/live E2E/GitHub closure.
- GitHub #11 is excluded until Lilia answers the already-posted clarification
  questions.

## Parallel Decomposition Matrix

| Stream | Goal | Agent | Write zone | Verification | Decision | Reason |
| --- | --- | --- | --- | --- | --- | --- |
| A `tj-gh18.1` | Fix SKU/product selection for `CH 616` variants | Codex worker, high reasoning | `src/llm/engine.py`, `src/llm/verified_answers.py`, `src/llm/prompts.py`, LLM tests | LLM engine and verified-answer tests | parallel | Central LLM routing risk justified high reasoning, but write zone did not overlap media send tests. |
| B `tj-gh18.2` | Verify/fix media caption behavior | Codex worker, medium reasoning | `tests/test_services_chat_batch.py`, `tests/test_outbound_audit.py`, Wazzup tests | chat batch, outbound audit, Wazzup tests | parallel | Send-layer/customer-visible assertions were independent from SKU parser changes. |
| Orchestrator | Review and integrate both streams | local | shared branch and orchestration artifacts | targeted suite, full gates, process/stage closeout | sequential | Required detailed review of worker output and final conflict-free integration. |

## Implemented

- Extended deterministic purchase selection parsing for:
  - intent phrases: `need`, `want`, `would like`, `like`, existing order/buy terms;
  - SKU forms: `CH 616`, `CH-616`, `CH616`, numeric-hyphen and dotted/alphanumeric forms;
  - bare `quantity + SKU` only when the last assistant turn was a product choice prompt.
- Added SKU lookup variants for raw, hyphenated, spaced, and compact forms before
  catalog lookup, with deterministic priority in one SQL query.
- Kept exact named models such as `SKYLAND NOVO 2400` out of generic SKU
  selection parsing so the bot treats them as selected models, not as chair SKUs.
- Updated verified-answer classification so generic SKU plus quantity is
  `product/allow`, not `service_low_risk/handoff`.
- Added a prompt rule: when the customer already named an exact model/SKU, the
  agent clarifies only still-generic items.
- Strengthened media tests to prove deferred product media sends with
  `caption=None` and no `caption_crm_message_id`; hidden audit caption remains
  `customer_visible=False` and has no provider message id.
- After deployed E2E found a related SKU spacing miss, hotfixed repeated spaces
  between SKU prefix and numeric anchor so `CH   616` normalizes like `CH 616`.

## Context7 And External Docs

- Context7 `/pydantic/pydantic-ai` confirmed `RunContext` tool parameters and
  `TestModel`/`FunctionModel` patterns for LLM-safe tests without live model calls.
- Wazzup sending docs confirm media payload uses `contentUri`; `text` and
  `contentUri` are mutually exclusive, so captions must not be embedded in the
  media payload as customer-visible text:
  https://wazzup24.com/help/api-en/sending-messages/

## Verification

- `OPENROUTER_API_KEY=dummy uv run pytest tests/test_llm_engine.py::test_extract_purchase_selection_accepts_generic_sku_spacing_variants tests/test_llm_engine.py::test_context_purchase_selection_accepts_bare_quantity_sku_after_product_choice tests/test_llm_engine.py::test_process_message_ch616_selection_confirms_without_manager_handoff tests/test_verified_answers.py::test_policy_routes_generic_sku_quantity_selection_to_product_path tests/test_services_chat_batch.py::test_process_incoming_batch_sends_deferred_product_media_after_bot_reply tests/test_outbound_audit.py::test_send_wazzup_media_with_audit_can_audit_caption_without_sending_it tests/test_outbound_audit.py::test_send_wazzup_media_with_audit_detailed_provider_suppresses_caption_send -v --tb=short` -> `9 passed`.
- `OPENROUTER_API_KEY=dummy uv run pytest tests/test_llm_engine.py tests/test_verified_answers.py tests/test_services_chat_batch.py tests/test_outbound_audit.py tests/test_messaging_wazzup.py -v --tb=short` -> `246 passed`.
- `uv run ruff check src/ tests/` -> passed.
- `uv run ruff format --check src/ tests/` -> passed after formatting the two touched LLM files.
- `uv run mypy src/` -> passed.
- `env DYLD_FALLBACK_LIBRARY_PATH="${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}" OPENROUTER_API_KEY=dummy uv run pytest tests/ -v --tb=short` -> `1056 passed, 19 skipped`.
- `scripts/orchestration/run_process_verification.sh` -> passed.
- `uv run python scripts/orchestration/validate_artifact.py .codex/stages/tj-gh18/artifacts/tj-gh18.1-2.md` -> passed.
- `OPENROUTER_API_KEY=dummy scripts/orchestration/run_stage_closeout.py --stage tj-gh18` -> passed.
- Post-merge hotfix checks:
  - `OPENROUTER_API_KEY=dummy uv run pytest tests/test_llm_engine.py::test_extract_purchase_selection_accepts_generic_sku_spacing_variants tests/test_llm_engine.py::test_context_purchase_selection_accepts_bare_quantity_sku_after_product_choice tests/test_llm_engine.py::test_process_message_ch616_selection_confirms_without_manager_handoff tests/test_verified_answers.py::test_policy_routes_generic_sku_quantity_selection_to_product_path -v --tb=short` -> `7 passed`.
  - `uv run ruff check src/ tests/` -> passed.
  - `uv run ruff format --check src/ tests/` -> passed.
  - `uv run mypy src/` -> passed.
  - `env DYLD_FALLBACK_LIBRARY_PATH="${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}" OPENROUTER_API_KEY=dummy uv run pytest tests/ -v --tb=short` -> `1057 passed, 19 skipped`.

## Delivery And Live E2E

- `codex/tj-gh18-open-issues-hardening` was fast-forward merged into `main`.
- First deploy: GitHub Actions run `26086747707`, release
  `49d7d066e4ec1228bf0397e163c3196b6a74f831`, success.
- Production API smoke after first deploy: `7 passed, 0 failed`.
- Initial production SKU matrix caught one related gap: `I need   6   CH   616`
  did not parse. This was fixed before closure.
- Final deploy: GitHub Actions run `26087478319`, release
  `af39abc4a1f299eb2c37af916c14d476ea2ab1b7`, success; `/opt/noor/.release-sha`
  and `/opt/noor/.release-run-id` match.
- Production API smoke after final deploy: `7 passed, 0 failed`.
- Approved production cleanup for `79262810921%` / `+79262810921%` before live
  testing removed 1 conversation, 4 messages, and 2 outbound audit rows; after
  cleanup all matching counts were 0.
- Final production parser/policy matrix passed for:
  `CH 616`, `CH-616`, `CH616`, lowercase `ch 616`, Cyrillic homoglyph `СН 616`,
  repeated spaces `CH   616`, bare `6 CH 616` rejected without product-choice
  context, bare `6 CH 616` accepted after a product-choice prompt, and
  verified-policy `product/allow/no-handoff`.
- Final #39 live webhook conversation
  `e3b12221-7206-4be8-8e59-d70d0732d446` passed:
  `name-gate`, bare `Lili`, then `I need   6   CH   616` returned
  `z-ai/glm-5|selection-confirmation`, stored pending quote item
  `CH 616 NEW black x6`, and kept pending escalations `0`.
- Final #35 live media conversation
  `d331625b-84be-442e-9b6a-f92ce6139101` passed:
  3 product media rows had provider message ids, 3 caption audit rows had
  `provider_message_id=NULL` and `details={"customer_visible": false}`, and no
  customer-visible caption text was sent separately.
- GitHub #39 and #35 were commented with fix and deployed E2E evidence, then
  closed.

## Comprehensive E2E Matrix For `tj-gh18.3`

Run after merge/deploy against the canonical runtime and only with explicit
approval for production cleanup/live WhatsApp if needed.

1. Clean synthetic runtime state for the approved test identity and record
   before/after counts.
2. #39 original flow:
   `Hi, I need 2 SKYLAND NOVO 2400 tables and 4 ergonomic chairs` -> name gate;
   `lil` -> product options; `I need 6 CH 616` -> `selection-confirmation`,
   `pending_quote_selection`, no manager text, `pending_escalations=0`.
3. SKU separator matrix after bot product-choice prompt:
   `6 CH 616`, `6 CH-616`, `6 CH616`, `I want 6 CH 616`,
   `I would like 6 CH-616`, `like 6 CH616`.
4. Numeric and dotted SKU matrix:
   `2 00-07024023`, `2 CP-2.1S`, `I need 2 CP 2.1S` where catalog data supports it.
5. Homoglyph/spaces matrix:
   Latin/Cyrillic lookalike `СН 616`, extra spaces, lowercase `ch 616`,
   and mixed separators.
6. Exact model matrix:
   `SKYLAND NOVO 2400`, `2 SKYLAND NOVO 2400`, and mixed
   `2 SKYLAND NOVO 2400 and 4 ergonomic chairs`; the bot must not re-ask the
   exact table model and may clarify only generic chairs.
7. Negative matrix:
   `6` alone, `yes`, `ok`, price text, payment terms, refund/complaint, and
   explicit human request; only true escalation paths may notify a manager.
8. #35 media flow:
   product recommendation with photos sends text first, then media with
   provider `caption=None`, no `caption_crm_message_id`, no separate caption
   text row visible to customer, and hidden caption audit rows
   `customer_visible=False`.
9. Long-dialog regression:
   name, company, address, exact products, generic product clarification,
   delivery/assembly questions, and follow-up selection should retain memory
   and avoid manager handoff unless a true escalation trigger appears.

## Project Index

project-index: reviewed-no-change. This stage changes LLM routing and regression
tests only; no stable entrypoints, directories, integrations, or verification
commands changed.

## Remaining Defers

- none for `tj-gh18`.
- `tj-b4n` / GitHub #24 remains provider-blocked pending an official Wazzup
  typing endpoint.
- GitHub #11 remains pending Lilia's answers.
