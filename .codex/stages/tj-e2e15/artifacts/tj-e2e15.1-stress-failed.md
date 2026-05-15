---
schema_version: orchestration-artifact/v1
artifact_type: live-e2e
task_id: tj-e2e15.1
stage_id: tj-e2e15
repo: treejar
branch: codex/tj-long-memory-e2e
base_branch: origin/main
base_commit: 7d3579cbf7b84826318d154cb98a3cdc3121db60
worktree: /home/me/code/treejar/.worktrees/codex-tj-gh15-name-escalation-hardening
status: blocked
delivery_method: n/a
accepted_by_orchestrator: yes
cleanup_status: not_applicable
cleanup_notes: No child worktree was created; approved production test phone was cleaned before the run and now contains the failed test transcript.
risk_level: high
verification:
  - "production cleanup for 79262810921%": passed, before conversations/messages/outbound audits 1/6/15, after all 0
  - "python3 scripts/bot_test.py -p 79262810921 turn 1": passed, assistant model name-gate and escalation none
  - "python3 scripts/bot_test.py -p 79262810921 turn 2": passed, bare Lili stored name and resumed product planning
  - "python3 scripts/bot_test.py -p 79262810921 turn 3": failed, company detail message created pending verified-policy escalation
  - "python3 scripts/bot_test.py -p 79262810921 turns 4-6": failed, fallback manager-notified replies
  - "python3 scripts/bot_test.py -p 79262810921 turn 7": failed, no correlated assistant reply within 90 seconds
  - "production DB inspection for cb46ebcb-1c5a-41f4-a7d7-99e295f11ba7": failed, escalation_status pending and one pending escalation
changed_files:
  - .codex/stages/tj-e2e15/artifacts/tj-e2e15.1-stress-failed.md
  - .codex/stages/tj-e2e15/summary.md
  - .codex/handoff.md
explicit_defers:
  - tj-e2e15.2 remains open for implementation, deploy, and repeat long-dialog E2E validation.
---

# Summary

Ran the separate production long-dialog E2E stress test on the approved phone
`+79262810921`. The test did not pass: Noor preserved the initial name-gate
context, but a neutral customer-detail update triggered verified-policy manager
handoff and stopped the normal dialogue flow.

# Verification

- Cleanup before the test removed all matching state for `79262810921%`: before
  cleanup there were 1 conversation, 6 messages, and 15 outbound audit rows;
  after cleanup all matching counts were 0.
- Live conversation `cb46ebcb-1c5a-41f4-a7d7-99e295f11ba7`:
  - Turn 1 returned only the name question via `name-gate`.
  - Turn 2 `Lili` stored `customer_name=Lili`, updated quote customer details,
    and resumed the original Skyland Novo/mobile drawer request.
  - Turn 3 `The company is Memory Test LLC.` returned `I want to be accurate,
    so our manager will confirm this for you.` via `z-ai/glm-5|verified-policy`.
  - Production DB recorded pending escalation reason:
    `Verified-answer policy requires manager confirmation because no verified
    FAQ support was found for 'The company is Memory Test LLC.'`.
  - Turns 4-6 returned fallback manager-notified replies, so address, drawer
    comparison, and quantity changes were not handled as a continuing dialogue.
  - Turn 7 timed out with no correlated assistant reply within 90 seconds.
- Final DB state confirmed `customer_name=Lili`, `escalation_status=pending`,
  metadata only containing `quote_customer_details.name=Lili`, and one pending
  escalation.

# Risks / Follow-ups

Created P1 Bead `tj-e2e15.2` to fix the newly found class of bug: customer
detail-only messages after active product context must be captured or handled by
normal agent flow, not converted into verified-policy handoff. The long-dialog
memory test should be repeated after that fix is deployed.
