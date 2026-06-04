# Orchestrator Handoff
Updated: 2026-06-04
Current branch: `codex/tj-memory-customer-facts-layer`

## Current Truth
- Canonical host: `https://noor.starec.ai`; runtime path: `/opt/noor`.
- Current stage: `tj-memory` for Customer Facts and Order Memory Layer.
- Spec/plan are in `docs/specs/customer-facts-layer.md` and
  `docs/superpowers/plans/2026-06-04-customer-facts-layer.md`.
- Implemented v1 foundation: memory models/migration/service, fact extractor,
  prompt context, past-order answer, quote snapshot sync, source message ids, and
  savepoint-backed fail-open handling.
- Review hardening applied: price objections are non-terminal, current-order
  `individual/company` satisfies quotation details, and memory writes are
  isolated from the normal reply path.
- `customer_facts_mode` defaults to `disabled`; no prod customer-visible change
  until config/deploy/evidence are explicitly approved.
- Beads `tj-memory.1`-`.6` are implementation scope; `.7` tracks rollout and
  production evidence.
- Scope: persistent profile facts, current order state, and past order history
  are separate; past orders require confirmation before reuse in a new quote.
- GitHub #48/tj-gh49 is delivered and closed; runtime release
  `5bd91b9013cedcc7d3101f7a6c64d2c71b35ab7f`, deploy run `26942597892`, prod
  smoke `8 passed, 0 failed`.
- Production now runs `dialogue_kernel_mode=enforce` only for
  `dialogue_kernel_enforced_flows=product_selection`; all other flows stay on
  legacy.
- Stage evidence is in `.codex/stages/tj-memory/summary.md`; GitHub #48 and
  Beads `tj-gh49`/`tj-gh49.2` are closed.
## Next recommended
Next stage id: `tj-memory`.
Recommended action: decide whether to ship with `customer_facts_mode=shadow`.

## Starter prompt for next orchestrator
Use $orchestrator-stage. Continue from `/home/me/code/treejar`; read repo
contracts, `tj-memory` summary, spec, and plan. Keep engine integration sequential.

## Explicit defers
- Beads `tj-gh21`: production follow-up sends outside 24h remain blocked until
  client provides approved Wazzup WABA EN/AR template ids/codes and variables.
