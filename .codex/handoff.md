# Orchestrator Handoff
Updated: 2026-06-09
Current branch: `codex/tj-gh51-order-quote-cutover`

## Current Truth
- Canonical host: `https://noor.starec.ai`; runtime path: `/opt/noor`.
- Current local stage: `tj-gh51-order-quote-cutover`; worktree:
  `/home/me/code/treejar/.worktrees/tj-gh51-order-quote-cutover`.
- Delivery was pushed/merged to `main` through
  `7049107ad04fa67513efb559a6fb2a00115eb9ce`.
- GitHub Actions run `27200937145` passed `changes`, `lint`, `test`,
  `type-check`, and `deploy`; deploy job `80304760664` completed
  successfully.
- Production API smoke after deploy passed: `scripts/verify_api.py --base-url
  https://noor.starec.ai` reported `8 passed, 0 failed`.
- Spec/plan: `docs/specs/dialogue-state-kernel.md`,
  `docs/specs/customer-facts-layer.md`,
  `docs/superpowers/plans/2026-06-08-order-state-runtime.md`.
- Production runtime target is expected to be the deployed `7049107` code path.
- Active stage evidence: `.codex/stages/tj-gh51-order-quote-cutover/summary.md`.
- Previous stage evidence: `.codex/stages/tj-order-state/summary.md` and
  `.codex/stages/tj-order-state/artifacts/tj-order-state-live-e2e.md`.
- Live WhatsApp E2E for this stage was attempted on the approved phone ending
  `0921`, but stopped after repeated assistant messages were delivered to the
  real physical WhatsApp number. Do not run further live sends on that personal
  number without fresh explicit approval after this incident.

## Next recommended
Next stage id: `tj-gh51-order-quote-cutover`.
Recommended action: use an isolated test number or an outbound-disabled
production-like harness for the final full live E2E; do not reuse the owner's
personal WhatsApp number for repeated test conversations.

## Starter prompt for next orchestrator
Use $orchestrator-stage. Continue from worktree
`/home/me/code/treejar/.worktrees/tj-gh51-order-quote-cutover`; read repo
contracts, stage artifacts, Beads, git status/diff, and active worktrees before
follow-up implementation, review, delivery, or issue closeout.

## Explicit defers
- Final full live WhatsApp E2E pass for `tj-gh51-order-quote-cutover` is
  deferred because the approved personal number received repeated real messages
  during test attempts. This is blocked on an isolated test number or an
  outbound-disabled production-like harness.
- `tj-gh21`: outside-24h follow-ups wait for approved Wazzup WABA EN/AR templates.
