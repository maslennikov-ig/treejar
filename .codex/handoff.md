# Orchestrator Handoff

Updated: 2026-09-03
Current branch: `main`
Current stage id: `tj-stwf-test-only-restore`
Status: ACCEPTED AND DEPLOYED. Production testing is enabled only for WhatsApp
ending0665.

## Current truth

- Release `af93ebd5a07d50e1689df76a28d465ddbbec2c17` passed the full root
  closeout and GitHub Actions run `33759923277`.
- Public health reports the exact release with healthy PostgreSQL and Redis.
- App `7b36af77e0c5` and worker `5dc6ccec0c99` are running from that release
  with zero restarts and no OOM event.
- `WAZZUP_CHANNEL_ID` and `WAZZUP_OUTBOUND_ALLOWED_CHANNEL_ID` both resolve
  only to test0665. `bot_enabled=true` and
  `TEST_CHANNEL_RESTORE_MODE=true`.
- The production main model is `z-ai/glm-5.3-flash`.
- One fresh owner-authored message produced one user row and one assistant row
  using `z-ai/glm-5.3-flash|verified-policy-clarify`. The outbound audit shows
  one sent Wazzup message on test0665 with a provider message id and zero
  foreign egress.
- Live inbound and ARQ queues are empty. All nine historical inbound lists stay
  preserved under `hold:tj-stwf:20260901T104616Z:`; do not replay, delete or
  inspect them.
- PostgreSQL `43ccb64efb9d`, Redis `1b9c9a5c99d0` and nginx
  `0cdbce63c5db` were preserved with zero restarts and no OOM event.
- Rollback environment backup:
  `/opt/noor/.hotfix-backups/env-20260901T104712Z-before-test0665-restore`.
- The accepted candidate worktree and its merged local branch were removed.
  Production runtime and the rollback backup were untouched.

## Verification

- Ruff, format and Mypy passed.
- Full pytest: 3,925 passed and 20 skipped.
- Concurrency: 104 passed; security: 65 passed; database/migration: 13 passed;
  integration: 174 passed.
- Process verification, stage readiness, documentation review and blocking
  findings checks passed.
- GitHub Actions and app-only deploy:
  `https://github.com/maslennikov-ig/treejar/actions/runs/33759923277`.

## Operating boundary

The worker remains running for production testing on test0665. Restore mode
intentionally disables Telegram, cron jobs, embedding warmup and every
non-test channel. Normal multi-channel operation requires a separate release.

## Explicit defers

- Wazzup sender authentication enforcement remains a long-term backlog task.
- The paid five-call route verifier and paid second reader were not used.
- Existing unrelated product defects remain in their own tracked tasks.
- Referral activation remains an excluded client decision.
- Reader-gap drift remains tracked in `tj-4q79`.

## Next recommended

Next stage id: `none` (accepted stage is complete)
Recommended action: keep production testing limited to test0665. Open a new
stage only when normal multi-channel operation or a deferred item is explicitly
scheduled.

## Starter prompt for next orchestrator

Use $orchestrator-stage only for a newly authorized production change. Treat
`tj-stwf-test-only-restore` as accepted history, preserve the test0665-only
boundary and held-message namespace, and obtain fresh authority before deploy
or any broader channel activation.

docs-reviewed: updated - accepted release and live evidence recorded.
graph-reviewed: no-change-needed - no graph is available in this worktree.
