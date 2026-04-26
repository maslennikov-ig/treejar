---
task_id: tj-e2e26.4-6
stage_id: tj-e2e26
repo: treejar
branch: codex/tj-e2e26-order-decision-replies
base_branch: codex/live-triage-20260417
base_commit: b54ebb7
worktree: /home/me/code/treejar/.worktrees/codex-tj-e2e26-order-decision-replies
status: returned
verification:
  - uv run --extra dev python -m pytest -s tests/test_outbound_audit.py tests/test_messaging_wazzup.py tests/test_webhook.py tests/test_services_chat_batch.py tests/test_order_review_flow.py tests/test_webhook_manager.py tests/test_product_images.py tests/test_migrations.py tests/test_admin_views_localization.py -q: passed
  - uv run ruff check src/ tests/: passed
  - uv run ruff format --check src/ tests/: passed
  - uv run mypy src/: passed
  - uv run python scripts/orchestration/validate_artifact.py .codex/stages/tj-e2e26/artifacts/tj-e2e26.4-6.md: passed
  - git diff --check: passed
changed_files:
  - .codex/stages/tj-e2e26/artifacts/tj-e2e26.1-3.md
  - .codex/stages/tj-e2e26/artifacts/tj-e2e26.4-6.md
  - migrations/versions/2026_04_26_add_outbound_message_audit.py
  - src/api/admin/views.py
  - src/api/telegram_webhook.py
  - src/api/v1/webhook.py
  - src/integrations/messaging/base.py
  - src/integrations/messaging/wazzup.py
  - src/llm/engine.py
  - src/models/__init__.py
  - src/models/outbound_message.py
  - src/services/chat.py
  - src/services/followup.py
  - src/services/outbound_audit.py
  - tests/test_admin_views_localization.py
  - tests/test_llm_engine.py
  - tests/test_messaging_wazzup.py
  - tests/test_migrations.py
  - tests/test_order_review_flow.py
  - tests/test_outbound_audit.py
  - tests/test_product_images.py
  - tests/test_services_chat_batch.py
  - tests/test_webhook.py
  - tests/test_webhook_manager.py
---

# Summary

Implemented cohesive batch `tj-e2e26.4`, `tj-e2e26.5`, and `tj-e2e26.6` on top of the already reviewed order/Telegram fixes.

- Added `OutboundMessageAudit` plus Alembic migration for durable Wazzup outbound audit rows with provider, conversation, chat ids, message type, content/caption/media metadata, provider `messageId`, `crmMessageId`, source, status, error/details JSON, and timestamps.
- Added `src.services.outbound_audit` helpers for audited text/media sends, deterministic `crmMessageId`, local idempotency suppression for active audit rows, durable failed-attempt commits before re-raise, provider duplicate marking, normalized missing/`unknown` provider message ids, caption-only retry after media success, and status webhook updates by Wazzup `messageId`.
- Extended Wazzup provider/interface with optional `crmMessageId` for text, media, and templates while preserving existing return contracts. Added a detailed media helper for separate media/caption ids.
- Wired audit/idempotency into normal bot replies, Telegram private manager replies, order confirm/reject text, order PDF media plus caption, product media side effects, timeout/fallback sends, and automatic followup/feedback sends. Product media sends are sequential on the shared LLM session and commit audit rows immediately after each successful outbound side effect.
- Added Wazzup status webhook persistence that updates matching audit rows and safely ignores unknown provider message ids.
- Added read-only SQLAdmin visibility for outbound audit rows.

# Docs Notes

Wazzup first-party docs used:

- Sending messages: https://wazzup24.com/help/api-en/sending-messages/
  - `POST /v3/message` supports `crmMessageId` as the CRM-side identifier for idempotent routing.
  - `text` and `contentUri` are mutually exclusive request fields.
  - Successful send responses include `messageId` and `chatId`.
  - Reusing a `crmMessageId` can return HTTP 400 with `REPEATED_CRM_MESSAGE_ID` / `repeatedCrmMessageId`; current code commits `provider_duplicate` before re-raising and treats future attempts with the same `crmMessageId` as skipped.
- Webhooks: https://wazzup24.com/help/webhooks/
  - A webhook can include `messages` and `statuses` in the same payload.
  - Status updates arrive under `statuses[]`, keyed by Wazzup `messageId`.
  - Outbound status values include `sent`, `delivered`, `read`, `error`, and `edited`; error payloads may include provider error details.

SQLAlchemy/Alembic/SQLAdmin notes:

- SQLAlchemy JSON in-place mutations are not relied on for new audit writes; JSON fields are assigned/reassigned as full values. Existing order metadata code from `.1/.3` also uses safe reassignment/explicit mutation handling.
- Alembic migration follows repo/local operation patterns for `op.create_table`, constraints, indexes, and reverse-order `downgrade`.
- SQLAdmin read-only behavior follows the installed SQLAdmin `ModelView` pattern with `can_create`, `can_edit`, and `can_delete` disabled.

# Verification

- `uv run --extra dev python -m pytest -s tests/test_outbound_audit.py tests/test_messaging_wazzup.py tests/test_webhook.py tests/test_services_chat_batch.py tests/test_order_review_flow.py tests/test_webhook_manager.py tests/test_product_images.py tests/test_migrations.py tests/test_admin_views_localization.py -q` -> passed, `71 passed`.
- `uv run ruff check src/ tests/` -> passed.
- `uv run ruff format --check src/ tests/` -> passed.
- `uv run mypy src/` -> passed.
- `uv run python scripts/orchestration/validate_artifact.py .codex/stages/tj-e2e26/artifacts/tj-e2e26.4-6.md` -> passed.
- `git diff --check` -> passed.

# Risks / Follow-ups / Explicit Defers

- No prod/staging mutation, deploy, broad production suite, `verify_wazzup.py`, scheduled AI Quality Controls, frontend work, or unsolicited live media tests were run.
- No explicit functional defer for requested send paths: bot text, manager private replies, order text/PDF/caption, product media, timeout/fallback, followup, feedback, and status webhooks are covered by hooks or tests.
- Provider duplicate handling is intentionally conservative: first repeated Wazzup `crmMessageId` responses are committed as `provider_duplicate` and re-raised so existing caller-visible error behavior is not silently changed; later local attempts with the same `crmMessageId` are suppressed as skipped.
- Ordinary provider errors are committed as `error` before re-raise. A later retry reuses the same audit row for that `crmMessageId` instead of inserting a duplicate row.
- Live Wazzup delivery/status sequencing remains untested locally; validation is limited to provider payload/unit tests and webhook persistence tests.
