# Orchestrator Handoff
Updated: 2026-06-08
Current branch: `codex/tj-order-state-refactor`

## Current Truth
- Canonical host: `https://noor.starec.ai`; runtime path: `/opt/noor`.
- Current stage: `tj-order-state`; local implementation, review-fix, follow-up
  fixes, and full local verification are complete.
- Spec/plan: `docs/specs/dialogue-state-kernel.md`,
  `docs/specs/customer-facts-layer.md`, and
  `docs/superpowers/plans/2026-06-08-order-state-runtime.md`.
- Production runtime: `455693cb26cf45ae5255dc07ad1732c52a3e8124`,
  deploy run `26965492878`, smoke `8 passed, 0 failed`.
- Customer facts v1 is globally enabled in production
  (`customer_facts_mode=enforce`); PII masking remains opt-in.
- Final customer facts enforce E2E passed for synthetic conversations
  `4983dc17-c27c-4756-8a65-3afc0a25b447` and
  `cfeb7a07-d50c-47a3-8cf8-5cd3af570b25`; the real unsuffixed
  `+79262810921` thread was not touched.
- Production still runs `dialogue_kernel_mode=enforce` only for
  `dialogue_kernel_enforced_flows=product_selection`.
- New local stage evidence: `.codex/stages/tj-order-state/summary.md` plus
  artifacts under `.codex/stages/tj-order-state/artifacts/`; latest full local
  pytest result is `1335 passed, 19 skipped`.
- Previous production evidence lives in the `tj-memory` stage summary/artifacts.

## Next recommended
Next stage id: `tj-order-state`.
Recommended action: decide delivery for `codex/tj-order-state-refactor`; do not
deploy, run live WhatsApp/API E2E, close GitHub issues, or mutate production
without explicit approval.

## Starter prompt for next orchestrator
Use $orchestrator-stage. Continue from `/home/me/code/treejar`; read repo
contracts, `tj-order-state` summary/artifacts, specs, plan, Beads state, git
status/diff, and active subagents/worktrees before deciding delivery, live E2E,
or follow-up implementation.

## Explicit defers
- `tj-gh21`: outside-24h follow-ups wait for approved Wazzup WABA EN/AR templates.
