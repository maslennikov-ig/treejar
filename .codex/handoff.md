# Orchestrator Handoff
Updated: 2026-06-16
Current branch: `codex/tj-order-route-adapter`

## Current Truth
- Stage `tj-order-cutover-route-adapter`; worktree `/home/me/code/treejar/.worktrees/tj-order-route-adapter`.
- `tj-order-cutover.10` local implementation is complete and verified: remaining deterministic order/quote route families now delegate from `process_message` to `_order_quote_route_for_turn`.
- `create_quotation` remains directly callable only through `_execute_order_quote_side_effect`; structural regression coverage was added.
- Production E2E found and fixed four route-resume gaps: bare `2` after numbered SKU options first fell through to `verified-policy-clarify`, then preserved route but defaulted quantity to 1 after name-gate, then the dialogue-kernel product quantity prompt failed to store the canonical pending quantity frame, then short affirmative follow-up after a single stock/price option lost the quote context; all four regressions are covered locally.
- Beads `tj-order-cutover.10` is closed; Beads export was written to the shared `/home/me/code/treejar/.beads/issues.jsonl`.
- Local full gates passed after the single stock-option quote-resume fix: ruff check, ruff format check, mypy, and `pytest tests/ -q` with 1418 passed, 19 skipped.
- Stage closeout passed again for `tj-order-cutover-route-adapter` after the single stock-option quote-resume fix.
- Fourth delivery commit `4d68f78` reached production and passed marker/smoke; live E2E verified name-gate resume, bare `2` quantity preservation, exact-quote repair/resume, SKU variant, all-details first turn, and pending quantity/reference resume, then exposed the single stock/price option short follow-up gap now fixed locally.
- Fifth delivery commit `ec8dd61` reached production via CI run `27622142673`; production marker matched, health/`verify_api.py` smoke passed, final live order/quote E2E matrix passed, and scoped PostgreSQL/Redis synthetic cleanup completed.
- Graphify is not configured; no `graphify-out/GRAPH_REPORT.md` exists.

## Verification
- `OPENROUTER_API_KEY=test uv run ruff check src/ tests/` passed.
- `OPENROUTER_API_KEY=test uv run ruff format --check src/ tests/` passed.
- `OPENROUTER_API_KEY=test uv run mypy src/` passed.
- `OPENROUTER_API_KEY=test uv run pytest tests/ -q` passed: 1418 passed, 19 skipped.
- `scripts/orchestration/run_stage_closeout.py --stage tj-order-cutover-route-adapter` passed.

## Next recommended
Next stage id: `tester-order-quote-handoff`
Recommended action: hand the order/quote route adapter delivery to the tester with production evidence from commit `ec8dd61` / CI run `27622142673`.

## Starter prompt for next orchestrator
Use $orchestrator-stage only if more engineering work is needed. For tester handoff, read `.codex/stages/tj-order-cutover-route-adapter/summary.md` and Beads `tj-order-cutover.10`; production is on `ec8dd612dfb0a44eb41104bd198a5936f91c847d` from CI run `27622142673`.

## Explicit defers
- No in-scope defers remain for `tj-order-cutover.10` after production verification and cleanup.
- GitHub issue #42 second-occurrence comment still lacks a separate production evidence reply; adding one is externally visible and was not separately authorized.
