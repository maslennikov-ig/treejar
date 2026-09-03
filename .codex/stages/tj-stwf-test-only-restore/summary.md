# Stage tj-stwf-test-only-restore

Status: IN PROGRESS. Restore production only for test WhatsApp ending0665.
The superseded9235 stage and frozen criteria remain historical and unaccepted.

## Current evidence

- Owner reconnected test0665; read-only User API v3 returned `active` at
  2026-09-01 10:08:21 UTC.
- Production app and worker remain exited with restart policy `no`; DB, Redis
  and nginx remain running.
- Candidate safety code passed the prior focused local acceptance and independent
  authorization re-review. Release acceptance and delivery are pending here.
- At 2026-09-01 10:46:16 UTC, all nine retained `wazzup_msgs` lists were
  atomically renamed into `hold:tj-stwf:20260901T104616Z:` after exact key and
  DUMP fingerprint validation. Live retained keys and ARQ jobs are zero; the
  held manifest SHA-256 is
  `3c4b14e106525adcd4c40c48b82f1d11ae870ef85f5c14f5d0d7635ea1442585`.
- Production `bot_enabled` is temporarily `false`. The mode-0600 environment
  backup is
  `/opt/noor/.hotfix-backups/env-20260901T104712Z-before-test0665-restore`.
  Both Wazzup channel variables now match the active WhatsApp channel ending
  0665, and `TEST_CHANNEL_RESTORE_MODE=true`; app and worker are still stopped.
- The deploy candidate now adds an app-only CI gate plus restore mode: Telegram
  startup/inbound is disabled, and worker registers only fresh inbound handling
  with no cron jobs or embedding warmup. Its focused additions passed 34 tests.
- Final independent review found one P1 in the general app-only contract: an
  already-running worker was not explicitly stopped. The deployer now stops it
  before replacing files and aborts unless a readback proves no worker remains.
  Five focused deploy tests pass; review found no other issues.

## Technical premortem

Verdict: GO WITH CONDITIONS.

- Never start the old containers: their environment contains prohibited9235.
- Deployment must create new containers from one exact accepted release SHA.
- Preserve retained Redis/ARQ data but prevent it from executing. Do not replay,
  delete or inspect customer message bodies.
- Set both Wazzup sender variables to the exact test0665 UUID only after a
  protected environment backup. Missing/mismatched outbound authorization must
  fail closed.
- App may start before worker for content-free health. Worker starts only after
  retained-work isolation and exact environment/image readback.
- Only an owner-sent fresh message after recovery may prove reply delivery.
- Roll back by stopping app/worker, restoring the protected release/environment
  and retained-work namespace, then recreating only app/worker. DB/Redis/nginx
  and neighboring products are never restarted.

## Explicit defers

- Fresh-message proof waits until the exact release is healthy and root asks the
  owner for one new message. No manual send or historical replay is permitted.

docs-reviewed: updated - new current stage records recovery and rollback scope.
graph-reviewed: no-change-needed - no graph is available in this worktree.
