# Final Feedback And Referral Acceptance Note

Date: 2026-04-30
Stage: `tj-final27`
Beads: `tj-final27.5`, `tj-final27.6`

## Post-Delivery Feedback

Post-delivery feedback is acceptance-ready for local verification:

- only active delivered-order conversations with deal/order evidence can enter the feedback-request path;
- the request window remains 24-48 hours after `deal_delivered_at`;
- each conversation gets a deterministic `crmMessageId` in the form `feedback:<conversation_id>:request`;
- successful or provider-duplicate sends are recorded in conversation metadata under `feedback_request`;
- customer feedback can be saved only from the delivered feedback context and remains one row per conversation;
- `/dashboard` shows feedback KPIs and the operator center reads recent feedback rows from the protected admin API.

No live WhatsApp feedback branch was run in this worker stream.

## Referrals

No approved referral business policy was found in repo docs/config. The referral launch path is therefore explicitly blocked pending client decision.

Search refresh, 2026-05-26: a repeat search across client docs, stage artifacts, handoff notes, and Beads found no client-approved referral mechanics. The durable client-facing materials only define referral scope and request the missing parameters: new-customer discount, referrer bonus, and activation conditions. Internal implementation defaults or prompts are not treated as client approval.

Default referral policy state:

- `status`: `client_decision_required`
- `approved`: `false`
- `enabled`: `false`
- customer-visible confirmation is required before any future launch

The protected referral API and LLM tools now read the policy before generating or applying referral codes. With default settings they return a client-decision/manager-confirmation message and do not apply discounts.

The low-level referral service remains available for future approved-policy implementation and existing internal tests, but launched callers are policy-gated.

## Client Decision Needed

To launch referrals later, the client must approve:

- referrer bonus and new-customer discount;
- eligibility and abuse checks;
- expiry and reuse rules;
- whether discounts affect quotation/SaleOrder price, reporting only, or manager approval;
- admin/reporting expectations;
- live E2E permission for the referral branch.
