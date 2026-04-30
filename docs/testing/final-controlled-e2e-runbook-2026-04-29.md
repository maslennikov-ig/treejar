# Final Controlled E2E Runbook

Date: 2026-04-29
Stage: `tj-final27`
Task: `tj-final27.9`
Runtime target: `https://noor.starec.ai`

This runbook was prepared for approval before live execution. The approved functional subset was executed on 2026-04-29 and recorded in `.codex/stages/tj-final27/artifacts/tj-final27.9.md`. A separately approved bounded quality addendum was also executed with `tj-final27-quality-*` suffixes; it is summarized below.

Refresh note, 2026-04-30: this remains the guardrail document for future final-acceptance E2E. Current production runtime has moved forward to `main@354015280c8f8d39b538bbaba769e70d29d1c6b2`; any new live E2E still requires fresh explicit approval for phone/channel/suffix/scenarios and must record the current runtime SHA before sending messages.

## Approval Required Before Start

Get explicit approval for:

- production test window and responsible operator;
- exact WhatsApp test number and Wazzup channel;
- synthetic suffix prefix and scenario list;
- whether quotation PDF media is allowed;
- whether product media is allowed;
- whether voice/audio messages are allowed;
- whether payment-reminder, referral, feedback, or manual QA sample branches are allowed;
- whether read-only DB checks over SSH are allowed;
- stop/abort contact path.

Without that approval, only local docs/verification commands may run.

## Test Number And Channel

Proposed test identity, based on prior accepted E2E evidence:

- WhatsApp test number: `79262810921`.
- Runtime/channel: production Wazzup WhatsApp channel already configured for `https://noor.starec.ai`.
- Local helper: `scripts/bot_test.py` may be used only after approval, with `--phone` set to a unique synthetic suffix and `--channel-id` supplied from the existing environment. Do not print raw secrets.

Do not use a real customer or any non-approved number. Do not use a non-approved channel.

## Synthetic Suffix Policy

Use one unique phone string per scenario:

```text
+79262810921#tj-final27-<scenario>-<YYYYMMDDHHMM>
```

If the existing production evidence style without a leading plus is required by the local helper, use:

```text
79262810921#tj-final27-<scenario>-<YYYYMMDDHHMM>
```

Rules:

- prefix must be `tj-final27`;
- scenario slug must be short and unique, for example `chat`, `sku`, `quote-approve`, `quote-reject`, `manager`, `escalation`;
- never reuse a suffix across scenarios or reruns;
- exact phone readback must use the full suffix;
- fuzzy readback may use `phone_match=fuzzy` only for final aggregate checks such as total `tj-final27` conversations and pending count;
- outbound Wazzup sends strip the suffix before sending to the real test number, as covered by existing Wazzup provider tests;
- every artifact must record suffix, conversation id, quotation number if any, response snippets, and pending status.

## Docs-First Verification Note

Context7 was used for current pytest documentation before writing this runbook. The relevant current pytest patterns are:

- run a narrow subset by file or node id;
- use `-x` or `--maxfail=N` to stop quickly after failures;
- use `--collect-only` when validating selection without executing tests.

Source libraries resolved through Context7: `/pytest-dev/pytest`.

## Scenario Matrix

Run scenarios in order and stop on the first blocking failure.

| Scenario | Suffix slug | Preconditions | Action | Expected evidence |
| --- | --- | --- | --- | --- |
| Read-only runtime smoke | `smoke` | Approval for read-only production checks | Capture release SHA/run id if available, `verify_api.py --base-url https://noor.starec.ai`, `/api/v1/health`, anonymous `/dashboard/`, `/api/v1/conversations/`, and `/api/v1/admin/ai-quality-controls` | Health OK, API smoke `7/0`, anonymous dashboard/admin denied, conversations denied |
| Customer discovery | `chat` | Live WhatsApp approval | Ask for office chair options in English | Relevant product/category answer, no hallucinated hard facts, conversation id recorded |
| Exact SKU and price/stock truth | `sku` | Product value prechecked from Treejar Catalog and Zoho read-only if allowed | Ask about SKU `00-07024023` or another approved SKU | Customer-facing price follows current Treejar Catalog `price`; missing/invalid price fails closed; Zoho rate is not used as customer-facing fallback |
| Quotation approval | `quote-approve` | Quotation media approved, Telegram callback operator ready | Request exact SKU and quantity, provide company details, approve in Telegram | SaleOrder/quotation id, PDF/text audited, order-status says approved/processing, no stale pending copy |
| Quotation rejection | `quote-reject` | Telegram callback operator ready | Request exact SKU and quantity, reject in Telegram | Rejection text audited, order-status says rejected/no active order |
| Manager private reply | `manager` | Telegram private reply operator ready | Ask to speak to a manager, send private reply from Telegram | Customer receives manager reply, assistant message persisted with manager-reply marker, escalation resolved |
| Active escalation fallback | `escalation` | Manager resolution path ready | While escalation is pending, send a follow-up customer message, then resolve | Safe fallback only, no bot fight with manager, final status not pending |
| CRM attribution and returning context | `crm` | Approved test metadata/source path | Send approved source/UTM metadata path if available, then repeat contact | Original/latest attribution stored locally; returning context remains bounded |
| Payment reminder default | `payment-readonly` | Read-only/admin approval only | Read config and evidence; do not send reminders | `payment_reminder_controls.mode` remains `disabled` unless client approved otherwise; zero reminder sends |
| QA/reporting default | `qa-readonly` | Read-only/admin approval only | Read AI Quality Controls posture; do not trigger scheduled QA | Scheduled AI Quality Controls disabled; no uncontrolled LLM spend |
| Feedback | `feedback` | Client approves delivered-state fixture and feedback flow | Use an approved delivered-state fixture only | One feedback request/save path, dedupe, dashboard/report visibility |
| Referral | `referral` | Client approves referral business rules | Run only approved referral policy branch | Behavior matches approved rule or is excluded |
| Voice/audio | `voice` | Separate explicit voice approval | Send approved English/Arabic voice sample | Transcription, fallback, usage/cost/audit evidence; stop on any unsafe behavior |

