# Orchestrator Handoff
Updated: 2026-06-04
Current branch: `main`

## Current Truth
- Canonical host: `https://noor.starec.ai`; runtime path: `/opt/noor`.
- Current stage: `tj-memory` for Customer Facts and Order Memory Layer.
- Spec/plan: `docs/specs/customer-facts-layer.md` and
  `docs/superpowers/plans/2026-06-04-customer-facts-layer.md`.
- Production runtime: `455693cb26cf45ae5255dc07ad1732c52a3e8124`,
  deploy run `26965492878`, smoke `8 passed, 0 failed`.
- Customer facts v1 is globally enabled in production:
  `customer_facts_mode=enforce`, trace enabled, fast extractor enabled.
- PII masking is disabled by default in production because it was not a client
  requirement and blocked extraction of phones/emails/facts; opt-in remains via
  `PII_MASKING_ENABLED=true`.
- Final customer facts enforce E2E passed:
  `4983dc17-c27c-4756-8a65-3afc0a25b447` and
  `cfeb7a07-d50c-47a3-8cf8-5cd3af570b25`. Noor kept `2 x CH 616`, saved
  name/email/phone/address/customer type, consumed name-gate pending request,
  created no escalation, and produced fact traces with `conflict_count=0`.
- Synthetic E2E conversations were closed/resolved after readback; the real
  unsuffixed `+79262810921` thread was not touched.
- Production still runs `dialogue_kernel_mode=enforce` only for
  `dialogue_kernel_enforced_flows=product_selection`.
- Evidence: `tj-memory` summary plus artifacts
  `tj-memory.7-global-enable-e2e.md`, `tj-memory.7-delivery-e2e.md`, and
  `tj-memory.10-delivery-e2e.md`.

## Next recommended
Next stage id: choose from the next GitHub issue or Wazzup follow-up work.
Recommended action: monitor real customer conversations for customer facts
trace anomalies; rollback is config-only by setting `customer_facts_mode=disabled`.

## Starter prompt for next orchestrator
Use $orchestrator-stage. Continue from `/home/me/code/treejar`; read repo
contracts, `tj-memory` summary, spec, plan, and delivery E2E artifact.

## Explicit defers
- `tj-gh21`: outside-24h follow-ups wait for approved Wazzup WABA EN/AR templates.
