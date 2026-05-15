# Stage tj-e2e15: Long-Dialog Memory E2E Stress Test

Updated: 2026-05-15
Status: blocked by new production defect
Branch: `codex/tj-long-memory-e2e`
Base: `origin/main@7d3579cbf7b84826318d154cb98a3cdc3121db60`

## Goal

Run a separate production E2E stress test on the approved personal test number
`+79262810921` to check whether Noor preserves customer details, product
context, quantity changes, delivery, and assembly intent over a long dialogue.

## Scope

- Clean all matching production state for `79262810921%` before testing.
- Send a 10+ turn long-dialog scenario through the production webhook.
- Inspect the final transcript and database state.
- Record any memory loss, context loss, or unnecessary escalation in Beads.

## Result

The stress test failed before reaching the final memory-summary turns.

Production conversation `cb46ebcb-1c5a-41f4-a7d7-99e295f11ba7` showed:

- Turn 1 correctly returned the first-turn `name-gate` response.
- Turn 2 `Lili` correctly stored `customer_name=Lili` and resumed the original
  workstation/drawer planning request.
- Turn 3 `The company is Memory Test LLC.` incorrectly triggered
  `z-ai/glm-5|verified-policy` manager confirmation and created a pending
  escalation.
- Turns 4-6 returned fallback manager-notified responses instead of continuing
  the product/address/quantity planning dialogue.
- Turn 7 timed out while the conversation was already in pending escalation.

## Beads

- `tj-e2e15`: long-dialog memory production E2E stress test.
- `tj-e2e15.1`: executed and recorded the failed stress test.
- `tj-e2e15.2`: new P1 bug for customer-detail messages triggering
  verified-policy handoff during an active sales dialogue.

## Verification

- Production cleanup was executed in one transaction before the test:
  conversations/messages/outbound audits were reduced from `1/6/15` to `0/0/0`
  for the approved phone prefix.
- Live bot-test transcript was captured in
  `/tmp/tj-e2e15-long-memory-20260515T112355Z.log`.
- Production DB inspection confirmed `customer_name=Lili`,
  `escalation_status=pending`, one pending escalation, and fallback replies after
  the company detail message.

## Boundaries

- No production code was changed or deployed in this stage.
- Lili's real WhatsApp thread was not mutated.
- The approved personal test phone now contains the failed E2E transcript.
