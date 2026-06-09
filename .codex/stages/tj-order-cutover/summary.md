# Stage tj-order-cutover: Full Order/Quote Flow Cutover

Updated: 2026-06-09
Status: planned, not implemented
Branch: `codex/tj-order-flow-cutover-plan`
Base: `origin/main` at `3d37eb1cd6002aea6919ff07f01c7c03beeb8e10`
Beads: `tj-order-cutover`

docs-reviewed: updated - `docs/specs/dialogue-state-kernel.md`,
`docs/specs/customer-facts-layer.md`, and
`docs/superpowers/plans/2026-06-09-order-flow-cutover.md` now define the full
cutover.
graph-reviewed: no-change-needed - Graphify is not configured in this worktree;
no `graphify-out/GRAPH_REPORT.md` exists.

## Goal

Finish the migration from scattered order/quote branch logic to one typed
runtime-owned frame. The direct motivation is the recurring issue family #40-#51,
including the second #42 occurrence and open #49/#50/#51. The architectural goal
is to stop similar regressions by removing mixed ownership, not by adding another
phrase-specific patch.

## Current Evidence

- Production currently points to `3d37eb1` after the GH51 deployment.
- GH51 live E2E passed, but closed #42 received a second occurrence on
  2026-06-08: `SK 45 White` -> quantity prompt -> `2` -> generic opener.
- Code review found the remaining risk: `order_runtime` exists but does not own
  the full order/quote transition. `src/llm/engine.py` still owns many
  order/quote outcomes through branch order and legacy metadata.

## Root Cause

The system has multiple order/quote state owners:

- `order_runtime.quote_frame`;
- `pending_product_reference_quantity`;
- `pending_quote_selection`;
- `quote_customer_details`;
- expected-answer frames;
- recent assistant prose and assistant-prose quote recovery;
- branch ordering inside `src/llm/engine.py`.

This lets one scenario pass while an adjacent customer wording follows a
different owner and loses context. The fundamental fix is to make typed runtime
state the only order/quote authority and leave legacy keys as migration or
diagnostic fallback.

## Planned Tasks

- `tj-order-cutover.1`: RED replay matrix and failing invariants for #40-#51.
- `tj-order-cutover.2`: final typed frame contract and migration rules.
- `tj-order-cutover.3`: runtime-owned quantity frames.
- `tj-order-cutover.4`: runtime-owned quote selection and SKU repair.
- `tj-order-cutover.5`: side-effect adapter and order/quote branch removal from
  `src/llm/engine.py`.
- `tj-order-cutover.6`: customer facts, memory, and dialogue kernel alignment.
- `tj-order-cutover.7`: observability and review-fix gate.
- `tj-order-cutover.8`: full verification, delivery, live E2E, docs, and
  closeout.

## Required Verification

- RED/GREEN replay tests for #40-#51, with explicit coverage for the second #42
  occurrence.
- `uv run ruff check src/ tests/`
- `uv run ruff format --check src/ tests/`
- `uv run mypy src/`
- `env DYLD_FALLBACK_LIBRARY_PATH="${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}" uv run pytest tests/ -v --tb=short`
- `scripts/orchestration/run_stage_closeout.py --stage tj-order-cutover`
- Deploy and live WhatsApp E2E only after explicit user approval.

## Prompt Pack

The next orchestrator prompt is stored in
`.codex/stages/tj-order-cutover/artifacts/next-orchestrator-prompt.md`.

## Explicit Defers

- No implementation, push, merge, deploy, or live WhatsApp testing was performed
  in this planning stage.
- `tj-gh21` remains blocked on approved Wazzup WABA EN/AR templates.
