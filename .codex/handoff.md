# Orchestrator Handoff
Updated: 2026-06-15
Current branch: `codex/tj-order-cutover-rework`

## Current Truth
- Stage `tj-order-cutover`; worktree `/home/me/code/treejar/.worktrees/tj-order-cutover-rework`.
- Local #52 rework is verified on top of `origin/main` `d0b5dda`: `point/points` quantity parsing, `CH 615 NEW black 6 point` selection confirmation, durable `order_runtime.quote_frame` before quote details, compact slash-labeled customer details, and no assistant-prose quote recovery.
- No deploy, push, production mutation, GitHub issue update, or live WhatsApp E2E has been run for the 2026-06-15 rework yet.
- Docs updated: `docs/specs/dialogue-state-kernel.md`, `docs/specs/customer-facts-layer.md`; details in `.codex/stages/tj-order-cutover/summary.md`.
- Graphify is not configured; no `graphify-out/GRAPH_REPORT.md` exists.

## Verification
- `OPENROUTER_API_KEY=test uv run pytest tests/test_dialogue_order_runtime.py::test_order_runtime_accepts_point_as_trailing_unit_count tests/test_llm_engine.py::test_extract_purchase_selection_accepts_position_quantity_phrases tests/test_llm_engine.py::test_order_cutover_gh52_customer_details_resume_after_point_selection_confirmation -q` passed: 8 passed.
- `OPENROUTER_API_KEY=test uv run pytest tests/test_dialogue_order_runtime.py tests/test_llm_engine.py -q` passed: 325 passed.
- `OPENROUTER_API_KEY=test uv run ruff check src/ tests/` passed.
- `OPENROUTER_API_KEY=test uv run ruff format --check src/ tests/` passed.
- `OPENROUTER_API_KEY=test uv run mypy src/` passed: no issues in 157 source files.
- `OPENROUTER_API_KEY=test env DYLD_FALLBACK_LIBRARY_PATH="${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}" uv run pytest tests/ -v --tb=short` passed: 1394 passed, 19 skipped, after local `npm ci` in `frontend/admin` installed `esbuild` for frontend regression scripts.

## Reviews
- `correctness_reviewer` found mixed-line loss and stale-frame lifecycle; both fixed and tested.
- `improvement_reviewer` had no blocking findings; trace persistence and lifecycle improvements were accepted.

## Next recommended
Next stage id: `tj-order-cutover`
Recommended action: commit/push/deploy the rework, confirm production SHA, run `uv run python scripts/verify_api.py --base-url https://noor.starec.ai`, then run live WhatsApp E2E on `+79262810921` for #42 second occurrence, #49/#50/#51/#52, multi-item quote, compact details, SKU repair, bare quantity, blockers, and duplicate-message checks.

## Starter prompt for next orchestrator
Use $orchestrator-stage. Continue from `/home/me/code/treejar/.worktrees/tj-order-cutover-rework`; read `.codex/stages/tj-order-cutover/summary.md`, Beads `tj-order-cutover`, git status/diff, and complete delivery/live E2E if not already done.

## Explicit defers
- External delivery actions for the 2026-06-15 rework are still pending.
- Follow-up hardening: replace remaining order/quote-specific `engine.py` branches with one runtime decision adapter.
- `tj-gh21` waits for approved Wazzup WABA EN/AR templates.
