# WhatsApp tester ingress incident — 2026-10-12

Task: `tj-spg1`. Owner requested diagnosis and immediate repair.
Status: direct callback restored; provider transport verified; fresh customer
reply and delivery remain unverified.
Diagnosis collected around 14:47–14:52 Moscow time; repair applied at 14:56.

## Findings

- Canonical runtime `/opt/noor` reports release
  `25a8c080e9b014333380b8e62be7d5e981daefe7`. App, worker, PostgreSQL,
  Redis and nginx are running. Health reports database/Redis `ok`.
- `bot_enabled=true`, `TEST_CHANNEL_RESTORE_MODE=true`. Configured sender
  and outbound allowlist both match Wazzup channel
  `b49b1b9d-757f-4104-b56d-8f43d62cc515`, phone ending `0665`.
- Wazzup `GET /v3/channels`: the approved WhatsApp test channel is `active`.
- ARQ queue is empty. Latest persisted user/assistant messages and outbound
  audit rows are from 2026-09-30. No recent customer turn reaches Noor.
- Before repair, Wazzup `GET /v3/webhooks`: callback host was `audit.treejartrading.ae`,
  path `/webhook`; a secret-bearing query is present and intentionally omitted.
  Subscriptions: `messagesAndStatuses=true`, `channelsUpdates=true`,
  `contactsAndDealsCreation=false`, `wabaTemplatesStatus=false`.
- The direct Noor callback
  `https://noor.starec.ai/api/v1/webhook/wazzup` responds HTTP 200 with
  `{"ok":true}` to `{"test":true}`. Noor logs confirm the test ping arrived.
- The configured audit callback also responds HTTP 200 to a test ping and an
  empty messages/statuses event. Neither probe appears in Noor callback logs.
  This demonstrates no forwarding of these probes; actual customer payload
  forwarding remains unverified without access to the audit service.
- Free OpenRouter key metadata request: HTTP 200, positive key limit remaining.
  No paid completion was run. Model availability/completion is not inferred.

The callback routed Wazzup events to the audit service instead of directly to
the sales bot. Other active channels exist in the same Wazzup account. The
owner explicitly decided that audit capture is not required and requested
returning events directly to the bot.

## Applied repair and acceptance

- Re-read the current provider configuration and compared callback and
  subscriptions against the private backup before mutation; both matched.
- Verified the Noor callback preflight with a harmless test ping: HTTP 200.
- Changed `webhooksUri` with `PATCH /v3/webhooks` to
  `https://noor.starec.ai/api/v1/webhook/wazzup`; HTTP 200.
- Immediate `GET /v3/webhooks` readback confirmed the exact callback and all
  four original subscription values unchanged.
- At `2026-10-12T11:56:26.123Z` (14:56:26 Moscow), Noor received Wazzup's
  registration test from `94.242.234.196`; HTTP 200. This is provider-to-bot
  transport evidence, distinct from the local preflight at 11:56:25.992Z.
- A subsequent configuration read confirmed the callback remained correct.
  The test channel remained active, restore mode and sender allowlist remained
  intact, and app/worker were running with zero restarts and no OOM.
- Health remained on the same release, database and Redis `ok`.

No new tester message has been observed during acceptance. `tj-spg1` retains
the explicit remaining criterion: fresh inbound tester message, generated reply,
correlated Wazzup provider ID and delivered/read status or tester confirmation.
The transport repair does not establish a model response or customer delivery.

## Rollback

- A private copy of the original webhook response is stored at
  `/opt/noor/.hotfix-backups/whatsapp-ingress-20261012/webhooks-before.json`,
  mode `0600`, SHA-256
  `fe630a6e797bd991ea534f61e7cfd157c78f407aa79283cd44277cfa76ab4b48`.
  The original query secret stays outside Git and this report.
- Restore the original `webhooksUri` and subscriptions from the private backup
  if the direct callback change needs rollback. Verify current configuration
  before changing it and perform a fresh provider readback afterward.

The only external configuration mutation was the owner-approved Wazzup callback
repair. No deployment, customer reset, queued-message replay, paid model call
or synthetic outbound customer message was performed. Probe bodies contain
no customer text. Source and running images were unchanged.

Official API reference: https://wazzup24.com/help/api-en/webhooks/
