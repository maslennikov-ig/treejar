# Orchestrator Handoff
Updated: 2026-06-09
Current branch: `codex/tj-gh51-order-quote-cutover`

## Current Truth
- Canonical host: `https://noor.starec.ai`; runtime path: `/opt/noor`.
- Current local stage: `tj-gh51-order-quote-cutover`; worktree:
  `/home/me/code/treejar/.worktrees/tj-gh51-order-quote-cutover`.
- Delivery reached `main` through `785ad1a`; CI/deploy run `27203026681`
  and deploy job `80311779370` passed; prod API smoke passed `8/0`.
- Spec/plan: `docs/specs/dialogue-state-kernel.md`,
  `docs/specs/customer-facts-layer.md`,
  `docs/superpowers/plans/2026-06-08-order-state-runtime.md`.
- Live WhatsApp E2E on approved phone ending `0921` passed:
  core GH51 flow created quotation `Fr3368`; direct SKU+quantity, quantity
  repair, and discount/payment blocker scenarios also passed.
- Active evidence: `.codex/stages/tj-gh51-order-quote-cutover/summary.md`.

## Next recommended
Next stage id: `tj-gh51-order-quote-cutover`.
Recommended action: monitor manager/customer follow-up behavior for quote
`Fr3368`; no GH51 delivery blocker remains.

## Starter prompt for next orchestrator
Use $orchestrator-stage. Continue from worktree
`/home/me/code/treejar/.worktrees/tj-gh51-order-quote-cutover`; read repo
contracts, stage artifacts, Beads, git status/diff, and active worktrees before
follow-up implementation, review, delivery, or issue closeout.

## Explicit defers
- `tj-gh21`: outside-24h follow-ups wait for approved Wazzup WABA EN/AR templates.
