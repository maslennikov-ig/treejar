---
schema_version: orchestration-artifact/v1
artifact_type: delivery
task_id: tj-gh20.7
stage_id: tj-gh20
repo: treejar
branch: main
base_branch: origin/main
base_commit: f22545b7260e
worktree: /home/me/code/treejar/.worktrees/codex-tj-gh14-main-merge
status: accepted
delivery_method: merge
accepted_by_orchestrator: yes
cleanup_status: not_applicable
cleanup_notes: Delivery used existing main worktree; no delegated write worktree remained to clean.
risk_level: high
verification:
  - GitHub Actions run 26098722338: success, including deploy
  - Production /opt/noor/.release-sha: 9e967d5acd862e98c74b472c1d6fa102e686bf3f
  - uv run python scripts/verify_api.py --base-url https://noor.starec.ai: 7 passed, 0 failed
  - Production synthetic process_message E2E with mock messaging: passed
changed_files:
  - .codex/stages/tj-gh20/artifacts/tj-gh20.7-delivery.md
  - .codex/stages/tj-gh20/summary.md
  - .codex/handoff.md
explicit_defers:
  - Keep production in dialogue_kernel_mode=shadow; enforce rollout remains deferred.
  - GitHub #11 remains pending Lilia's policy answers.
---

# Summary

Date: 2026-05-19
Owner: orchestrator
Status: delivered in production shadow mode

## Deployment

- Feature branch: `codex/tj-gh20-dialogue-state-kernel`
- Delivery commit: `9e967d5acd862e98c74b472c1d6fa102e686bf3f`
- Main delivery: fast-forward merge to `main`
- GitHub Actions: `26098722338`, success
- Production release marker: `/opt/noor/.release-sha` =
  `9e967d5acd862e98c74b472c1d6fa102e686bf3f`

## Production Configuration

`SystemConfig` after delivery:

- `dialogue_kernel_mode=shadow`
- `dialogue_kernel_trace_enabled=true`
- `dialogue_kernel_enforced_flows=""`

This means the LangGraph kernel writes bounded traces but performs no
customer-visible actions, creates no quotations, and sends no escalations.

# Verification

`uv run python scripts/verify_api.py --base-url https://noor.starec.ai`

Result: `7 passed, 0 failed`.

## Synthetic E2E Evidence

The production E2E used direct backend `process_message()` calls with a mock
messaging provider, so no live WhatsApp messages were sent.

Conversation evidence:

- `d9ca9c92-cece-4536-aee3-bde2b75dba5a`: first-turn name gate plus bare
  `Lili` reply resumed the stored workstation/drawers/delivery/assembly
  request; trace mode `shadow`, kernel route `name_gate`, no kernel side
  effects.
- `9be2e89e-d79f-452f-9027-8e1d55d80c12`: pending quotation plus
  `Lil, 1 dubay` preserved quote context, stored name/address, kept
  `pending_quote_selection`, and asked only for company-or-individual; trace
  mode `shadow`, kernel route `quote_details`, no kernel side effects.
- `4f903b85-3f28-4e9e-8938-e7393c37703f`: `I need SKYLAND NOVO 2400 Meeting
  Table and CH 616` did not parse `2400` as quantity; legacy asked for item
  quantities and did not escalate; trace mode `shadow`, kernel route
  `product_selection`.
- `ac97149b-2876-402e-8ace-6aa01e2fd65e`: post-quotation context produced a
  shadow kernel `post_quotation_hold` decision with no side effects while
  preserving the existing quotation metadata.

Parser checks inside production runtime:

- `_extract_purchase_selection("I need SKYLAND NOVO 2400 Meeting Table and CH 616")`
  returned `None`.
- `_extract_purchase_selection("I need 6 CH 616")` returned `CH-616 x 6`.

Direct kernel corpus checks:

- `I need CH 616` -> `product_selection`, handled in shadow, no side effects.
- `I need 6 CH616` -> `product_selection`, delegated to legacy in shadow, no
  side effects.
- `Lil, 1 dubay` -> `quote_details`, handled in shadow, no side effects.

# Risks / Follow-ups

Do not enable `enforce` yet.

The shadow evidence confirms the kernel is capturing the intended flows and
can explain mismatches without changing customer-visible behavior. The
post-quotation scenario also exposed a remaining legacy weakness: legacy
answered with a manager-confirm message where the kernel would hold the quote
context. Because GitHub #11 is still waiting for Lilia's policy answers, the
safe decision is to keep shadow mode enabled, collect more traces, and defer
enforce rollout to a separate stage.
