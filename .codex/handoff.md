# Orchestrator Handoff
Updated: 2026-06-04
Current branch: `main`

## Current Truth
- Canonical host: `https://noor.starec.ai`; runtime path: `/opt/noor`.
- Current stage: `tj-memory` for Customer Facts and Order Memory Layer.
- Spec/plan: `docs/specs/customer-facts-layer.md` and
  `docs/superpowers/plans/2026-06-04-customer-facts-layer.md`.
- Production runtime: `e4e7ecff52d71434e5f0c179bc166c9e325f05bc`,
  deploy run `26956771039`, smoke `8 passed, 0 failed`.
- Customer facts v1 is deployed but globally gated; `tj-memory.7` tracks the
  remaining decision to enable `customer_facts_mode=shadow|enforce`.
- PII masking is disabled by default in production because it was not a client
  requirement and blocked extraction of phones/emails/facts; opt-in remains via
  `PII_MASKING_ENABLED=true`.
- Final PII/default-off E2E passed:
  `20bf6801-e24a-4474-a015-2c4be31bc50e` and
  `f9e669ef-b46e-43cf-9096-bd0e50167819`. Noor kept `2 x CH 616`, saved
  name/email/phone/address/customer type, created no escalation, consumed
  name-gate pending request, and stored no `[PII-...]` placeholders.
- Synthetic E2E conversations were closed/resolved after readback; the real
  unsuffixed `+79262810921` thread was not touched.
- Production still runs `dialogue_kernel_mode=enforce` only for
  `dialogue_kernel_enforced_flows=product_selection`.
- Evidence: `.codex/stages/tj-memory/summary.md`,
  `.codex/stages/tj-memory/artifacts/tj-memory.7-delivery-e2e.md`, and
  `.codex/stages/tj-memory/artifacts/tj-memory.10-delivery-e2e.md`.

## Next recommended
Next stage id: `tj-memory`.
Recommended action: decide whether to enable `customer_facts_mode=shadow` first
or move selected flows to `enforce` after reviewing E2E evidence.

## Starter prompt for next orchestrator
Use $orchestrator-stage. Continue from `/home/me/code/treejar`; read repo
contracts, `tj-memory` summary, spec, plan, and delivery E2E artifact.

## Explicit defers
- `tj-gh21`: outside-24h follow-ups wait for approved Wazzup WABA EN/AR templates.
