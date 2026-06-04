# Orchestrator Handoff
Updated: 2026-06-04
Current branch: `main`

## Current Truth
- Canonical host: `https://noor.starec.ai`; runtime path: `/opt/noor`.
- Current stage: `tj-memory` for Customer Facts and Order Memory Layer.
- Spec/plan: `docs/specs/customer-facts-layer.md` and
  `docs/superpowers/plans/2026-06-04-customer-facts-layer.md`.
- Customer facts v1 is implemented and deployed: DB models/migration/service,
  deterministic/fast extractor, prompt context, past-order answer, quote
  snapshot sync, source message ids, and fail-open savepoints.
- Production runtime: `ccd8b094b521ed7f899240feaf739c12d4e0ba83`, deploy run
  `26951658369`, smoke `8 passed, 0 failed`.
- Final E2E: `+79262810921#tj-memory-e2e-20260604-1231`, conversation
  `0e1feaa8-5922-49b9-abb6-9ab111607d92`; Noor confirmed `2 x CH 616 black`,
  did not repeat supplied quote details, saved 7 accepted facts with 0 conflicts,
  and created no escalation.
- `customer_facts_mode` is restored to default disabled/UNSET after E2E; Bead
  `tj-memory.7` tracks the remaining global rollout enable decision.
- Production still runs `dialogue_kernel_mode=enforce` only for
  `dialogue_kernel_enforced_flows=product_selection`.
- Detailed evidence: `.codex/stages/tj-memory/summary.md` and
  `.codex/stages/tj-memory/artifacts/tj-memory.7-delivery-e2e.md`.

## Next recommended
Next stage id: `tj-memory`.
Recommended action: decide whether to enable `customer_facts_mode=shadow` first
or move selected flows to `enforce` after reviewing E2E evidence.

## Starter prompt for next orchestrator
Use $orchestrator-stage. Continue from `/home/me/code/treejar`; read repo
contracts, `tj-memory` summary, spec, plan, and delivery E2E artifact.

## Explicit defers
- `tj-gh21`: production follow-up sends outside 24h remain blocked until client
  provides approved Wazzup WABA EN/AR template ids/codes and variables.
