# Stage tj-gh56-product-media-sku Summary

Updated: 2026-06-27
Status: delivered, deployed, and closed
Branch: `main`
Base: `origin/main@b28c246af13db58cae921e4ff08705831c3ae8ad`
Commit: `6df39c72ef6d4b79de67b58a9c6f29a7771293ab`
Beads: `tj-jyig`, external ref `gh-56`, closed

docs-reviewed: no-change-needed - this is a narrow runtime behavior bugfix
covered by regression tests; no public API, operator workflow, deployment,
integration, or durable architecture contract changed.
graph-reviewed: no-change-needed - Graphify is not configured; no
`graphify-out/GRAPH_REPORT.md` or `[knowledge_graph]` configuration exists.
project-index: reviewed-no-change - no stable entrypoint, route, subsystem,
integration, verification command, or ownership boundary changed.

## Goal

Fix GitHub #56 where the bot text selected
`Convertible Sleeper Skyland Chair (Beige)` / SKU `CSC-01 beige`, but product
media could include a normal non-convertible chair image.

## Root Cause

`search_products` queued media for every RAG top-3 result with `image_url`
before the final assistant response existed. If the RAG result set included one
exact convertible/sleeper chair and one nearby generic chair, the text could
emphasize the exact SKU while deferred media still sent both images.

Secondary remaining possibility: catalog data for `CSC-01 beige` may itself have
a wrong primary image. This was not proven or mutated locally.

## Implementation

- Added an exact-match media filter inside `src/llm/engine.py::search_products`.
- When the aggregate product result contains exact matches, only per-product
  exact matches can queue/send product media.
- Suppressed nearby products remain in the tool text as alternatives, but do not
  get the hidden "image will be sent" note.
- Added a RED/GREEN regression in `tests/test_product_images.py` for an exact
  convertible sleeper product plus a nearby visitor chair.

## Routing Result

- Documentation: Docs L1/L2 attempted for `pydantic-ai@1.30.1` and
  `sqlalchemy@2.0.47`; both returned `fallback-needed`. No external API docs
  blocked the local product-media fix.
- Knowledge Graph: not configured.
- Selected skills: `orchestrator-stage`, `task-router`, `process-issues`,
  `systematic-debugging`, `test-driven-development`, `writing-plans`,
  `verification-before-completion`, `orchestration-closeout`.
- Selected agents/personas: visible read-only `code_mapper` and `debugger`.
- Catalog candidates: none.

## Parallel Decomposition Matrix

| Stream | Goal | Agent | Write zone | Dependencies | Verification | Decision | Reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A | Map product-media path | `code_mapper` | read-only | none | file/line evidence | parallel | Independent path mapping. |
| B | Root-cause and RED strategy | `debugger` | read-only | none | evidence + proposed test | parallel | Independent debugging lens. |
| C | RED/GREEN fix | local | `src/llm/engine.py`, `tests/test_product_images.py` | A/B findings | targeted tests + gates | sequential | One shared runtime path; local owner should integrate. |
| D | Closeout | local | stage docs, handoff, Beads | C verification | stage closeout | sequential | Requires final command evidence. |

## Verification Evidence

Passed:

- RED:
  `OPENROUTER_API_KEY=dummy uv run --extra dev pytest tests/test_product_images.py::test_search_products_defers_only_exact_match_media_when_query_has_specific_modifier -q`
  failed before implementation because both exact and nearby media were queued.
- GREEN targeted:
  `OPENROUTER_API_KEY=dummy uv run --extra dev pytest tests/test_product_images.py::test_search_products_defers_only_exact_match_media_when_query_has_specific_modifier -q`
  passed.
- Targeted media:
  `OPENROUTER_API_KEY=dummy uv run --extra dev pytest tests/test_product_images.py tests/test_services_chat_batch.py::test_process_incoming_batch_sends_deferred_product_media_after_bot_reply -q`
  passed: 9 passed.
- `uv run --extra dev ruff check src/ tests/` passed.
- `uv run --extra dev ruff format --check src/ tests/` passed.
- `uv run --extra dev mypy src/` passed.
- Full pytest initially failed only because fresh worktree lacked
  `frontend/admin/node_modules/esbuild`. `npm ci` in `frontend/admin` installed
  the existing frontend dependencies; npm warned local Node `v24.16.0` is above
  the declared `<23` range.
- Full pytest after dependency install:
  `OPENROUTER_API_KEY=dummy env DYLD_FALLBACK_LIBRARY_PATH="${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}" uv run --extra dev pytest tests/ -v --tb=short`
  passed: 1431 passed, 19 skipped.
- Stage closeout:
  `scripts/orchestration/run_stage_closeout.py --stage tj-gh56-product-media-sku`
  passed.
- CI/deploy run:
  `https://github.com/maslennikov-ig/treejar/actions/runs/28278326716`
  passed, including deploy.
- Production smoke:
  `uv run python scripts/verify_api.py --base-url https://noor.starec.ai`
  passed: 8 passed, 0 failed.
- VPS release check:
  `/opt/noor/.release-sha` is
  `6df39c72ef6d4b79de67b58a9c6f29a7771293ab`; `.release-run-id` is
  `28278326716`.

## Delivery

Completed on 2026-06-27:

- committed `fix(llm): restrict product media to exact matches`
- pushed feature branch `origin/codex/tj-gh56-product-media-sku`
- fast-forwarded `origin/main` to `6df39c7`
- deployed through the `main` GitHub Actions workflow
- commented on GH #56 and closed it as completed
- closed Beads `tj-jyig`
- removed the local GH56 stage worktree and local feature branch

Live WhatsApp E2E and catalog/prod data audit are not part of this delivery
unless separately needed.

## Explicit Defers

- Read-only live/catalog audit can still distinguish whether the incident media
  came from an extra nearby RAG product or from a wrong primary image on
  `CSC-01 beige`.
- No GH #56 delivery, deploy, Beads, or GitHub mutation remains pending.
