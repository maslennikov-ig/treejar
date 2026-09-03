# Test-only authority correction and containment

## Current owner decision

On 2026-08-28 the owner identified only WhatsApp ending **0665** as the test
number and prohibited use of other numbers. The previously selected active
Treejar Trading channel ending **9235** is outside the authorized test scope.
The root's earlier incident attribution and channel selection were wrong.
The prior frozen scope snapshot and execution artifact remain unchanged as
historical evidence; neither authorizes use of 9235 now.

The owner then explicitly approved stopping only the Treejar app and worker,
preserving the database, queue and neighboring products, and preparing a safe
return to the approved test number. No real-user test send, replay, provider
registration change or new-channel authorization was requested.

## Observed effect and limits

- Since the switch at 2026-08-27 13:57:44 UTC: 33 `bot_reply` rows across
  12 conversations, plus 12 `product_media` rows across 2 conversations, had
  status `sent`. These are audit counts, not proven deliveries or unique media.
- The audit model does not store an independently immutable sender channel.
- Status callbacks reached the app, but 39 errors in the observed 24 hours
  reported an aware/naive datetime comparison failure. Missing terminal status
  cannot currently be attributed only to Wazzup.
- Before containment, Redis had 9 buffered incoming items and one in-progress
  key. An in-progress key is not proof of an active send. No queue payloads were
  exported or replayed, and no queue keys were deleted.

## Executed containment

At **2026-08-28 16:45:11 UTC**, root verified exact Compose project/service
labels, stopped `noor-worker-1` and `noor-app-1` with timeout zero, and changed
their restart policy from `unless-stopped` to `no`.

Readback at 16:45:12 UTC: both containers `exited`, `Running=false`, restart
policy `no`. `noor-db-1`, `noor-redis-1` and `noor-nginx-1` retained the same
container IDs and start timestamps and remained running.

At **16:48:01 UTC**, root made a mode-0600 backup at
`/opt/noor/.codex-backups/tj-stwf-before-test-only-20260828T164801Z.env`, then
restored only the `WAZZUP_CHANNEL_ID` line in `/opt/noor/.env` to
`b49b1b9d-757f-4104-b56d-8f43d62cc515`. Byte comparison excluding that line
confirmed all other content unchanged. Both containers remained stopped.

The stopped containers still contain their old environment. **Never start or
unpause them.** New containers from a reviewed safe artifact and corrected env
are required for eventual recovery. Do not restore the unsafe running state
merely because the public API is unavailable: downtime is intentional here.
Already-submitted provider requests cannot be recalled by stopping processes.

## Technical premortem for recovery

Verdict: **GO WITH CONDITIONS for local preparation; HOLD live startup.**

- Only core chat checked `bot_enabled`; background jobs and direct Telegram
  callbacks could bypass it. Both app and worker must remain stopped until a
  common outbound guard is verified.
- Some background senders omitted `channelId`; changing the default channel
  alone was not an isolation guarantee. Require explicit allowed sender scope.
- Telegram callbacks could use an old conversation's recipient with a new
  configured sender. Verify the conversation's inbound channel before sending.
- Guard before any provider HTTP call or public media upload, and recheck
  before retries/caption sends. A disabled/missing/foreign authorization must
  not become an audit row marked sent.
- Preserve queues and existing data. Do not run old batches to drain them.
- Executor-error control: exact phone-to-channel identity is owner-confirmed;
  channel activity alone is never evidence of test authorization.
- Test 0665 was `qridle` at the last provider readback. Its WhatsApp owner must
  reconnect it through the Wazzup QR flow. A config edit cannot do that.

## Current acceptance, separate from superseded historical scope

1. Non-test outgoing execution remains stopped; neighboring services unchanged.
2. Disk configuration targets only the authorized test channel; old containers
   remain stopped and cannot auto-restart.
3. Local tests prove common disabled/foreign/missing authorization denial for
   text/media/template and background/manager paths, and an allowed test reply.
4. Status persistence handles PostgreSQL timezone-aware values correctly.
5. Independent security review approves the local change before any release.
6. Live acceptance remains open until test QR reconnection, controlled safe
   startup, and one fresh owner-sent test message with a correlated reply.

No merge to auto-deploying main or service start is part of local preparation.
