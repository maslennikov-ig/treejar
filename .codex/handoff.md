# Orchestrator Handoff
Updated: 2026-06-20
Current branch: `codex/tj-lgmg-catalog-discovery`

## Current Truth
- Stage `tj-lgmg-catalog-discovery`; Beads `tj-lgmg` tracks GH #55.
- Local implementation is in
  `/home/me/code/treejar/.worktrees/tj-lgmg-catalog-discovery`.
- Verified-answer routing now keeps ordinary wardrobes, beds, and
  restaurant/living-room/kids discovery on product path or bounded clarify.
- Payment terms and company office-location questions still hand off.
- No commit, push, PR, deploy, GitHub mutation, production mutation, or live
  WhatsApp E2E has been performed.
- Graphify is not configured; `graphify-out/GRAPH_REPORT.md` is absent.

## Verification
- RED regressions failed before implementation; post-fix targeted slices passed:
  `4 passed`, `8 passed`, and policy/order-handoff `48 passed`.
- Ruff check, ruff format-check, and `uv run mypy src/` passed.
- Full pytest first exposed missing local `frontend/admin` deps (`esbuild`).
  After `npm --prefix frontend/admin ci --ignore-scripts`, final full pytest
  passed: `1430 passed, 19 skipped`.
- Stage evidence: `.codex/stages/tj-lgmg-catalog-discovery/summary.md`.
- Stage closeout passed for `tj-lgmg-catalog-discovery`.

## Next recommended
Next stage id: `tj-lgmg-delivery`.
Recommended action: review diff, commit if accepted, then decide whether to
push/deploy and run live GH #55 WhatsApp E2E.

## Starter prompt for next orchestrator
Use $orchestrator-stage for delivery of `tj-lgmg`. Read AGENTS.md,
`.codex/orchestrator.toml`, this handoff, Beads `tj-lgmg`, and the stage
summary. Verify branch `codex/tj-lgmg-catalog-discovery`; ask before any
push/deploy/live/GitHub mutation not explicitly authorized.

## Explicit defers
- No technical defers. Push, deploy, live WhatsApp E2E, and GH #55 closure were
  not performed because external/delivery actions need explicit authorization.
