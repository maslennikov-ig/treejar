# Stage tj-stwf-test-only-restore

Status: ACCEPTED. Production testing is restored only for WhatsApp ending0665.
The superseded9235 stage remains historical and unauthorized.

## Accepted evidence

- Release `af93ebd5a07d50e1689df76a28d465ddbbec2c17` passed root closeout:
  Ruff, format, Mypy, 3,925 tests with 20 skips, all risk groups and process
  verification.
- GitHub Actions run `33759923277` passed and completed the app-only deploy.
- Public health reports the exact release; PostgreSQL and Redis are healthy.
- App `7b36af77e0c5` and worker `5dc6ccec0c99` are running from the exact
  release with zero restarts and no OOM event.
- Both Wazzup channel settings authorize only test0665. Restore mode registers
  only fresh inbound processing and disables Telegram, cron jobs and embedding
  warmup.
- One fresh owner-authored message produced one user row and one assistant row.
  The assistant used `z-ai/glm-5.3-flash|verified-policy-clarify`; Wazzup
  recorded one sent message on test0665 with a provider message id and zero
  foreign egress.
- Live inbound and ARQ queues are empty. All nine historical lists remain
  preserved under `hold:tj-stwf:20260901T104616Z:`.
- PostgreSQL `43ccb64efb9d`, Redis `1b9c9a5c99d0` and nginx
  `0cdbce63c5db` were preserved with zero restarts and no OOM event.
- The protected pre-restore environment backup remains at
  `/opt/noor/.hotfix-backups/env-20260901T104712Z-before-test0665-restore`.
- The accepted candidate worktree and its merged local branch were removed;
  production runtime and the rollback backup were untouched.

## Operating boundary

The worker remains running for production testing on test0665. Do not replay
held messages or enable Telegram, cron jobs, embedding warmup or any other
channel as part of this accepted stage.

docs-reviewed: updated - current evidence and operating boundary recorded.
graph-reviewed: no-change-needed - no graph is available in this worktree.
