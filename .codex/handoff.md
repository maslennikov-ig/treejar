# Orchestrator Handoff
Updated: 2026-06-04
Current branch: `codex/tj-gh49-name-gate-duplicate-fix`

## Current Truth
- Canonical host: `https://noor.starec.ai`; runtime path: `/opt/noor`.
- Current local stage: `tj-gh49` for GitHub #48 duplicate name prompt after `Lili`.
- Local fix is implemented in
  `/home/me/code/treejar/.worktrees/tj-gh49-name-gate`: the name-gate resume
  directive now includes the captured name and a narrow guard repairs repeated
  name questions after the pending request is consumed.
- Local evidence: engine tests `234 passed`; full closeout passed with ruff,
  format, mypy, pytest `1225 passed, 19 skipped`, process verification, and
  stage closeout.
- Production now runs `dialogue_kernel_mode=enforce` only for
  `dialogue_kernel_enforced_flows=product_selection`; all other flows stay on
  legacy.
- Latest deployed runtime before this local fix remains
  `3d91e54a8de36fa379ac6e2ec1bfcf778cace11e` from `tj-gh48`; #48 is not yet
  deployed, live-tested, commented, or closed.
- Stage evidence is in `.codex/stages/tj-gh49/summary.md` and
  `.codex/stages/tj-gh49/artifacts/tj-gh49.1-implementation.md`.
- Beads `tj-gh49.1` is closed for local implementation; `tj-gh49.2` remains
  open for merge/deploy/production evidence/GitHub #48 closure.
## Next recommended
Next stage id: `tj-gh49`.
Recommended action: request merge/deploy approval for #48 and capture production
evidence under `tj-gh49.2` before closing the GitHub issue.

## Starter prompt for next orchestrator
Use $orchestrator-stage. Continue from
`/home/me/code/treejar/.worktrees/tj-gh49-name-gate`; read repo contracts,
`.codex/stages/tj-gh49/summary.md`, and the artifact. Current production
dialogue kernel is enforce only for product_selection. Do not enable other
flows. Do not close GitHub #48 until the fix is deployed and production
evidence is captured.

## Explicit defers
- Beads `tj-gh21`: production follow-up sends outside 24h remain blocked until
  client provides approved Wazzup WABA EN/AR template ids/codes and variables.
