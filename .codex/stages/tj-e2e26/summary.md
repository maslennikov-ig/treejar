# Stage tj-e2e26: 2026-04-26 Production E2E Hardening

Status: deployed; scoped E2E passed with order-status copy patch pending redeploy
Base worktree: `/home/me/code/treejar/.worktrees/codex-live-triage-20260417`
Primary evidence: production E2E on `https://noor.starec.ai` with real WhatsApp `79262810921` and synthetic suffixes.

## Evidence

- Discovery/stock/funnel: conversation `40bf2fae-a6b4-4c73-8e6e-574ca600e7da`, resolved.
- Telegram private reply: conversation `5aa65ae1-3e7a-4b0f-a0bb-206a517172e5`, resolved.
- Quotation approval + PDF: conversation `a5a49ecc-d273-44e4-9108-551ac7c19cd2`, quotation `Fr3139`, PDF delivered, resolved.
- Quotation reject: conversation `ae5f630b-4c00-4920-918f-dc0cfb17f466`, quotation `Fr3140`, resolved.
- Active escalation fallback: conversation `8e81e1b5-fa33-42aa-85a3-febbf868cddf`, fallback model worked, resolved.
- No created test conversation remained pending; health stayed `200 OK`.
- Direct SSH logs were unavailable to the tester: `Permission denied (publickey)`.

## Code Evidence

- `src/llm/engine.py` `check_order_status()` returns no-order before checking `metadata.zoho_sale_order_id`.
- `src/api/telegram_webhook.py` `_handle_manager_reply()` sends adapted private replies and resolves escalation without persisting a conversation `Message`.
- `src/api/telegram_webhook.py` `_handle_order_decision()` persists only a text `manager_decision` message and does not mark reject/approve decision metadata.
- `src/integrations/messaging/wazzup.py` returns provider `messageId`, but callers generally discard it; `send_media()` discards caption message ID.
- `src/api/v1/webhook.py` accepts Wazzup status payloads at schema level but status-only payloads are ignored before persistence.
- `src/api/v1/router.py` mounts `/api/v1/conversations` without auth dependencies; `src/api/v1/conversations.py` uses fuzzy `phone.ilike("%...%")` by default.

## Docs Notes

- Context7 FastAPI docs confirm router-level and `include_router(..., dependencies=[Depends(...)])` dependencies are current supported patterns for applying auth to all endpoints in an included router.
- Wazzup docs confirm `/v3/message` is not idempotent by default, `crmMessageId` is the duplicate-protection mechanism, successful responses include `messageId`, and status webhooks send `statuses[].messageId/status/timestamp`.

## Beads

- `tj-e2e26`: epic for the follow-up stage.
- `tj-e2e26.1`: order-status and quotation decision state after approval/reject. Closed after integration and local verification.
- `tj-e2e26.2`: conversation API auth and exact phone filtering by default. Closed after integration and local verification.
- `tj-e2e26.3`: Telegram private manager replies persisted as conversation messages. Closed after integration and local verification.
- `tj-e2e26.4`: durable outbound Wazzup audit for text/media/captions/statuses. Closed after integration and local verification.
- `tj-e2e26.5`: Wazzup `crmMessageId` idempotency. Closed after integration and local verification.
- `tj-e2e26.6`: product media and outbound side effects visible in admin/audit. Closed after integration and local verification.
- `tj-e2e26.7`: scoped post-fix E2E regression. In progress after deploy; required scope passed, then opened follow-up `tj-e2e26.8` for order-status copy consistency.
- `tj-e2e26.8`: order-status copy after quotation approve/reject. Closed locally; pending redeploy and narrow recheck.

## Implemented

