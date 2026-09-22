# Telegram reset webhook recovery

Task: `tj-it9r`. Owner authorized switching the production Telegram webhook,
deploying the repair, and resetting `+79689818825`.

## Cause and repair

Telegram still pointed at the legacy relay
`https://tele.goldenherd.com/tg/webhook/8651031074`. The relay returned 502/timeouts,
so the queued `/reset` update never reached Noor even though Noor health stayed
green. Restore mode intentionally skipped all Telegram startup synchronization,
which also prevented the application from repairing the stale provider webhook.

Release `64a28bd520fce97a998596a652666eb2267d71ee` now always reconciles the
secret-protected Noor webhook on startup. In restore mode it does not publish
Telegram commands and continues to accept only authenticated admin reset command,
confirmation and cancellation updates; all unrelated Telegram actions remain
ignored. WhatsApp remains restricted to the configured test channel, and cron
jobs and embedding warmup remain disabled.

## Delivery and recovery

The canonical webhook is now
`https://noor.starec.ai/api/v1/webhook/telegram`. GitHub Actions run
`35706122529` passed and deployed the exact release. The app and guarded worker
are running; the worker registers only `process_incoming_batch` and zero cron
jobs.

Pre-change backup: `/opt/noor/.hotfix-backups/tj-it9r-20260922T083204Z`.
It contains the prior sources, release markers, image and container records. The
prior app image is also tagged `noor-app:tj-it9r-before`. If this webhook repair
must be rolled back, restore the saved sources/image and explicitly restore the
saved provider webhook registration only after confirming current Telegram
delivery state. Do not reverse the completed data reset as part of code rollback.

## Evidence

- Focused local acceptance: 61 tests passed; Ruff check/format, Mypy and
  `git diff --check` passed.
- CI acceptance: lint and type checks passed; 4,067 tests passed and 27 skipped.
- Public health reports release `64a28bd520fce97a998596a652666eb2267d71ee`;
  Redis and PostgreSQL are healthy.
- Telegram reports the canonical Noor webhook, zero pending updates and no last
  delivery error. Invalid webhook secret returns 403; an authenticated inert
  update returns 200 and is ignored.
- Reset completed at `2026-09-22T08:33:12.989639+00:00` (11:33 Moscow).
  Fresh conversation `d73f0b16-928b-41ab-97e4-de8c3644fd74` is active at the
  greeting stage with no name and zero messages. The previous conversation is
  archived with all 10 messages retained. No matching customer profile or
  pending reset token remains.
- The owner independently observed the bot's successful reset confirmation.

docs-reviewed: updated - root cause, release, reset result and recovery recorded.
graph-reviewed: no-change-needed - this bounded startup integration change does
not require a graph refresh.
