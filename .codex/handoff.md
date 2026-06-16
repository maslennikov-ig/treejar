# Orchestrator Handoff
Updated: 2026-06-16
Current branch: `codex/tj-order-cutover-review-fix`

## Current Truth
- Stage `tj-order-cutover-review-fix`; worktree `/home/me/code/treejar/.worktrees/tj-order-cutover-review-fix`.
- Beads `tj-s1qi` is in progress for the local review-and-fix pass.
- Source of truth was `origin/main` at `b03227e`; no push, deploy, production mutation, or live WhatsApp E2E was run in this pass.
- Three read-only reviewer streams were used: `correctness_reviewer`, `improvement_reviewer`, and `architect_reviewer`.
- Accepted and fixed locally: invalid canonical quote frame no longer falls back to stale legacy quote selection; expired/non-answerable typed quantity frame suppresses stale legacy `pending_product_reference_quantity`; `legacy_migration_read` trace now records legacy metadata reads.
- Stage summary and artifacts are in `.codex/stages/tj-order-cutover-review-fix/`.
- Graphify is not configured; no `graphify-out/GRAPH_REPORT.md` exists.

## Verification
- RED/GREEN tests were run for quote legacy leak, quantity legacy leak, and `legacy_migration_read` trace.
- `PYTHONDONTWRITEBYTECODE=1 PYTEST_ADDOPTS="-p no:cacheprovider" OPENROUTER_API_KEY=test uv run pytest tests/test_dialogue_order_runtime.py tests/test_llm_engine.py -q` passed: 330 passed.
- `OPENROUTER_API_KEY=test uv run ruff check src/ tests/` passed.
- `OPENROUTER_API_KEY=test uv run ruff format --check src/ tests/` passed: 293 files already formatted.
- `OPENROUTER_API_KEY=test uv run mypy src/` passed: no issues in 157 source files.
- Stage closeout full pytest passed after local `npm ci` in `frontend/admin`: 1399 passed, 19 skipped. `npm ci` reported local Node v24.16.0 outside the package engine range `>=22.12.0 <23` and 2 high severity audit findings.
- Final `scripts/orchestration/run_stage_closeout.py --stage tj-order-cutover-review-fix` passed: artifact validation OK, process verification OK, stage closeout verification OK.

## Reviews
- `correctness_reviewer` found the quantity legacy fallback leak and trace observability gap; both fixed.
- `improvement_reviewer` found the invalid canonical quote frame legacy leak; fixed. It also recommended route-selection extraction and quote diagnostics follow-ups.
- `architect_reviewer` returned Conditional Pass: production flow is sound enough, but route selection still needs extraction from `process_message`.

## Next recommended
Next stage id: `tj-order-cutover-review-fix-delivery`
Recommended action: review/commit/push this branch only after explicit approval. If delivery is deferred, continue with `tj-order-cutover.10` only when ready for the broader behavior-preserving route-selection extraction.

## Starter prompt for next orchestrator
Use $orchestrator-stage. Continue from `/home/me/code/treejar/.worktrees/tj-order-cutover-review-fix`; read `.codex/stages/tj-order-cutover-review-fix/summary.md`, Beads `tj-s1qi`, `tj-order-cutover.10`, `tj-1ha9`, `tj-hqsa`, and git status/diff. Ask for explicit approval before push, deploy, production mutation, GitHub issue commenting, or live E2E.

## Explicit defers
- External delivery actions require explicit approval.
- `tj-order-cutover.10`: extract deterministic order/quote route selection from `process_message`.
- `tj-1ha9`: move unresolved-only quote repair into typed runtime state.
- `tj-hqsa`: add bounded quote frame lifecycle diagnostics.
- `tj-v2k9`: audit frontend admin npm vulnerabilities and Node engine range surfaced by local `npm ci`.
- #42 second-occurrence GitHub issue comment lacks a matching production evidence response; adding a GitHub comment is externally visible and was not done.
