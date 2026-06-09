# Orchestrator Handoff
Updated: 2026-06-09
Current branch: `codex/tj-order-flow-cutover-plan`

## Current Truth
- Canonical host: `https://noor.starec.ai`; runtime path: `/opt/noor`.
- Current local planning stage: `tj-order-cutover`; worktree:
  `/home/me/code/treejar/.worktrees/tj-gh51-order-quote-cutover`.
- Production delivery reached `main` through `3d37eb1`; CI/deploy run
  `27207213847` and deploy job `80326453443` passed; prod API smoke passed
  `8/0`.
- Spec/plan: `docs/specs/dialogue-state-kernel.md`,
  `docs/specs/customer-facts-layer.md`,
  `docs/superpowers/plans/2026-06-09-order-flow-cutover.md`.
- Live WhatsApp E2E on approved phone ending `0921` passed:
  core GH51 flow created quotation `Fr3368`; direct SKU+quantity, quantity
  repair, and discount/payment blocker scenarios also passed.
- New planning evidence: `.codex/stages/tj-order-cutover/summary.md` and
  `.codex/stages/tj-order-cutover/artifacts/next-orchestrator-prompt.md`.

## Next recommended
Next stage id: `tj-order-cutover`.
Recommended action: implement the full order/quote flow cutover from
`docs/superpowers/plans/2026-06-09-order-flow-cutover.md`, starting with RED
replay coverage for #40-#51 and especially the second #42 occurrence.

## Starter prompt for next orchestrator
Use $orchestrator-stage. Continue from worktree
`/home/me/code/treejar/.worktrees/tj-gh51-order-quote-cutover`; read repo
contracts, `.codex/stages/tj-order-cutover/summary.md`,
`.codex/stages/tj-order-cutover/artifacts/next-orchestrator-prompt.md`, Beads
`tj-order-cutover`, git status/diff, and active worktrees before implementation.

## Explicit defers
- `tj-gh21`: outside-24h follow-ups wait for approved Wazzup WABA EN/AR templates.
