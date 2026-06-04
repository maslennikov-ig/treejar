# Orchestrator Handoff
Updated: 2026-06-04
Current branch: `codex/tj-memory-customer-facts-layer`

## Current Truth
- Canonical host: `https://noor.starec.ai`; runtime path: `/opt/noor`.
- Current stage: `tj-memory` for Customer Facts and Order Memory Layer.
- `tj-memory.1` is complete: spec `docs/specs/customer-facts-layer.md` and plan
  `docs/superpowers/plans/2026-06-04-customer-facts-layer.md` were created.
- Beads `tj-memory` is in progress; tasks `tj-memory.2` through `tj-memory.7`
  remain open.
- Scope: persistent profile facts, current order state, and past order history
  are separate; past orders require confirmation before reuse in a new quote.
- GitHub #48/tj-gh49 is delivered and closed; runtime release
  `5bd91b9013cedcc7d3101f7a6c64d2c71b35ab7f`, deploy run `26942597892`, prod
  smoke `8 passed, 0 failed`.
- Production now runs `dialogue_kernel_mode=enforce` only for
  `dialogue_kernel_enforced_flows=product_selection`; all other flows stay on
  legacy.
- Stage evidence is in `.codex/stages/tj-memory/summary.md` and artifacts.
- GitHub #48 and Beads `tj-gh49`/`tj-gh49.2` are closed.
## Next recommended
Next stage id: `tj-memory`.
Recommended action: implement `tj-memory.2` and `tj-memory.3` in parallel, then
integrate into `process_message` sequentially.

## Starter prompt for next orchestrator
Use $orchestrator-stage. Continue from `/home/me/code/treejar`; read repo
contracts, `.codex/stages/tj-memory/summary.md`, the spec, and the plan. Keep
`src/llm/engine.py` integration sequential.

## Explicit defers
- Beads `tj-gh21`: production follow-up sends outside 24h remain blocked until
  client provides approved Wazzup WABA EN/AR template ids/codes and variables.
