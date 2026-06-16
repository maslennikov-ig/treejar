# Orchestrator Handoff
Updated: 2026-06-16
Current branch: `codex/tj-order-sideeffect-adapter`

## Current Truth
- Stage `tj-order-adapter-hardening`; worktree `/home/me/code/treejar/.worktrees/tj-order-sideeffect-adapter`.
- Side-effect adapter hardening commit `8bce80194cd3640d30a8a5c25e66cc85c3eeadff` is pushed to `origin/main` and deployed by CI run `27602099718`; deploy job `81605605844`.
- Production API smoke passed against `https://noor.starec.ai`: `verify_api.py` -> 8 passed, 0 failed. Local SSH alias `noor` does not resolve, so release-marker SSH readback was not repeated from this environment.
- Beads `tj-order-cutover.5` is closed. Broader route-selection extraction is tracked as `tj-order-cutover.10`.
- #52 point/points parsing, durable `order_runtime.quote_frame`, compact slash-labeled details, no assistant-prose quote recovery, and commercial blocker handoff are verified.
- GitHub issues #49, #50, #51, and #52 were closed with production evidence comments.
- Stage docs updated: `.codex/stages/tj-order-adapter-hardening/summary.md`. No product/spec docs changed for the adapter refactor.
- Graphify is not configured; no `graphify-out/GRAPH_REPORT.md` exists.

## Verification
- Adapter hardening local gates passed: structural RED/GREEN, targeted order/quote 6 passed, engine/runtime 327 passed, ruff, format, mypy, and full pytest `1396 passed, 19 skipped`.
- GitHub Actions run `27602099718` passed changes/lint/test/type-check/deploy. Duplicate manual workflow_dispatch run `27602134953` was cancelled before delivery to avoid double deploy.
- Production smoke passed after deploy: `uv run python scripts/verify_api.py --base-url https://noor.starec.ai` -> 8 passed, 0 failed.
- Rework local gates passed before first deploy: targeted 8 passed, engine/runtime 325 passed, ruff, format, mypy, and full pytest `1394 passed, 19 skipped`.
- Hotfix local gates passed: targeted regression 5 passed, classifier regression 6 passed, rework regression 9 passed, ruff, format, mypy, and full pytest `1395 passed, 19 skipped`.
- GitHub Actions run `27535297609` passed changes/lint/test/type-check/deploy.
- Production smoke passed: `uv run python scripts/verify_api.py --base-url https://noor.starec.ai` -> 8 passed, 0 failed.
- Live WhatsApp E2E passed on `+79262810921`: #52, #52quote, #42 original/equivalent, #49/#50/#51 quote `Fr3389`, and blocker2 verified-policy handoff.
- DB readback found no consecutive duplicate assistant replies; #50 is `order_runtime.quote_frame.status=quoted`, #52quote is `collecting_details`.

## Reviews
- No spawned reviewer was used for `tj-order-adapter-hardening`; user did not request subagents. Existing order-cutover reviewer findings for mixed-line loss and stale-frame lifecycle remain fixed and tested.

## Next recommended
Next stage id: `tj-order-route-selection-extraction`
Recommended action: only if desired, work Beads `tj-order-cutover.10` to move the remaining deterministic order/quote route-selection branches out of `process_message`; otherwise resume `tj-gh21` only after Wazzup templates are approved.

## Starter prompt for next orchestrator
Use $orchestrator-stage. Start from `/home/me/code/treejar`; read `.codex/handoff.md`, `.codex/stages/tj-order-adapter-hardening/summary.md`, `.codex/stages/tj-order-cutover/summary.md`, and Beads before further order/quote runtime changes.

## Explicit defers
- Follow-up hardening: `tj-order-cutover.10` tracks extracting remaining deterministic order/quote route-selection branches from `process_message`.
- `tj-gh21` waits for approved Wazzup WABA EN/AR templates.
