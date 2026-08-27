# Stage tj-stwf-prod-wazzup-channel

Status: in progress.

## Incident

At 13:09-13:11 UTC, eight tester-time inbound messages reached Noor through the
active `Treejar Trading` Wazzup channel but were rejected before Redis, ARQ, the
database, or the model because production expected the disconnected `Treejar`
channel. Twenty-one messages were rejected by the same guard over two hours.

## Technical premortem

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

## Explicit defers

- Fresh-message acceptance waits for a new tester message after the switch.
