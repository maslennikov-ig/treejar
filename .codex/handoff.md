# Orchestrator Handoff
Updated: 2026-06-08
Current branch: `main`

## Current Truth
- Canonical host: `https://noor.starec.ai`; runtime path: `/opt/noor`.
- Current stage: `tj-order-state`; implementation, review-fix, deploy, API
  smoke, and final live WhatsApp E2E are complete.
- Spec/plan: `docs/specs/dialogue-state-kernel.md`,
  `docs/specs/customer-facts-layer.md`,
  `docs/superpowers/plans/2026-06-08-order-state-runtime.md`.
- Production runtime: `770da1721837496c70a5e28902c26e8f275cafc9`,
  deploy run `27146046204`, smoke `8 passed, 0 failed`.
- Customer facts v1 is globally enabled; production still runs
  `dialogue_kernel_mode=enforce` only for `product_selection`.
- Stage evidence: `.codex/stages/tj-order-state/summary.md` and
  `.codex/stages/tj-order-state/artifacts/tj-order-state-live-e2e.md`.
- Latest full local pytest: `1345 passed, 19 skipped`; final CI run
  `27146046204` passed lint/test/type-check/deploy.
- Final live E2E passed on the approved phone ending `0921`: stock+price,
  ordinal selection, multi-item selection, compact quote details, missing
  quantity resume, ambiguous CH616 options, and ordinal selection after options.
- Live quote artifacts remain in Zoho: at least `Fr3361` and `Fr3362`; the
  live phone was reset to blank active conversation
  `48e0ab68-cc4f-43a6-a3fd-87be8c3609b7`.

## Next recommended
Next stage id: `tj-order-state`.
Recommended action: monitor production normally; optionally close linked GitHub
issues after human review of the recorded evidence.

## Starter prompt for next orchestrator
Use $orchestrator-stage. Continue from `/home/me/code/treejar`; read repo
contracts, stage artifacts, Beads, git status/diff, and active worktrees before
follow-up implementation or issue closeout.

## Explicit defers
- `tj-gh21`: outside-24h follow-ups wait for approved Wazzup WABA EN/AR templates.
