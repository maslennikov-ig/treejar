# Stage tj-order-route-module-extract: Order/Quote Route Module Extraction

Updated: 2026-06-16
Status: stage closeout passed; delivery pending
Branch: `codex/tj-order-route-module-extract`
Worktree: `/home/me/code/treejar/.worktrees/tj-order-route-module-extract`
Beads: `tj-kk3y` closed

docs-reviewed: updated - `.codex/project-index.md` now lists
`src/llm/order_quote_routes.py` as the deterministic order/quote route adapter.
graph-reviewed: no-change-needed - Graphify is not configured in this worktree;
no `graphify-out/GRAPH_REPORT.md` exists.
project-index: updated - stable `src/llm/` ownership boundary changed.

## Goal

Physically move the order/quote route adapter out of `src/llm/engine.py` after
the previous route-adapter delivery, without changing runtime behavior.

## Parallel Decomposition Matrix

| Stream | Goal | Agent | Write zone | Dependencies | Verification | Decision | Reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A: module extraction | Move adapter ownership to `src/llm/order_quote_routes.py` | local orchestrator | `src/llm/engine.py`, `src/llm/order_quote_routes.py`, `tests/test_llm_engine.py` | existing route adapter on `origin/main` | RED structural test, engine/quote tests, full gates | local/sequential | one tightly coupled import boundary; parallel writes would increase circular-import and behavior drift risk |
| B: closeout docs | Record structural ownership change | local orchestrator | `.codex/project-index.md`, `.codex/handoff.md`, `.codex/stages/tj-order-route-module-extract` | stream A result | stage closeout | local/sequential | docs must reflect accepted code shape |

No spawned subagents were used. This was one write zone with high circular-import
risk and no independent parallel stream.

## Scope

- Added `src/llm/order_quote_routes.py`.
- Moved `QuotationItem`, `OrderQuoteSideEffectPlan`,
  `_execute_order_quote_side_effect`, `_append_quote_effect_trace`, and
  `_order_quote_route_for_turn` out of `src/llm/engine.py`.
- Kept `src/llm/engine.py::process_message` as the turn-preparation entrypoint;
  it imports and delegates to `_order_quote_route_for_turn`.
- Kept `create_quotation` in `engine.py` as the PydanticAI tool and side-effect
  owner.
- Added a structural regression test that fails if `_order_quote_route_for_turn`
  moves back into `engine.py`.
- Updated the structural `create_quotation` ownership test to inspect the new
  adapter module.
- Used lazy helper binding from `order_quote_routes.py` back to `engine.py` only
  after engine import completes, avoiding import-time circular dependency while
  preserving existing helper behavior and pytest monkeypatch semantics.

## Verification

- RED:
  - `OPENROUTER_API_KEY=test uv run pytest tests/test_llm_engine.py::test_order_quote_route_adapter_is_in_dedicated_module -q`
    failed with `ModuleNotFoundError: No module named 'src.llm.order_quote_routes'`.
- GREEN / targeted:
  - `OPENROUTER_API_KEY=test uv run pytest tests/test_llm_engine.py::test_order_quote_route_adapter_is_in_dedicated_module tests/test_llm_engine.py::test_order_quote_create_quotation_calls_are_adapter_owned tests/test_llm_engine.py::test_process_message_order_quote_route_selection_is_adapter_owned -q`
    passed: 3 passed.
  - `OPENROUTER_API_KEY=test uv run pytest tests/test_llm_quotation.py tests/test_e2e_tools.py -q`
    passed: 24 passed.
  - First full `tests/test_llm_engine.py -q` run exposed a lazy-binding cache
    issue where pytest monkeypatches for `create_quotation` and
    `_resolve_exact_quote_candidate_sku` were not refreshed between scenarios.
    The adapter now rebinds helper globals on each route entry.
  - `OPENROUTER_API_KEY=test uv run pytest tests/test_llm_engine.py -q`
    passed after the rebinding fix: 329 passed.
  - First full pytest run failed only in `tests/test_admin_dashboard_frontend.py`
    because fresh `frontend/admin/node_modules` lacked `esbuild`.
  - `npm ci` in `frontend/admin` installed 90 packages; npm reported 0
    vulnerabilities and the existing local Node engine warning
    (`v24.16.0` vs package `>=22.12.0 <23`).
  - `OPENROUTER_API_KEY=test uv run pytest tests/test_admin_dashboard_frontend.py -q`
    passed after `npm ci`: 11 passed.
- Full local gates:
  - `OPENROUTER_API_KEY=test uv run ruff check src/ tests/` passed.
  - `OPENROUTER_API_KEY=test uv run ruff format --check src/ tests/` passed.
  - `OPENROUTER_API_KEY=test uv run mypy src/` passed: no issues in 158 source
    files.
  - `OPENROUTER_API_KEY=test env DYLD_FALLBACK_LIBRARY_PATH="${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}" uv run pytest tests/ -v --tb=short`
    passed: 1419 passed, 19 skipped.
  - `scripts/orchestration/run_stage_closeout.py --stage tj-order-route-module-extract`
    passed: artifact validation OK, process verification OK, project-index/docs
    review OK, debt marker scan OK, full code-change verification OK, and stage
    closeout verification OK.

## Changed Files

- `src/llm/order_quote_routes.py`
- `src/llm/engine.py`
- `tests/test_llm_engine.py`
- `.codex/project-index.md`
- `.codex/handoff.md`
- `.codex/stages/tj-order-route-module-extract/summary.md`
- `.codex/stages/tj-order-route-module-extract/artifacts/tj-kk3y.md`
- `docs/superpowers/plans/2026-06-16-order-route-module-extract.md`

## Delivery

Delivery is pending. This stage has passed local gates and stage closeout, and
still needs commit, delivery to `main`, CI/deploy monitoring, production
marker/smoke, and a focused live order/quote E2E sanity pass before tester
handoff.

## Explicit Defers

- No code defers for `tj-kk3y`.
- Deployment and live E2E are intentionally pending until after closeout/commit.
