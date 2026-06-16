# Orchestrator Handoff
Updated: 2026-06-16
Current branch: `codex/tj-order-cutover-review-fix`

## Current Truth
- Stage `tj-order-cutover-review-fix`; worktree `/home/me/code/treejar/.worktrees/tj-order-cutover-review-fix`.
- Beads covered by this branch: `tj-s1qi`, `tj-1ha9`, `tj-hqsa`, `tj-v2k9`; `tj-order-cutover.10` is only partially improved and remains open for the full P2 route extraction.
- Base was `origin/main` at `b03227e`; no push, deploy, production mutation, or live E2E has been run after the latest hardening changes yet.
- Review streams used: `correctness_reviewer`, `improvement_reviewer`, `architect_reviewer`; final current-diff correctness review is running as `Ledger`.
- Accepted and fixed locally: invalid canonical quote frame no longer falls back to stale legacy quote selection; expired/non-answerable typed quantity frame suppresses stale legacy `pending_product_reference_quantity`; `legacy_migration_read` trace now records legacy metadata reads.
- Follow-up hardening added locally: unresolved-only quote repair has canonical typed frame ownership; pending quantity/reference route selection is delegated to `_pending_reference_route_for_turn`; quote frames get deterministic IDs and bounded non-PII quote side-effect traces; frontend admin package-lock resolves the Vite/esbuild audit findings.
- Stage summary and artifacts are in `.codex/stages/tj-order-cutover-review-fix/`.
- Graphify is not configured; no `graphify-out/GRAPH_REPORT.md` exists.

## Verification
- RED/GREEN tests were run for quote legacy leak, quantity legacy leak, and `legacy_migration_read` trace.
- `PYTHONDONTWRITEBYTECODE=1 PYTEST_ADDOPTS="-p no:cacheprovider" OPENROUTER_API_KEY=test uv run pytest tests/test_dialogue_order_runtime.py tests/test_llm_engine.py -q` passed: 330 passed.
- `OPENROUTER_API_KEY=test uv run ruff check src/ tests/` passed.
- `OPENROUTER_API_KEY=test uv run ruff format --check src/ tests/` passed: 293 files already formatted.
- `OPENROUTER_API_KEY=test uv run mypy src/` passed: no issues in 157 source files.
- Follow-up hardening targeted tests passed: `tests/test_dialogue_order_runtime.py tests/test_llm_engine.py` -> 332 passed.
- `frontend/admin`: `npm audit --json` reports 0 vulnerabilities; `npm run lint` and `npm run build` passed on local Node v24.16.0 with the existing package engine policy still set to `>=22.12.0 <23`.
- Latest `run_stage_closeout.py --stage tj-order-cutover-review-fix` reached full pytest `1400 passed, 19 skipped` but failed only because this handoff exceeded the 40-line limit; rerun after this compression.

## Next recommended
Next stage id: `tj-order-cutover-review-fix-delivery`
Recommended action: run canonical closeout, commit remaining hardening/docs, push current branch HEAD to `origin/main`, monitor GitHub Actions deploy, verify production release markers/smoke, then run the approved live E2E matrix.

## Starter prompt for next orchestrator
Use $orchestrator-stage. Continue from `/home/me/code/treejar/.worktrees/tj-order-cutover-review-fix`; read `.codex/stages/tj-order-cutover-review-fix/summary.md`, Beads `tj-s1qi`, `tj-order-cutover.10`, `tj-1ha9`, `tj-hqsa`, `tj-v2k9`, and git status/diff. User approved merge/deploy/live E2E in this active delivery thread; if resuming outside that context, ask again. Always ask before GitHub issue commenting or rollback/destructive production actions.

## Explicit defers
- #42 second-occurrence GitHub issue comment lacks a matching production evidence response; adding a GitHub comment is externally visible and has not been authorized separately.
- `tj-order-cutover.10` full route-family extraction remains open as a P2 architecture follow-up.
