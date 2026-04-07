# Inbound Channel Phone Gating Design

**Date:** 2026-04-07
**Status:** Approved
**Related task:** `tj-8cs3`

---

## Problem

Telegram alerts for escalations and manager quality reviews are currently sent for all eligible conversations within the configured Wazzup project/channel scope. The business requirement is narrower: alerts must only be sent for conversations that arrived through the test inbound WhatsApp number `+971551220665`.

The current webhook payload gives us `channelId`, but not the human-readable inbound phone number. Using only `channelId` in business logic would hardwire an internal transport identifier instead of the domain concept we actually care about.

## Decision

Introduce a first-class conversation attribute in metadata:

- `inbound_channel_id`
- `inbound_channel_phone`

The runtime will resolve `channelId -> plainId` via the Wazzup channels API, normalize the number into a stable E.164-like form, and persist both values into `Conversation.metadata`.

Telegram alerts will be gated by `inbound_channel_phone`, compared against a new environment-backed setting containing the allowed inbound phone. If the inbound phone cannot be determined, alerting fails closed.

## Scope

- Read `channelId` from incoming Wazzup webhook messages.
- Resolve channel phone via Wazzup API.
- Persist inbound channel metadata on conversations.
- Gate Telegram escalation alerts.
- Gate low-score manager review alerts.

## Non-goals

- No database migration. Existing JSON conversation metadata is sufficient.
- No change to general message processing or WhatsApp reply routing.
- No attempt to infer inbound phone from historic conversations that lack channel metadata.

## Data Flow

1. Wazzup webhook receives message with `channelId`.
2. Batch processor filters by configured project channel as before.
3. For the surviving message batch, the runtime resolves `channelId` via Wazzup channels API.
4. The runtime stores:
   - `metadata.inbound_channel_id`
   - `metadata.inbound_channel_phone`
5. Escalation and manager-review notification paths check whether `metadata.inbound_channel_phone` equals the configured allowed inbound phone.
6. If yes, Telegram alert is sent. If no or unknown, Telegram alert is skipped.

## Safety Rules

- Normalize numbers before comparison so user input like `+971 55 122 0665` matches stored values.
- If channels API lookup fails or returns no phone, do not send the alert.
- Preserve escalation DB state even when Telegram notification is suppressed.

## Test Strategy

- Unit test Wazzup channel phone resolution.
- Unit test persistence of inbound channel metadata during batch processing.
- Unit test escalation notification suppression for non-allowed inbound phones.
- Unit test manager low-score alert suppression for non-allowed inbound phones.
