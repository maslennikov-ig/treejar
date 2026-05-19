# Stage tj-gh18: Open Issues SKU Selection and Media Caption Hardening

Updated: 2026-05-19
Status: local implementation verified; delivery, deployed E2E, and GitHub closure pending in `tj-gh18.3`
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
- `tj-gh18.3`: merge/deploy/live E2E/GitHub closure remains explicitly pending.
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

- `tj-gh18.3`: delivery, deployed synthetic/live E2E, comments, and GitHub
  closure for #39/#35.
- `tj-b4n` / GitHub #24 remains provider-blocked pending an official Wazzup
  typing endpoint.
- GitHub #11 remains pending Lilia's answers.
