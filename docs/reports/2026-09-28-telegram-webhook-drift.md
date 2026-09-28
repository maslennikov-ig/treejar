# Telegram reset: webhook drift, third occurrence

Owner report 2026-09-28: `/reset +79689818825` in the admin chat did nothing,
the third time.

## Cause

Telegram `getWebhookInfo` showed `url: ""` with one pending update (the
`/reset`). Noor delivered its last Telegram update on 2026-09-25 12:38 UTC; the
app restarted at 13:18 UTC and registered the webhook without error. Someone
else holding the bot token deleted the registration afterwards. No agent
session, local project or other container on the Noor host holds the token;
it is still known to the legacy relay `tele.goldenherd.com` (alive) and the old
`136.243.71.213` server (documented as compromised, host key changed).

The three incidents share one mechanism:

- 2026-09-16: restore mode answered 503 before routing Telegram updates.
- 2026-09-22: the webhook pointed at the legacy relay.
- 2026-09-28: the webhook was deleted.

Noor only registered the webhook at app startup, so any outside change broke
`/reset` silently until the next deploy.

## Repair

- Immediate: the webhook was re-registered with the runtime's own
  `sync_telegram_webhook`; the queued `/reset` was delivered (HTTP 200) and the
  pending count dropped to 0.
- Permanent: worker cron `reconcile_telegram_webhook` runs every minute, also
  in test-channel restore mode. It re-registers the webhook when the URL
  differs from Noor's or Telegram reports a 403 (a foreign secret on our URL),
  and alerts the admin chat at most once an hour. The deploy probe allowlist
  includes the job.
- Remaining owner action: revoke the bot token in @BotFather and put the new
  one in `TELEGRAM_BOT_TOKEN`. Only that removes the outside holders; the cron
  bounds any further interference to about a minute.

## Evidence

Focused tests: 182 passed (telegram, reset, webhook, worker, deploy);
Ruff, format and Mypy passed.

## Follow-up: token rotation and deploy-interrupted turn

- Owner rotated the bot token. The old one was hardcoded in the public
  repository (`scripts/setup_bot.py`, since 2026-03-18), which explains the
  outside holders; the script now reads `TELEGRAM_BOT_TOKEN`. Production and
  local env files updated (backup `/opt/noor/.hotfix-backups/tj-gurp-*`), app
  and worker recreated, old token rejected by Telegram, webhook re-registered.
- The 09:26 deploy cancelled the tester's turn ("LUMA would be better for us.")
  mid-reply; the at-most-once guard quarantined it as `uncertain_replay`. With
  no outbound audit row and no assistant message, the batch was re-queued
  through the normal path and answered at 09:35:51 (sent).
- Permanent: the worker sets arq `job_completion_wait` (170 s): on SIGTERM it
  stops taking jobs and lets a running turn finish. Worker `stop_grace_period`
  is 200 s and the deploy stop timeout 200 s. Verified with a real arq worker
  and Redis: without the wait a 6 s job was cancelled; with it, it finished.
