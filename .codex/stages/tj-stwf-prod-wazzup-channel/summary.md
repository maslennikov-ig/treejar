# Stage tj-stwf-prod-wazzup-channel

Status: REPLAN REQUIRED. The owner confirmed on 2026-08-28 that only test
WhatsApp ending 0665 may be used. The earlier switch to 9235 was based on an
incorrect identity assumption and is not accepted. See
`containment-2026-08-28.md`; the older observations below are historical.

## Current local preparation

The safety candidate is in `codex/test-channel-safety`, not deployed. Shared
outbound denial, channel-scoped conversations and UTC status handling passed
130 root-owned affected tests, Ruff, formatting and Mypy. Independent security
re-review found no blocking issues after correcting old-conversation rebinding.
See `artifacts/tj-stwf-test-only-safety.md` for exact scope and evidence.

Production app/worker remain stopped with auto-restart disabled. Disk config
targets only test0665; old stopped containers must never be started. Provider
readback at 17:00:25 UTC still requires the owner to reconnect0665 via QR.
Stage and live reply acceptance remain open. No release or stage close occurred.

docs-reviewed: updated - README, current handoff, containment and safety evidence.
graph-reviewed: no-change-needed - no graph in this worktree; no extraction.

## Historical incident (superseded channel assumption)

At 13:09-13:11 UTC, eight incident-adjacent inbound messages reached Noor through the
active `Treejar Trading` Wazzup channel but were rejected before Redis, ARQ, the
database, or the model because production expected the disconnected `Treejar`
channel. Twenty-one messages were rejected by the same guard over two hours.
Their attribution to the tester was never proven and has been withdrawn.

## Historical technical premortem (not current authority)

Verdict: GO WITH CONDITIONS.

- Re-read provider channel state immediately before mutation; proceed only if
  `Treejar Trading` is active and the prior channel is still disconnected.
- Back up the exact `.env` with mode `0600` and verify only
  `WAZZUP_CHANNEL_ID` changes.
- Recreate app and worker together so inbound filtering and outbound sending use
  the same channel. Do not restart the database, Redis, nginx, or other products.
- Roll back by restoring the protected `.env` and recreating app and worker if
  either container fails, public health changes, or runtime readback mismatches.
- Do not replay the dropped events or send a real-user message. A fresh tester
  message is the only allowed end-to-end proof.

## Historical defer

- Fresh-message acceptance waits for a new tester message after the switch.

## Historical runtime result (before containment)

- Production `app` and `worker` now use the active Treejar Trading channel.
- Only the `WAZZUP_CHANNEL_ID` line changed; two exact mode-`0600` backups exist.
- Only app and worker were recreated. Database, Redis, nginx, and neighboring
  products were not restarted.
- Public health is `ok` at unchanged release `43d6430`; Redis and PostgreSQL are
  healthy, and both recreated containers have restart `0` and OOM `false`.
- Previously dropped events were not replayed or manually answered.
- No fresh tester message arrived during the bounded post-switch observation,
  so end-to-end reply proof remains pending.