- `src/llm/engine.py` now checks active `metadata.zoho_sale_order_id` before returning no-order, ignores rejected/inactive sale-order metadata, and avoids concurrent audit writes from product-media side effects.
- `src/llm/engine.py` / `src/llm/order_status.py` now make approved/rejected quotation decision copy explicit so draft Zoho sale orders no longer sound like pending manager review after Telegram decision.
- `src/api/telegram_webhook.py` now persists private manager replies as conversation messages after successful Wazzup send and writes approve/reject quotation decision metadata.
- `/api/v1/conversations/*` is mounted behind the API-key dependency; phone filtering is exact by default with explicit fuzzy mode.
- Added `outbound_message_audits` migration/model/service for Wazzup outbound text/media/caption audit, status updates, local idempotency, provider duplicate tracking, normalized provider message IDs, and caption-only retry when media already succeeded.
- Added Wazzup `crmMessageId` support to text/media/template sends and deterministic IDs for bot replies, manager replies, order decision text/PDF/caption, product media, timeout/fallback, follow-up, and feedback sends.
- Added read-only SQLAdmin visibility for outbound message audit rows.

## Local Verification

- `uv run --extra dev python -m pytest -s tests/test_llm_engine.py tests/test_order_review_flow.py tests/test_webhook_manager.py tests/test_outbound_audit.py tests/test_messaging_wazzup.py tests/test_webhook.py tests/test_services_chat_batch.py tests/test_product_images.py tests/test_migrations.py tests/test_admin_views_localization.py tests/test_api_conversations.py tests/test_api_escalation.py tests/test_scripts_bot_test.py tests/test_scripts_verify_api.py -q` -> `146 passed`.
- `uv run --extra dev python -m pytest -s tests/ -v --tb=short` -> `770 passed, 19 skipped`.
- `uv run ruff check src/ tests/ scripts/bot_test.py scripts/verify_api.py` -> passed.
- `uv run ruff format --check src/ tests/ scripts/bot_test.py scripts/verify_api.py` -> passed.
- `uv run mypy src/` -> passed.
- Artifact validation passed for `tj-e2e26.1-3.md`, `tj-e2e26.2.md`, and `tj-e2e26.4-6.md`.
- `uv run alembic heads` -> single head `2026_04_26_outbound_audit`.
- `bash scripts/orchestration/run_process_verification.sh` -> passed.
- `PYTEST_ADDOPTS=-s uv run python scripts/orchestration/run_stage_closeout.py --stage tj-e2e26` -> stage closeout verification OK. Plain closeout without `-s` hit the known local pytest capture tmpfile issue before tests ran.
- `git diff --check` -> passed.
- `tj-e2e26.8` local patch: `uv run --extra dev python -m pytest -s tests/test_order_status.py tests/test_llm_engine.py tests/test_order_review_flow.py tests/test_webhook_manager.py -q` -> `96 passed`; ruff/format/mypy/process verification/git diff check -> passed.

## Delivery / E2E

- `main@71f6b07c57fd7b075956d574f6ddf8efe6eca877` deployed through GitHub Actions run `24957702024`; jobs `lint`, `test`, `type-check`, and `deploy` succeeded.
- Post-deploy smoke passed: `verify_api.py` -> `7 passed, 0 failed`; health `200`; `/dashboard/` anonymous `401`; `/api/v1/conversations/` anonymous `403`; release `.release-sha=71f6b07...`; Alembic `2026_04_26_outbound_audit`; table `outbound_message_audits` exists.
- Scoped production E2E for `tj-e2e26.7` passed required checks: approve conversation `550ac918-d940-4d7d-af44-e48de4b4dfca` / `Fr3141`, reject conversation `9d28d1f2-c9a4-4f8d-bea7-1664807eba30` / `Fr3142`, private reply conversation `7781aa27-73b6-4f96-82c8-d3591f06737d`, anonymous conversations API `403`, exact/fuzzy phone filtering, outbound audit rows, synthetic status webhook update, zero pending created test conversations, health `200`.
- The same E2E found the `tj-e2e26.8` copy caveat: approved/rejected order-status text still sounded like pending manager review. The local fix is implemented and must be redeployed/rechecked before closing `tj-e2e26.7`.

## Guardrails

- Do not run broad production suites, `verify_wazzup.py`, scheduled AI Quality Controls, or unsolicited media tests without explicit approval.
- Keep product/API hardening separate from OpenRouter cost-control follow-ups.
- No deploy, prod mutation, force push, or permission expansion without explicit approval.
