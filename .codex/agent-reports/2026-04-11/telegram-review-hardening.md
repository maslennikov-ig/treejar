# Telegram Review Hardening

## Root Cause Of Webhook Drift

- `src/api/telegram_webhook.py` validated `X-Telegram-Bot-Api-Secret-Token` against a secret derived from runtime state (`app_secret_key` + `telegram_bot_token`).
- Telegram webhook registration lived outside the repo/runtime lifecycle as a manual `setWebhook(...)` operation.
- After deploy/restart or secret rotation, runtime could start expecting a different secret than the one Telegram still had registered.
- Official Telegram Bot API behavior matters here:
  - `setWebhook` accepts `secret_token` and Telegram sends it back in `X-Telegram-Bot-Api-Secret-Token`.
  - `getWebhookInfo` exposes URL/error state, but not the stored `secret_token`.
- Result: drift was invisible until callback delivery failed with `403 Forbidden`, which matched the observed `getWebhookInfo.last_error_message`.

## Chosen Durable Fix And Why

- Chosen fix: startup-only repo-owned webhook sync in FastAPI lifespan.
- Implementation:
  - Added `src/integrations/notifications/telegram_webhook.py` as the single source of truth for:
    - expected webhook secret
    - canonical webhook URL
    - idempotent Telegram webhook sync
  - Added `get_webhook_info` and `set_webhook` methods to `TelegramClient`.
  - Called `sync_telegram_webhook()` from `src/main.py` startup lifecycle before the app begins serving requests.
  - Switched `src/api/telegram_webhook.py` validation to use the shared `expected_telegram_webhook_secret()` function.
- Why this lifecycle point:
  - FastAPI lifespan runs once at startup, which is the narrowest controlled place to reconcile external webhook config without tying it to unrelated request paths.
  - Repeating `setWebhook` with the same URL/secret is safe and idempotent enough for deploy/restart.
  - The sync does not weaken security; request validation remains strict and still rejects wrong secrets.
  - `drop_pending_updates` is not used, so sync does not intentionally discard queued updates.

## Exact Files Changed

- `src/api/telegram_webhook.py`
- `src/integrations/notifications/telegram.py`
- `src/integrations/notifications/telegram_webhook.py`
- `src/main.py`
- `src/services/escalation_state.py`
- `tests/test_order_review_flow.py`
- `tests/test_telegram_notifications.py`

## Escalation Row Sync Fix

- Added `resolve_conversation_pending_escalations()` to `src/services/escalation_state.py`.
- The helper:
  - loads the target conversation with related `escalations`
  - sets `Conversation.escalation_status = resolved`
  - updates only related escalation rows whose `status == pending`
  - leaves already-resolved history rows untouched
- Reused that helper in both resolution paths inside `src/api/telegram_webhook.py`:
  - manager text reply path
  - order confirm/reject path
- This keeps the previous business semantics unchanged:
  - confirm still sends PDF + confirmation text when PDF exists
  - reject still sends text only
  - Redis cleanup still runs
  - double-click still short-circuits on already-resolved conversations

## Verification Results

- `git diff --check` -> passed
- `git status --short` -> expected modified files only in this task branch
- `TMPDIR=/home/me/code/treejar/.tmp uv run ruff check src/ tests/` -> passed
- `TMPDIR=/home/me/code/treejar/.tmp uv run ruff format --check src/ tests/` -> passed
- `TMPDIR=/home/me/code/treejar/.tmp uv run mypy src/` -> passed
- `TMPDIR=/home/me/code/treejar/.tmp uv run pytest tests/test_order_review_flow.py tests/test_telegram_notifications.py -v --tb=short` -> 29 passed
- `TMPDIR=/home/me/code/treejar/.tmp uv run pytest tests/test_order_review_flow.py tests/test_telegram_notifications.py tests/ -v --tb=short` -> 29 passed
- Extra safety check because the previous command only collected the explicitly listed Telegram files:
  - `TMPDIR=/home/me/code/treejar/.tmp uv run pytest tests/ -v --tb=short` -> 600 passed, 19 skipped

## Residual Risks / Follow-Ups

- If Telegram Bot API is unreachable during startup, the app currently logs the sync failure and continues booting; that avoids taking down the runtime, but webhook drift would remain until the next successful startup or an explicit resync.
- Non-production environments without `DOMAIN` intentionally skip webhook sync to avoid accidental registration against the production canonical URL.
- If stricter operational guarantees are needed later, the next step would be an explicit deploy-stage health check that fails rollout when webhook sync cannot be completed.
