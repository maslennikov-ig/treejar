# Stage tj-4kba — Allow `/admin` Telegram login command during `test_channel_restore_mode`

- Branch `codex/tj-4kba-telegram-admin-login`, worktree `.worktrees/tj-4kba-telegram-admin-login`,
  base `main` `fcc11ef` (owner-authorized push, merge to `main`, and production deploy `2026-10-26`).
- Pinned RAG files (`src/models/product.py`, `src/rag/embeddings.py`,
  `src/rag/pipeline.py`, `src/schemas/product.py`) unchanged vs `main`.

## Root Cause & Delivered Fix
- **Root Cause**: On live `/opt/noor`, `TEST_CHANNEL_RESTORE_MODE=true` is active to keep customer-facing WhatsApp manager replies gated to the test channel. In `src/api/telegram_webhook.py`, the `if settings.test_channel_restore_mode:` block only checked `_handle_reset_command_if_present(message)` and returned `{"status": "ignored"}` before `_handle_admin_login_command_if_present(message)` could run, silencing `/admin` and `/start admin` (`Войти через Telegram`).
- **Fix (`src/api/telegram_webhook.py`)**:
  - Added `await _handle_admin_login_command_if_present(message)` inside `test_channel_restore_mode` alongside `_handle_reset_command_if_present(message)`. Admin login issues a read-only Noor CRM session link to whitelisted `TELEGRAM_ADMIN_USER_IDS` and performs zero WhatsApp/customer egress; ordinary messages and non-reset callbacks remain ignored.
  - Added structured `INFO` log on unauthorized `/admin` requests (`user_id`, `username`, `reason`) to simplify onboarding approved team members.
- **Regression Coverage (`tests/test_webhook_manager.py`)**:
  - Verified `/admin` and `/start admin` issue one-time Noor CRM login links when `test_channel_restore_mode=True` without invoking `_handle_manager_reply`, and verified ordinary text messages still return `{"status": "ignored"}`.

## Verification
- `uv run ruff format --check src/ tests/`, `uv run ruff check src/ tests/`, `uv run mypy src/`: passed.
- `uv run pytest tests/test_webhook_manager.py tests/test_telegram_admin_login.py tests/test_e2e_acceptance_manifests.py tests/test_orchestration_repin_traceability.py -q --tb=short`: passed.
- `bash scripts/orchestration/run_process_verification.sh`: passed.
- `docs-reviewed: updated - added stage summary and updated handoff; re-pinned traceability manifest`.
- `graph-reviewed: no-change-needed - single-module webhook branch condition; no cross-module graph change`.
