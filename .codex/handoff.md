# Orchestrator Handoff

Updated: 2026-09-17
Current branch: `main` (delivered via codex/model-intent-main-final)
Current stage id: `tj-stwf-test-only-restore` (last operational stage)
Status: tj-r703, tj-tn29, tj-15bc and tj-a1bi complete; merged and deployed.

## Current truth

- Live release: `4abe8355d6dbb074d1d8e66e963457e054a481c2`.
- CI35223521584 succeeded: 4,059 passed, 27 skipped; lint/types passed.
- Public health200; database/Redis healthy. App/worker running, zero restarts;
  all14changed source hashes match accepted code in both containers.
- Main model owns contextual customer intent and receives per-run instructions
  even with history. Repairs retain tool results and bounded catalog/context.
- Orphan numbered-list reductions are rejected for coherent model repair.
  Transient Inventory reads return unavailable evidence rather than aborting
  the answer. Shared-session tools execute sequentially.
- Existing CI --app-only invocation now safely refreshes an already-running
  verified test-only worker; stopped/non-test workers retain the app-only gate.
- Report: `docs/reports/2026-09-17-live-reply-repair.md`.

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

- Latest backup: `/opt/noor/.hotfix-backups/tj-15bc-main-20260917`.
  Restore source-before.tar.gz and compose-rollback.yml for app/worker only,
  image noor-intent:tj-tn29, previous release9a08683. Preserve DB activity/env.
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
Recommended action: tester-authored dialogue on updated test-only runtime.
No claim that local tests eliminate all future model errors.

## Starter prompt for next orchestrator

Use $orchestrator-stage for a newly authorized change. Preserve test-only
channels, worker restrictions, rollback evidence and unrelated work.

docs-reviewed: updated - main release, proof and recovery recorded.
graph-reviewed: no-change-needed - no graph is available in this worktree.
