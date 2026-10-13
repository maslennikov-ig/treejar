# WhatsApp callback recurrence and live delivery — 2026-10-13

Task `tj-spg1` restored and verified; competing configuration changes tracked
in `tj-vqcc`. Actor and automatic/manual mechanism remain unknown.

## Diagnosis and restoration

At approximately 17:04 Moscow, Wazzup again registered
`audit.treejartrading.ae/webhook` with the same secret-bearing query and all
four subscriptions as the private pre-repair backup from October 12. The
full private response hash was unchanged:
`fe630a6e797bd991ea534f61e7cfd157c78f407aa79283cd44277cfa76ab4b48`.
This proves another reversion after yesterday's successful direct readbacks.

Noor still runs `25a8c080`, healthy database/Redis, bot enabled, active test
channel `0665`, matching sender/allowlist, empty ARQ queue. Latest persisted
customer turn was still September 30 before today's natural test. Deployed
`src/` and `scripts/` contain no Wazzup callback reconfiguration code.

Yesterday's post-repair callbacks reached Noor until 17:36:10 Moscow, including
foreign-channel events correctly rejected by the test-channel guard. That
last observation is not the exact callback-change timestamp.

Existing owner authority explicitly chose direct routing and no audit capture.
Saved today's private provider response at mode `0600`:
`/opt/noor/.hotfix-backups/whatsapp-ingress-20261013T140515Z/webhooks-before.json`.
Compared the provider state again before applying `PATCH /v3/webhooks` at
17:05:19 Moscow: HTTP 200; immediate readback confirmed the direct Noor URL
and unchanged subscriptions. Wazzup's own registration test reached Noor.
Seven readbacks at 30-second intervals from 17:05:59 through 17:08:59 all
retained the correct URL. This bounded observation proves three-minute
stability, not permanent protection against the competing writer.

## Natural owner-message acceptance

Owner sent the following from a number ending `0921`:
“Good day, could you please tell me if you have any new tables?”

| Event | Moscow time | Evidence |
| --- | --- | --- |
| Actual inbound arrival | 17:06:32.101 | Noor webhook HTTP 200 |
| Batch processing start | 17:06:37.476 | ARQ job for `ib1_29ced826a9c74fd3d391fd3f` |
| Text reply sent | 17:07:16.210 | Provider ID `1c9a65b2-efe4-4799-8029-f106d07b890d` |
| Three product images sent | 17:07:16–17:07:20 | Three distinct provider IDs |
| Whole batch completed | 17:07:20.246 | ARQ success; queues and processing lists empty |

Conversation `01089560-500f-4c41-931c-1a6c324b8e29` persisted the exact owner
message and a `gpt-6-luna` answer offering three table options. Text began
“Good day! Here are three table options”. Arrival-to-text-send was approximately
44 seconds; Wazzup's inbound message timestamp is minute-truncated and is not
used to calculate processing latency.

The owner explicitly confirmed: “Да, ответ и фото пришли”. Provider audit rows
still said `sent` at inspection; actual receipt is established by that owner
confirmation, not inferred from the audit status alone.

No deployment, customer reset, replay, credential change or synthetic customer
message was performed. This was normal processing of the owner's fresh input.

## Remaining work

`tj-vqcc`: establish and stop the competing configuration writer, or apply the
separately approved protective reconciliation. Actor attribution is still unknown.
Do not treat the successful owner round trip as proof that future reversion is
impossible. Reverting today's operator change uses the private backup above,
after comparing current settings and with an owner decision about routing.
