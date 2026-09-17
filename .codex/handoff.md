# Orchestrator Handoff

Updated: 2026-09-17
Current branch: `codex/model-owned-intent` (local worktree)
Current stage id: `tj-stwf-test-only-restore`
Status: `tj-r703` implemented and verified locally; not deployed.
Production testing remains limited to WhatsApp ending0665.

## Local delivery: tj-r703

- Main model owns customer intent, search constraints, consent and proposal
  decisions. Removed pre-model semantic routes and followup keyword rejection.
- Source remains on `codex/model-owned-intent` in
  `/home/me/code/treejar-model-intent`, based on `377a99a` (includes reset hotfix).
- Acceptance: 1,128 affected tests passed; Ruff check/format and Mypy passed.
  Controlled offline model/tool verification, not fresh live-model acceptance.
- Audit, preserved safety boundaries and rollback:
  `docs/reports/2026-09-17-model-owned-intent.md`.
- No new orchestration stage was created; the stage ID below records the last
  operational stage. Deployment and live messages require owner authorization.

## Current truth

- Owner-authorized reset repair `tj-0pht` is live as code release
  `82299519ac26eee8bcfbfaf2e69a47ec2af98747`, image `noor-reset:tj-0pht`.
- Exact source overlay on the prior image; app and worker recreated only.
  Health 200, Redis and database healthy. Environment is unchanged.
- TEST_CHANNEL_RESTORE_MODE remains true. Authenticated admin Telegram `/reset`
  plus confirmation/cancellation now work; unrelated Telegram updates are ignored.
- Test WhatsApp ending0665 remains the only allowed channel. Cron and embedding
  warmup remain off. Held messages were not inspected or changed.
- Owner-requested reset completed at 2026-09-16T17:18:44Z. New conversation
  `58f25771-f608-48e1-9586-6e22c503eec3`: greeting, no name, zero messages.
  Old conversation/profile archived; all 38 messages retained.
- Focused acceptance: 32 passed, Ruff/Mypy passed. Production authentication
  smoke passed and Telegram pending updates fell from 1 to 0.
- Source, risk, backup and recovery: `docs/reports/2026-09-16-telegram-reset-restore.md`.

## Completed repair: tj-d27h

- Fixed complete address capture, question/label collisions, invoice-as-phone
  capture, and known customer-fact alias loss. Details:
  `docs/reports/2026-09-09-customer-details-repair.md`.
- Repaired one diagnosed conversation and three address facts with a private
  backup, exact-state fingerprint, row locks and separate post-commit read.
- Local acceptance: 3,970 passed, 20 skipped; Ruff/format and Mypy passed.
  Independent review has no remaining blocking findings.
- CI acceptance: 3,963 passed, 27 skipped; lint and type checks passed.
- Read-only production smoke validated repaired data, original question/address/
  repeated-address sequence, no missing quotation fields, adjacent negative cases,
  and byte-identical deployed source. No model calls, messages or DB writes.
- This is deployed-code/data verification; a new tester-authored WhatsApp exchange
  was not performed as part of this release.
- Initial CI `34332793963` blocked on a mutable handoff digest. The repository
  maintenance helper corrected current-state pins; frozen sources were unchanged.

## Recovery

- Release rollback archive:
  `/opt/noor/.hotfix-backups/deploy-20260909T091436Z-from-af93ebd5a07d50e1689df76a28d465ddbbec2c17.tar.gz`.
- Data repair backup: `/home/me/.local/state/treejar/repairs/tj-d27h-before.json`
  (0600). Restore only changed fields after checking for intervening activity.
- Prior environment backup remains preserved:
  `/opt/noor/.hotfix-backups/env-20260901T104712Z-before-test0665-restore`.

## Operating boundary

The worker remains running for testing on test0665. Restore mode disables
non-reset Telegram actions, cron jobs, embedding warmup and every non-test channel. Broader
operation requires a separately authorized release.

## Explicit defers

- Integrate `codex/tj-0pht-telegram-reset` before the next standard deployment.
  Main CI uses app-only deployment and stops worker; preserve test continuity.

- `tj-bgwu`: existing corpus isolation test assumes a normal `.git` directory;
  linked-worktree acceptance uses an isolated normal clone until it is fixed.
- Wazzup sender authentication enforcement remains a long-term backlog task.
- The paid five-call route verifier and paid second reader were not used.
- Existing unrelated product defects remain in their own tracked tasks.
- Referral activation remains an excluded client decision.
- Reader-gap drift remains tracked in `tj-4q79`.

## Next recommended

Next stage id: `none` (accepted stage is complete)
Recommended action: review local tj-r703 delivery; obtain owner authority
before deployment, preserving the existing test0665-only boundary.

## Starter prompt for next orchestrator

Use $orchestrator-stage only for a newly authorized change. Preserve the
test0665-only boundary and held-message namespace. Obtain fresh authority
before another deploy or broader channel activation.

docs-reviewed: updated - model-owned intent, local acceptance and live boundary recorded.
graph-reviewed: no-change-needed - no graph is available in this worktree.
