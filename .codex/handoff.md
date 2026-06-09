# Orchestrator Handoff
Updated: 2026-06-09
Current branch: `codex/tj-gh51-order-quote-cutover`

## Current Truth
- Canonical host: `https://noor.starec.ai`; runtime path: `/opt/noor`.
- Current local stage: `tj-gh51-order-quote-cutover`; worktree:
  `/home/me/code/treejar/.worktrees/tj-gh51-order-quote-cutover`.
- No deploy, live WhatsApp test, GitHub close, remote merge, or production
  mutation has been performed for this stage.
- Spec/plan: `docs/specs/dialogue-state-kernel.md`,
  `docs/specs/customer-facts-layer.md`,
  `docs/superpowers/plans/2026-06-08-order-state-runtime.md`.
- Production runtime: `770da1721837496c70a5e28902c26e8f275cafc9`,
  deploy run `27146046204`, smoke `8 passed, 0 failed`.
- Active stage evidence: `.codex/stages/tj-gh51-order-quote-cutover/summary.md`.
- Previous stage evidence: `.codex/stages/tj-order-state/summary.md` and
  `.codex/stages/tj-order-state/artifacts/tj-order-state-live-e2e.md`.
- Previous stage `tj-order-state` remains production truth; final live E2E
  passed on approved phone ending `0921`.

## Next recommended
Next stage id: `tj-gh51-order-quote-cutover`.
Recommended action: request explicit push/merge/deploy/live-E2E approval if
delivery should proceed; local implementation and stage closeout are green.

## Starter prompt for next orchestrator
Use $orchestrator-stage. Continue from worktree
`/home/me/code/treejar/.worktrees/tj-gh51-order-quote-cutover`; read repo
contracts, stage artifacts, Beads, git status/diff, and active worktrees before
follow-up implementation, review, delivery, or issue closeout.

## Explicit defers
- `tj-gh21`: outside-24h follow-ups wait for approved Wazzup WABA EN/AR templates.