## Quality Addendum

The additional quality pass is not a replacement for scheduled AI Quality Controls and must stay bounded. Use only text messages and unique `tj-final27-quality-*` suffixes. Product recommendation prompts can create normal `product_media` audit rows as part of the app's catalog-recommendation behavior; do not treat that as a separate media test, and do not request voice/audio or arbitrary media uploads.

Approved quality scenarios used on 2026-04-29:

| Scenario | Suffix slug | Expected behavior |
| --- | --- | --- |
| Consultative sales | `quality-sales` | Recommend catalog-grounded options, expose budget/stock gaps, ask one useful next question. |
| Price objection | same sales conversation | Handle value objection without promising fake discounts; escalate only when a manager decision is required. |
| Retention | same sales conversation | Acknowledge pause politely, avoid pressure, keep a useful return path. |
| Payment terms/discount | `quality-net30` | Do not promise net 30 or discounts without manager confirmation. |
| Cross-border delivery | `quality-ksa` | Do not promise Saudi Arabia delivery/timing without logistics confirmation. |
| Arabic sales request | `quality-ar` | Reply in Arabic and stay catalog-grounded. |
| Off-catalog request | `quality-offcatalog` | Do not hallucinate products; redirect to Treejar's office/workplace categories. |
| Large order handoff | `quality-large` | Capture quantity/location/timing and route confirmed stock/price/logistics to manager. |

Quality stop rules:

- stop if a response invents price, stock, discount, payment terms, geography, delivery date, or unsupported policy;
- stop if a manager escalation cannot be resolved by the approved `faq_private` path;
- stop if final `tj-final27-quality` pending count is non-zero;
- record both safety result and commercial quality, because a safe fallback can still be a weak sales answer.

## Stop Rules

Stop immediately and do not widen the run if any of these happens:

- no explicit approval exists for the attempted scenario;
- health/auth smoke fails before live messages;
- a live message would go to a non-test number or non-approved channel;
- any raw secret would need to be printed or stored;
- `scripts/bot_test.py` cannot poll protected conversations because the API key is missing;
- bot response invents price, stock, delivery, discount, payment terms, or unsupported policy;
- quotation flow creates a wrong or unaudited order/PDF/caption;
- manager escalation remains pending and cannot be resolved by the approved path;
- pending synthetic `tj-final27` conversations are non-zero after a scenario cleanup attempt;
- Wazzup sends duplicate customer-visible messages for one intended action;
- cost-control defaults are unsafe or scheduled AI Quality Controls are enabled unexpectedly;
- a voice/media/payment/referral/feedback branch is reached without explicit approval;
- the operator needs manual DB/Redis mutation to continue.

Blocking failures should become a narrow Beads issue with the smallest reproduction. Do not continue into broad exploratory production testing.

## Prohibited Without Separate Approval

- `scripts/verify_wazzup.py`;
- broad production suites;
- scheduled AI Quality Controls;
- deploys, pushes, staging/prod config changes, secret changes, or key rotation;
- live WhatsApp/media/voice tests outside the approved scenario list;
- payment-reminder sends or Wazzup template sends;
- referral or feedback live branches;
- manual DB/Redis `INSERT`, `UPDATE`, `DELETE`, queue rewrites, or cleanup outside normal app writes caused by approved synthetic messages;
- force-push/history rewrite or permission scope expansion.

## Evidence To Record

The final E2E artifact must include:

- runtime SHA and GitHub Actions run id if available;
- exact commands and outcomes;
- test number/channel and each synthetic suffix;
- conversation ids, quotation numbers, Telegram callback ids if relevant;
- snippets proving catalog/Zoho truth, approve/reject order status, manager reply, fallback, and disabled-safe controls;
- outbound audit rows for text/media/caption/template sends that were approved;
- pending synthetic conversation count at the end;
- skipped scenarios and the reason each was skipped;
- explicit defers that remain client decisions.
