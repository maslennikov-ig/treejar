# Orchestrator Handoff
Updated: 2026-06-09
Current branch: `codex/tj-gh51-order-quote-cutover`

## Current Truth
- Canonical host: `https://noor.starec.ai`; runtime path: `/opt/noor`.
- Current local stage: `tj-gh51-order-quote-cutover`; worktree:
  `/home/me/code/treejar/.worktrees/tj-gh51-order-quote-cutover`.
- Delivery reached `main` through `7049107`; CI/deploy run `27200937145`
  and deploy job `80304760664` passed; prod API smoke passed `8/0`.
- Spec/plan: `docs/specs/dialogue-state-kernel.md`,
  `docs/specs/customer-facts-layer.md`,
  `docs/superpowers/plans/2026-06-08-order-state-runtime.md`.
- Live WhatsApp E2E on approved phone ending `0921` reproduced the GH #51
  symptom after mixed resolved/unresolved selection; fix is in progress.
- Active evidence: `.codex/stages/tj-gh51-order-quote-cutover/summary.md`.

## Next recommended
Next stage id: `tj-gh51-order-quote-cutover`.
Recommended action: finish the unresolved-item quote-details fix, redeploy, then
rerun controlled live E2E on the approved personal number.

## Starter prompt for next orchestrator
Use $orchestrator-stage. Continue from worktree
`/home/me/code/treejar/.worktrees/tj-gh51-order-quote-cutover`; read repo
contracts, stage artifacts, Beads, git status/diff, and active worktrees before
follow-up implementation, review, delivery, or issue closeout.

## Explicit defers
- Final full live WhatsApp E2E is not passed yet; current run found a blocking
  mixed resolved/unresolved quote-details regression.
- `tj-gh21`: outside-24h follow-ups wait for approved Wazzup WABA EN/AR templates.
