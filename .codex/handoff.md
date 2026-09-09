# Orchestrator Handoff

Updated: 2026-09-09
Current branch: `main`
Current stage id: `tj-stwf-test-only-restore`
Status: Customer-detail fix `tj-d27h` deployed and verified with owner approval.
Production testing remains limited to WhatsApp ending0665.

## Current truth

- Release `e071bb683e1fcc876efd40ca16b28ed6d2486241` is live.
  Code fix: `9d2fb662aa91b9c02fc1672ee3677bd7d7be33a4`.
- GitHub Actions run `34333335661` passed tests and deployed the application.
- App `154bc9721adf` and worker `f4ab6dd8b4ef` run the same image
  `sha256:158974224c54e390b344967cc13f8afc74fd05eb878dfdcabf631f30e38e0be2`,
  with zero restarts and no OOM event at verification.
- Worker startup confirmed `process_incoming_batch` and test-channel restore mode.
- Public health reports the exact release with healthy PostgreSQL and Redis.
- `WAZZUP_CHANNEL_ID` and `WAZZUP_OUTBOUND_ALLOWED_CHANNEL_ID` both resolve
  only to test0665. `bot_enabled=true`, `TEST_CHANNEL_RESTORE_MODE=true`.
- Production model remains `z-ai/glm-5.3-flash`; the environment file is unchanged.
- PostgreSQL `43ccb64efb9d`, Redis `1b9c9a5c99d0` and nginx `0cdbce63c5db`
  were preserved with zero restarts and no OOM event.
- Historical messages under `hold:tj-stwf:20260901T104616Z:` were untouched;
  do not replay, delete or inspect them. No current queue-depth claim is made.

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
Telegram, cron jobs, embedding warmup and every non-test channel. Broader
operation requires a separately authorized release.

## Explicit defers

- `tj-bgwu`: existing corpus isolation test assumes a normal `.git` directory;
  linked-worktree acceptance uses an isolated normal clone until it is fixed.
- Wazzup sender authentication enforcement remains a long-term backlog task.
- The paid five-call route verifier and paid second reader were not used.
- Existing unrelated product defects remain in their own tracked tasks.
- Referral activation remains an excluded client decision.
- Reader-gap drift remains tracked in `tj-4q79`.

## Next recommended

Next stage id: `none` (accepted stage is complete)
Recommended action: resume tester-owned testing on test0665.

## Starter prompt for next orchestrator

Use $orchestrator-stage only for a newly authorized change. Preserve the
test0665-only boundary and held-message namespace. Obtain fresh authority
before another deploy or broader channel activation.

docs-reviewed: updated - release, repair, verification and recovery recorded.
graph-reviewed: no-change-needed - no graph is available in this worktree.
