# Orchestrator Handoff

Updated: 2026-09-18
Current branch: `main` (delivered via codex/quotation-timeout)
Current stage id: `tj-stwf-test-only-restore` (last operational stage)
Status: tj-3egt quotation-timeout repair deployed and verified.

## Current truth

- Live release: `74ae14c789c909763b4150a4b22e296dd8abdd38`.
- CI35360991418 succeeded: 4,066 passed, 27 skipped; lint/types passed.
- Local acceptance: 4,073 passed, 20 skipped.
- Public health200; database/Redis healthy. App/worker running, zero restarts;
  all three changed source hashes match accepted code in both containers.
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
- Report: `docs/reports/2026-09-18-quotation-timeout.md`.

## Operating boundary

- Environment unchanged. TEST_CHANNEL_RESTORE_MODE=true; only WhatsApp ending0665.
- Worker only processes inbound batches; cron and embedding warmup disabled.
- Authenticated admin Telegram reset hotfix preserved.
- No synthetic messages, DB repairs, resets or held-message changes for release.
- Earlier six paid probes are exhausted; no further calls were made. Those
  probes showed intended tool directions but were not WhatsApp E2E evidence.
- Broader activation, additional paid probes or synthetic messaging require
  separate authority.

## Recovery

- Latest backup: `/opt/noor/.hotfix-backups/tj-3egt-20260918`.
  Restore source-before.tar.gz and compose-rollback.yml for app/worker only,
  images noor-rollback:tj-3egt-app and noor-rollback:tj-3egt-worker, previous
  release4abe835. Preserve DB activity/env.
- Earlier release backup: `/opt/noor/.hotfix-backups/tj-tn29-20260917`.
- Reset backup: `/opt/noor/.hotfix-backups/tj-0pht-20260916`.
- Customer-fact backup remains
  `/home/me/.local/state/treejar/repairs/tj-d27h-before.json` (0600).

## Explicit defers

- `tj-bgwu`: corpus identity tests assume normal treejar/.git; local full
  acceptance uses an isolated normal clone with canonical remote identity.
- Existing unrelated product defects stay tracked separately. Wazzup sender
  authentication enforcement remains backlog; referral activation excluded.
- Paid second reader not used; reader-gap drift remains tracked in tj-4q79.

## Next recommended

Next stage id: `none`
Recommended action: tester repeats the normal quotation scenario; live end-to-end
quotation creation was not probed in this release (no new paid-call authority).
No claim that local tests eliminate all future model errors.

## Starter prompt for next orchestrator

Use $orchestrator-stage for a newly authorized change. Preserve test-only
channels, worker restrictions, rollback evidence and unrelated work.

docs-reviewed: updated - main release, proof and recovery recorded.
graph-reviewed: no-change-needed - no graph is available in this worktree.
