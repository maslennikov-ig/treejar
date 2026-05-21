# tj-gh22 Post-Quotation Follow-Up E2E Plan

Date: 2026-05-21

Runtime target: `https://noor.starec.ai`

Runtime commit under test: `000dcfbc32c6a0084678c0582c983392e3b27ea6`

Delivery evidence:

- Branch `codex/tj-gh22-fu1-service-window` was fast-forwarded into `main`.
- GitHub Actions run `26233069352` completed successfully, including the `deploy` job.
- Production smoke passed: `uv run python scripts/verify_api.py --base-url https://noor.starec.ai` -> `7 passed, 0 failed`.
- Direct `/opt/noor/.release-sha` SSH check was not available from the local environment because SSH public-key authentication failed. Runtime evidence is therefore the successful GitHub Actions deploy plus production API smoke.

## Purpose

Validate the deployed post-quotation flow after the `tj-gh21` and `tj-gh22`
changes:

1. Noor asks whether the quotation works after sending a quotation.
2. Before customer acceptance, Noor continues answering normal customer questions.
3. Customer acceptance is handed off to a manager.
4. Proposal follow-up FU1 is scheduled at about 23 hours so it can use a normal
   WhatsApp text only when the real 24-hour customer-service window is still
   open.
5. FU2 and FU3 remain template-only because they are scheduled after 3 and 7
   days.
6. Customer-facing text is English or Arabic only.

## Execution Preconditions

Live WhatsApp E2E must not start until these are confirmed for the run:

1. Approved test number and channel. Use the existing controlled-test guardrail
   from `docs/testing/final-controlled-e2e-runbook-2026-04-29.md`; the usual
   approved number is `+79262810921`, with unique synthetic suffixes.
2. Approved execution window and scenario list for live sends.
3. API/admin access sufficient to record conversation ids, outbound audit rows,
   quotation ids, follow-up state, and cleanup evidence.
4. `proposal_followup_send_controls.enabled=true` only for the approved test
   scope.
5. FU1 English and Arabic free-form texts configured for in-window sends.
6. FU2/FU3 English and Arabic approved Wazzup WABA template ids/codes configured
   before testing actual 3-day and 7-day sends.
7. If FU1 fallback outside the 24-hour window should be tested, configure
   optional FU1 fallback template ids/codes.

If FU2/FU3 template ids/codes are not available, execute the FU1 and blocked
template-path checks only, and record FU2/FU3 as blocked by WABA setup.

## Test Identities

Use unique synthetic phone suffixes per scenario:

```text
+79262810921#tj-gh22-<scenario>-<YYYYMMDDHHMM>
79262810921#tj-gh22-<scenario>-<YYYYMMDDHHMM>
```

Do not reuse suffixes across reruns. Outbound Wazzup sends must strip the suffix
before sending to the real test number, as already covered by provider tests.

## Scenario Matrix

