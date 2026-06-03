# Orchestrator Handoff
Updated: 2026-06-03
Current branch: `codex/tj-gh48-e2e-service-interruption-fix`

## Current Truth
- Canonical host: `https://noor.starec.ai`; runtime path: `/opt/noor`.
- `tj-gh48.8` service-interruption hotfix is deployed at runtime commit
  `3d91e54a8de36fa379ac6e2ec1bfcf778cace11e`; Actions run `26841843489`
  and production smoke passed (`8 passed, 0 failed`).
- Production now runs `dialogue_kernel_mode=enforce` only for
  `dialogue_kernel_enforced_flows=product_selection`; all other flows stay on
  legacy.
- E2E on synthetic identities
  `+79262810921#tj-gh48-enforce-20260603081129-*` passed for product preference
  after delivery interruption, exact SKU, quantity guard, name gate resume, and
  explicit manager request.
- Six synthetic conversations were closed; one intentional synthetic escalation
  was resolved; real base phone conversation was not mutated.
- Stage evidence is in `.codex/stages/tj-gh48/summary.md` and
  `.codex/stages/tj-gh48/artifacts/`.
- `tj-gh48` rollout is closed; remaining tracked work is `tj-gh21`,
  blocked until client provides approved Wazzup WABA EN/AR templates.
## Next recommended
Next stage id: `tj-gh21`.
Recommended action: wait for Wazzup WABA template ids/codes and variable mapping
from the client, then configure and test follow-ups outside 24 hours.

## Starter prompt for next orchestrator
Use $orchestrator-stage. Continue from
`/home/me/code/treejar/.worktrees/tj-gh48-impl`; read repo contracts, summary,
and artifacts. Current production dialogue kernel is enforce only for
product_selection. Do not enable other flows or close Wazzup-template work
without approved template details.

## Explicit defers
- Beads `tj-gh21`: production follow-up sends outside 24h remain blocked until
  client provides approved Wazzup WABA EN/AR template ids/codes and variables.
