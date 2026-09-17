# Orchestrator Handoff

Updated: 2026-09-17
Current branch: `codex/model-owned-intent`
Current stage id: `tj-stwf-test-only-restore` (last operational stage)
Status: tj-15bc live-reply fixes and tj-a1bi authorized main deployment in progress.

## Current truth

- Live code release: `9a0868356065395853bcfaabd293639f78ce2ab5`.
- Image `noor-intent:tj-tn29`; app and worker recreated only.
- Public health 200, exact release SHA, database and Redis healthy.
- Main model owns customer intent, contextual short replies, consent,
  requirements, proposal decisions and search constraints. Old inbound semantic
  routes and automatically appended service promises are removed.
- Explicit model tools support atomic selected-item replacement/removal and
  validated durable customer facts. Factual/access/quote safeguards remain.
- Full local acceptance 4,045 passed, 20 skipped; final source delta 190 passed.
  Ruff and Mypy passed. Six paid main-model probes used (USD 0.045969111),
  with no executed business tools, messages or DB writes.
- All three cases selected the expected search direction. Comparison fixture
  omitted a NOVO SKU and exposed an overclaim from incomplete results; final
  prompt clarifies that limitation, locally checked. Not full WhatsApp E2E.
- Details: `docs/reports/2026-09-17-model-intent-release.md`.

## Operating boundary

- TEST_CHANNEL_RESTORE_MODE remains true; WhatsApp ending0665 is the only
  allowed channel. Worker only processes inbound batches.
- Cron, embedding warmup and non-reset Telegram startup sync remain disabled.
- Authenticated admin Telegram reset hotfix remains present and unchanged.
- Held messages and customer history were not inspected or changed for release.
- No customer messaging was authorized or sent as part of verification.
- Broader channel activation requires separate authority.

## Recovery

- Release backup: `/opt/noor/.hotfix-backups/tj-tn29-20260917` (0700).
- Restore `source-before.tar` to `/opt/noor`, use saved `compose-rollback.yml`
  with base compose and recreate only app/worker (`--no-deps --no-build`).
- Previous reset release `82299519ac26eee8bcfbfaf2e69a47ec2af98747`;
  rollback image `noor-intent-base:tj-tn29`. Do not roll back customer activity.
- September 16 reset backup remains `/opt/noor/.hotfix-backups/tj-0pht-20260916`;
  September 9 customer-fact backup remains
  `/home/me/.local/state/treejar/repairs/tj-d27h-before.json` (0600).

## Explicit defers

- `tj-a1bi`: integrate the release/reset branch into main without stopping the
  authorized test worker. Current main CI uses app-only deployment.
- `tj-bgwu`: corpus identity tests assume a normal treejar/.git directory;
  full acceptance uses an isolated normal clone with canonical remote identity.
- Existing unrelated product defects stay in their tracked tasks. Wazzup sender
  authentication enforcement remains backlog; referral activation excluded.
- Paid second reader not used; reader-gap drift remains tracked in tj-4q79.

## Pending main release

- Fixes: per-run persona with history, evidence-preserving repair, malformed-list
  repair, Inventory throttling containment and sequential shared-session tools.
- Source report: `docs/reports/2026-09-17-live-reply-repair.md`.
- CI now preserves an existing test-only worker after verifying its boundaries.

## Next recommended

Next stage id: `none`
Recommended action: finish the authorized tj-15bc/tj-a1bi main release.

Tester-authored dialogue against the updated test-only runtime. Do not infer
zero future model errors from offline tests or isolated model-plan probes.

## Starter prompt for next orchestrator

Use $orchestrator-stage for a newly authorized change. Preserve test-only
channels, worker restrictions, rollback evidence and unrelated work.

docs-reviewed: updated - release, evidence limitations and recovery recorded.
graph-reviewed: no-change-needed - no graph is available in this worktree.
