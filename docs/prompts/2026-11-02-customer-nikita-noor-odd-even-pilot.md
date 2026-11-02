# Customer developer handoff v2: Nikita / Noor odd-even Moscow-day pilot (`2026-11-02`)

Supersedes the pending-choice placeholders in `docs/prompts/2026-10-31-customer-claude-noor-pilot.md` with the business choices submitted by Viktor and Julia on `2026-11-02 16:14 MSK` (`docs/client-answers/noor-nikita-pilot-2026-10/responses-2026-11-02.{json,md}`).

## 1. Confirmed business rules (`2026-11-02`)

- **Eligible population (`pilot_scope`):** **New customers only** arriving after agreed activation. All pre-existing / open conversations stay with their current owner (Nikita or human manager) and are **never** forwarded to Noor.
- **Assignment rule (`routing_method` + `even_days_owner` + `pilot_timezone`):**
  - Evaluate the calendar day-of-month in **`Europe/Moscow` (`UTC+3`)** at the timestamp of the **first inbound message** of an eligible new customer conversation:
    - **Even day-of-month (`day % 2 == 0`):** durable owner = **`nikita`**
    - **Odd day-of-month (`day % 2 == 1`):** durable owner = **`noor`**
- **Sticky dialogue ownership:** Once assigned on first eligible message, the conversation retains that exact owner across midnight (`00:00 MSK`), retries, and process restarts. Midnight **never** switches an open dialogue's assistant.
- **Pilot window:** `14 calendar days` (desired start date `2026-11-03`, gated on joint pre-launch test completion and explicit activation sign-off).
- **Allowed Noor scope (`noor_actions`):** Catalog selection, live stock & VAT calculation, and PDF quotation on explicit customer request; order confirmation, invoicing, and payment stay with the human manager.
- **Treejar operational & stop owner:** Julia (`@youpyoupp`); joint outcome review by Viktor & Julia across all 6 metrics (accuracy, communication quality, response speed, quote rate, client-confirmed payment rate, clean manager handoff with zero double replies).
- **Still pending client confirmation (`noor-pilot-final-check-2026-11`):**
  1. `crm_write_scope` choice (`Contact + New Lead Deal + Draft Quote` vs `Contact + Draft Quote only` vs `Read-only`).
  2. Julia's delivery & assembly tariff rules file (until loaded into KB, Noor states delivery/assembly charges are confirmed by the manager).

## 2. Receiver & final-send contract on Nikita's side

1. **Durable assignment table:** Keyed by `(channel_id, normalized_chat_id)` in persistent storage (PostgreSQL/SQLite/Redis with persistence — not process memory). Pre-populate or gate by `pilot_started_at` so chats with prior history before `pilot_started_at` resolve to `existing_pre_pilot` (`nikita` / human) rather than creating a new assignment.
2. **Final-send fencing for Nikita:** Check durable owner immediately before **every** Nikita outbound Wazzup call (initial greeting, main reply, queued retries, scheduled follow-ups). If `owner == "noor"` or `manager_taken_over == true`, suppress Nikita's send and cancel scheduled follow-ups.
3. **Webhook forwarding to Noor (`owner == "noor"`):**
   - Endpoint: `POST https://noor.starec.ai/api/v1/webhook/wazzup`
   - Header: `Authorization: Bearer <WAZZUP_WEBHOOK_SECRET>` (exchanged out-of-band via Igor; never hardcode in public files)
   - Payload: forward original Wazzup JSON event untouched (`channelId` ending `...9235`, `chatId`, `messageId`, `authorType`, `isEcho`, `dateTime`, `type`, `text`, media fields, and outbound status updates). Do **not** rewrite `channelId` to `...0665`.
   - **Include manager echo events (`isEcho: true` / `authorType: "manager"`):** Noor uses these to transition `escalation_status -> "manual_takeover"` immediately so neither bot double-replies after Julia or another manager writes.
4. **Emergency stop switch:** A single runtime config flag (`PILOT_NOOR_ROUTING_ENABLED=false`) routes new conversations back to `nikita` immediately without replaying historical messages.

## 3. Required Noor-side activation checklist (do NOT execute without explicit owner authorization)

Noor currently remains in `TEST_CHANNEL_RESTORE_MODE=true` with `WAZZUP_CHANNEL_ID` / `WAZZUP_OUTBOUND_ALLOWED_CHANNEL_ID` pinned to `test0665`. When joint pre-launch testing and owner activation are explicitly authorized:
1. Snapshot `/opt/noor/.env` and DB `system_configs` into `/opt/noor/.hotfix-backups/tj-r62i-<timestamp>/`.
2. Apply Viktor & Julia's confirmed `crm_write_scope` setting and load Julia's delivery/assembly tariff KB entries if received.
3. Configure inbound/outbound authorization for business channel `...9235` and `TEST_CHANNEL_RESTORE_MODE` per the approved activation plan while keeping `WAZZUP_WEBHOOK_GUARD_ENABLED=false` so Noor never overwrites the customer's global Wazzup webhook URL.
4. Run the 4 isolated live pre-start checks (Nikita-owned chat + duplicate `messageId`; Noor-owned chat + zero Nikita greeting/follow-up; across-midnight stickiness; manager echo takeover + pilot stop switch) before opening customer traffic.