| ID | Scenario | Setup | Expected result |
| --- | --- | --- | --- |
| S0 | Production smoke | No live message send | `verify_api.py` passes `7/0`; health OK; protected endpoints deny anonymous access |
| S1 | Quotation send prompt | Live or synthetic conversation requests products and provides all required quote details | Quotation is created and sent; Noor sends a short message asking if the quotation works |
| S2 | Pre-acceptance question | After S1, customer asks about delivery, assembly, color, stock, or timing | Noor answers directly when policy/catalog data is available; no manager handoff solely because a quotation exists |
| S3 | Acceptance handoff | After S1, customer replies with clear acceptance such as `yes`, `ok`, `works`, or Arabic equivalent in the quotation-approval context | Follow-up chain stops; manager handoff is created; no duplicate quotation is created |
| S4 | Rejection/objection | After S1, customer says it is too expensive, not suitable, no, or maybe later | Follow-up chain stops; quotation decision metadata records rejection/objection; no FU send is scheduled |
| S5 | Any customer reply stops FU | After proposal state is initialized, customer sends any non-autoreply text | Follow-up metadata records stopped chain; no future FU send occurs |
| S6 | FU1 in service window | Proposal sent, last customer inbound less than 24h before FU1 due, FU1 free-form text configured | One normal text is sent at FU1; no template send; deterministic `crmMessageId` uses proposal follow-up source |
| S7 | FU1 outside service window with fallback | Proposal sent, last customer inbound older than configured free-form window, optional FU1 template configured and confirmed | One Wazzup template send is used; no free-form send |
| S8 | FU1 outside service window without fallback | Same as S7, but no FU1 fallback template configured | No message is sent; result is blocked with template-required reason |
| S9 | FU2/FU3 templates | FU2/FU3 template ids/codes configured and transport confirmed | FU2/FU3 use templates only; no free-form text outside the WhatsApp service window |
| S10 | Arabic follow-up | Conversation language is Arabic and Arabic FU text/template is configured | Customer-facing follow-up is Arabic; no Russian output |
| S11 | No response final status | FU3 sent and the grace period passes without customer reply | Final status is `no_response`/rejected according to proposal follow-up state; no manager handoff |
| S12 | Regression pack | Replay name-gate, SKU variants, quote context, media caption, over-escalation, and long-dialog memory scenarios | Prior issue fixes remain stable while follow-up behavior is active |

## Suggested Commands

Read-only smoke:

```bash
uv run python scripts/verify_api.py --base-url https://noor.starec.ai
```

Controlled live text send, after explicit approval and with real runtime
secrets supplied by the environment:

```bash
uv run python scripts/bot_test.py \
  --base-url https://noor.starec.ai \
  --phone "79262810921#tj-gh22-s1-$(date +%Y%m%d%H%M)" \
  --channel-id "$WAZZUP_TEST_CHANNEL_ID" \
  --api-key "$BOT_TEST_API_KEY" \
  --message "Hello Noor, I need one Skyland Novo meeting table and two CH 616 chairs. Please prepare a quotation for Office 1201, Dubai."
```

Follow-up state verification should be done with approved admin/API access or a
controlled production-maintenance command that records before/after counts and
does not affect real customer conversations.

## Required Evidence

Record these fields in `.codex/stages/tj-gh22/artifacts/` after execution:

1. GitHub Actions run id and runtime commit.
2. Production smoke command and result.
3. Scenario ids executed and skipped.
4. Approved phone/channel/suffixes.
5. Conversation ids.
6. Quotation ids or numbers, if created.
7. Outbound audit rows for quotation text, PDF/media, FU text/template sends.
8. Proposal follow-up metadata before and after each FU scenario.
9. Provider message ids and deterministic CRM message ids.
10. Manager handoff/escalation rows, if expected.
11. Cleanup evidence and remaining synthetic pending count.

## Stop Conditions

Stop the run immediately and do not continue to later scenarios if any of these
happen:

1. Production smoke fails.
2. The test number, channel, or suffix is not the approved one.
3. The bot sends Russian customer-facing text.
4. FU2/FU3 attempt free-form text outside the WhatsApp service window.
5. FU1 sends free-form text when the real service window is closed.
6. The bot creates duplicate quotations, duplicate follow-ups, or duplicate
   manager handoffs.
7. The bot escalates ordinary pre-acceptance customer questions to a manager.
8. The provider returns a template/config error that could affect real
   customers.
9. Cleanup cannot prove synthetic conversations are isolated from real customer
   threads.

## Completion Criteria

The E2E pass is accepted only when:

1. S0 passes.
2. S1-S6 pass in the approved live or production-synthetic environment.
3. S7-S9 pass if WABA FU1/FU2/FU3 templates are configured; otherwise they are
   explicitly recorded as blocked by missing approved templates.
4. S10 passes for Arabic when Arabic templates/text are configured.
5. S11 records the expected no-response/rejected final state.
6. S12 confirms the prior GitHub issue regressions did not reappear.
7. Evidence is committed to `.codex/stages/tj-gh22/artifacts/` and Beads is
   updated with exact run ids, conversation ids, and blockers.
