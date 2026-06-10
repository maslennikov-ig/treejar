# Orchestrator Handoff
Updated: 2026-06-09
Current branch: `codex/tj-order-flow-cutover-plan`

## Current Truth
- Stage `tj-order-cutover`; worktree `/home/me/code/treejar/.worktrees/tj-gh51-order-quote-cutover`.
- Local regression-class implementation is verified: typed runtime quantity frames, mixed-line snapshot preservation, stale-frame aging, no new `pending_product_reference_quantity` writes on quantity-frame paths, and disabled assistant-prose quote item recovery.
- No deploy, push, production mutation, or live WhatsApp E2E was run.
- Docs updated: `docs/specs/dialogue-state-kernel.md`, `docs/specs/customer-facts-layer.md`; details in `.codex/stages/tj-order-cutover/summary.md`.
- Graphify is not configured; no `graphify-out/GRAPH_REPORT.md` exists.

## Verification
- `OPENROUTER_API_KEY=test uv run ruff check src/ tests/` passed.
- `OPENROUTER_API_KEY=test uv run ruff format --check src/ tests/` passed.
- `OPENROUTER_API_KEY=test uv run mypy src/` passed.
- `OPENROUTER_API_KEY=test env DYLD_FALLBACK_LIBRARY_PATH="${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}" uv run pytest tests/ -v --tb=short` passed: 1382 passed, 19 skipped.

## Reviews
- `correctness_reviewer` found mixed-line loss and stale-frame lifecycle; both fixed and tested.
- `improvement_reviewer` had no blocking findings; trace persistence and lifecycle improvements were accepted.

## Next recommended
Next stage id: `tj-order-cutover-delivery`
Recommended action: after explicit approval only, push/deploy and run live WhatsApp E2E for #42 second occurrence, #49/#50/#51, multi-item quote, compact details, SKU repair, bare quantity, blockers, and duplicate-message checks.

## Starter prompt for next orchestrator
Use $orchestrator-stage. Continue from `/home/me/code/treejar/.worktrees/tj-gh51-order-quote-cutover`; read `.codex/stages/tj-order-cutover/summary.md`, Beads `tj-order-cutover`, git status/diff, and ask for explicit approval before push, deploy, production mutation, or live E2E.

## Explicit defers
- External delivery actions require approval.
- Follow-up hardening: replace remaining order/quote-specific `engine.py` branches with one runtime decision adapter.
- `tj-gh21` waits for approved Wazzup WABA EN/AR templates.
