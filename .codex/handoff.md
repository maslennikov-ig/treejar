# Orchestrator Handoff

Updated: 2026-09-23
Current branch: `codex/gpt6-luna-main`
Current stage id: `tj-stwf-test-only-restore` (last operational stage)
Status: tj-qr32 primary model switched to GPT-6 Luna medium; live readback verified.

## Current truth

- Latest live release: `6ae4c0ea4e61fe8bab77a0b9db59f015c4bf1d70` (tj-qr32).
  Primary DB/env model is `openai/gpt-6-luna`; core reasoning explicitly medium.
  App/worker source hashes, fresh DB reads, health and test restrictions verified.
  Focused acceptance: 43 tests, Ruff/format and Mypy passed. One isolated
  tool-schema compatibility call cost USD 0.0000155; no customer sends/tools ran.
  Real conversation quality is not yet verified. Fast/auxiliary routes unchanged.
  Report: `docs/reports/2026-09-23-gpt6-luna-main.md`.
  Rollback: `/opt/noor/.hotfix-backups/tj-qr32-20260923`, previous model GLM 5.3.

### Previous release evidence

- Live release: `1dd3b05d1fb69c6bf3b19e7ffb24a3d116334ac7`.
- CI 35825663699 succeeded: 4,108 passed, 27 skipped; lint/types and
  app-only deploy passed. Public API health returned the exact release SHA
  with healthy database and Redis.
- Escalation now requires an explicit human request, current-turn recorded
  acceptance of a sent quotation, or a customer-evidenced active incident.
  Ordinary sales, optional add-on refusals, policy questions, catalog gaps,
  and failed reply repair remain autonomous. Active handoffs are not duplicated.
- Telegram points directly to the canonical Noor webhook with zero pending
  updates and no delivery error. Restore-mode startup now reconciles the
  webhook without publishing unavailable commands.
- Owner-requested reset for `+79689818825` completed at
  2026-09-22T08:33:12.989639Z. New conversation
  `d73f0b16-928b-41ab-97e4-de8c3644fd74` has no name and zero messages.
  The previous conversation is archived with all 10 messages retained; no
  matching customer profile or pending reset token remains.
- Focused acceptance: 61 passed; Ruff/format/Mypy passed. Production webhook
  authentication smoke passed.
- Public health 200; database/Redis healthy. App/worker running, zero restarts;
  changed source hashes match accepted code.
- Core completions have a 35-second bound and one same-request retry within
  the unchanged 90-second run deadline; completed tools are not replayed.
- Quotation guidance records contextual consent through the model-owned tool;
  tool phase/outcome/duration logs omit customer arguments.
- Main model owns contextual customer intent and receives per-run instructions
  even with history. Repairs retain tool results and bounded catalog/context.
- Orphan numbered-list reductions are rejected for coherent model repair.
  Transient Inventory reads return unavailable evidence rather than aborting
  the answer. Shared-session tools execute sequentially.
- Existing CI --app-only invocation now safely refreshes an already-running
  verified test-only worker; stopped/non-test workers retain the app-only gate.
  This release passed the existing/candidate worker safety checks.
- Reset report: `docs/reports/2026-09-22-telegram-reset-webhook.md`.
- Quotation repair remains present; its report is
  `docs/reports/2026-09-18-quotation-timeout.md`.

## Operating boundary

- Only primary-model environment setting changed. TEST_CHANNEL_RESTORE_MODE=true; WhatsApp remains
  limited to ending0665 and Telegram to authenticated admin reset operations.
- Worker only processes inbound batches; cron and embedding warmup disabled.
- Non-reset Telegram actions remain ignored.
- No synthetic messages, direct DB repairs or held-message changes. The requested
  reset ran only through the authenticated Telegram flow.
- Prior paid probe allowance remains exhausted. This switch used one isolated
  compatibility call (USD 0.0000155); no additional calls are queued.
- Broader activation, additional paid probes or synthetic messaging require
  separate authority.

## Recovery

- Latest backup: `/opt/noor/.hotfix-backups/deploy-20260923T061517Z-from-64a28bd520fce97a998596a652666eb2267d71ee.tar.gz`.
  App-only rollback must preserve the completed Telegram data reset.
- Prior reset backup: `/opt/noor/.hotfix-backups/tj-it9r-20260922T083204Z`;
  prior app image tag `noor-app:tj-it9r-before`.
- Previous quotation-release backup: `/opt/noor/.hotfix-backups/tj-3egt-20260918`.
  Restore source-before.tar.gz and compose-rollback.yml for app/worker only,
  images noor-rollback:tj-3egt-app and noor-rollback:tj-3egt-worker, previous
  release4abe835. Preserve DB activity/env.
- Earlier release backup: `/opt/noor/.hotfix-backups/tj-tn29-20260917`.
- Reset backup: `/opt/noor/.hotfix-backups/tj-0pht-20260916`.
- Customer-fact backup remains
  `/home/me/.local/state/treejar/repairs/tj-d27h-before.json` (0600).

## Explicit defers

- `tj-3nvu`: integrate pushed `codex/gpt6-luna-main` before the next standard
  deployment. Explicit merge authority is required by the repo contract.
- `tj-pmbv`: curly-apostrophe self-introduction is not extracted and static
  error replies receive the first-turn name question. Reproduced; not fixed here.

- `tj-bgwu`: corpus identity tests assume normal treejar/.git; local full
  acceptance uses an isolated normal clone with canonical remote identity.
- Existing unrelated product defects stay tracked separately. Wazzup sender
  authentication enforcement remains backlog; referral activation excluded.
- Paid second reader not used; reader-gap drift remains tracked in tj-4q79.

## Next recommended

Next stage id: `none`
Recommended action: continue tester-owned testing on test0665. Use Telegram only
for authenticated admin reset operations. The live quotation scenario remains
unprobed without new paid-call authority; no synthetic customer messages or
paid model calls were part of that earlier release verification.

## Starter prompt for next orchestrator

Use $orchestrator-stage for a newly authorized change. Preserve test-only
channels, worker restrictions, rollback evidence and unrelated work. The reset
webhook repair is integrated into main; do not reintroduce the legacy relay.

docs-reviewed: updated - critical-only release, CI, backup and recovery recorded.
graph-reviewed: no-change-needed - no graph is available in this worktree.
