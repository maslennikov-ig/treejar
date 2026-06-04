# Orchestrator Handoff
Updated: 2026-06-04
Current branch: `main`

## Current Truth
- Canonical host: `https://noor.starec.ai`; runtime path: `/opt/noor`.
- Current stage: `tj-gh49` for GitHub #48 duplicate name prompt after `Lili`.
- Fix is implemented and delivered:
  `src/llm/closed_question_guard.py` repairs standalone repeated slot questions
  when name, company/individual status, or a specific delivery address is already
  known; no product-specific fallback remains.
- Delivered runtime: `5bd91b9013cedcc7d3101f7a6c64d2c71b35ab7f`;
  deploy run `26942597892`; prod smoke `8 passed, 0 failed`.
- Prod E2E #48 passed: synthetic chat `+79262810921-tjgh49-20260604092424`,
  conversation `25e10461-0121-4bc2-b259-df637d0ac64a`; after `Lili`, Noor stored
  the name, answered the original request, repeated no name question, and
  created no pending escalation.
- Production now runs `dialogue_kernel_mode=enforce` only for
  `dialogue_kernel_enforced_flows=product_selection`; all other flows stay on
  legacy.
- Stage evidence is in `.codex/stages/tj-gh49/summary.md` and artifacts.
- GitHub #48 and Beads `tj-gh49`/`tj-gh49.2` are closed.
## Next recommended
Next stage id: `tj-gh49`.
Recommended action: no immediate #48 work remains.

## Starter prompt for next orchestrator
Use $orchestrator-stage. Continue from `/home/me/code/treejar`; read repo
contracts, `.codex/stages/tj-gh49/summary.md`, and artifacts. Current production
dialogue kernel is enforce only for product_selection. GitHub #48 is closed with
production evidence.

## Explicit defers
- Beads `tj-gh21`: production follow-up sends outside 24h remain blocked until
  client provides approved Wazzup WABA EN/AR template ids/codes and variables.
