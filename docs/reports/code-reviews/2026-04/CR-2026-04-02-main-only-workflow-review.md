# Code Review: Main-Only Workflow And Safety Changes

Date: 2026-04-02
Scope: commits `3cc1b29..e380664`
Reviewer: Codex orchestrator + independent explorer review

## Findings

### 1. High: local smoke scripts now bypass escalation state persistence

- Files:
  - `scripts/bot_test_suite.py:169`
  - `src/integrations/notifications/escalation.py:49`
- Problem:
  - `scripts/bot_test_suite.py` now replaces `notify_manager_escalation()` with `AsyncMock()` unless `ALLOW_REAL_ESCALATIONS=1`.
  - `notify_manager_escalation()` is also the function that sets `conversation.escalation_status = pending` and commits it.
  - Escalation smoke scenarios in the suite still assert against persisted DB state after calling `process_message()`.
- Impact:
  - Escalation scenarios no longer exercise the real runtime contract.
  - The suite can now produce false negatives or false positives depending on the mock rather than the product behavior.
- Recommended fix:
  - Keep the state-changing `notify_manager_escalation()` path intact.
  - Suppress only the external Telegram side effects, for example by patching `TelegramClient.send_message_with_inline_keyboard()` and `TelegramClient.send_document()` in local scripts.

### 2. High: `setup-vps.sh` is broken for fresh main-only bootstrap

- Files:
  - `scripts/treejar-prod.conf:23`
  - `scripts/treejar-prod.conf:27`
  - `scripts/setup-vps.sh:46`
- Problem:
  - `scripts/setup-vps.sh` copies a config with mandatory `listen 443 ssl` and Let's Encrypt certificate paths, then immediately runs `nginx -t`.
  - On a fresh host those certificate files do not exist yet, so bootstrap fails before the server can even serve ACME challenges.
- Impact:
  - The production bootstrap path is no longer usable on a clean VPS.
  - Main-only simplification introduced an ops regression exactly in the first-install flow.
- Recommended fix:
  - Make bootstrap two-stage:
    - install an HTTP-only config when certificates are absent
    - enable the HTTPS config only after certificates exist
  - Update the script output so the operator knows to rerun setup after issuing the certificate.

## Follow-Up Improvements

- `scripts/setup-vps.sh:30` still prints the old clone location (`/home/starec/treejar-ai-bot`) even though the script now expects `/opt/treejar-prod`.
- Existing `treejar-dev` nginx sites are not removed during main-only convergence, so stale virtual hosts can survive on already-configured servers.
- `.codex/handoff.md` still references closed follow-up `tj-2e5`, so repo-local handoff state is stale.

## Sources Checked

- Local diff and source inspection for all touched files in the review scope.
- Context7:
  - `/nginx/documentation` for HTTPS server configuration with explicit `ssl_certificate` and `ssl_certificate_key`
  - `/pytest-dev/pytest` for module-level conditional skipping patterns used by the safety test gate
