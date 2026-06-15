# Orchestrator Handoff
Updated: 2026-06-15
Current branch: `codex/tj-order-cutover-rework`

## Current Truth
- Stage `tj-order-cutover`; worktree `/home/me/code/treejar/.worktrees/tj-order-cutover-rework`.
- Rework and hotfix are deployed. Production marker: `.release-sha=4bcab4d1d9e91a7cfcc69ff940acec68ac54b913`, `.release-run-id=27535297609`; deploy job `81383375571`.
- #52 point/points parsing, durable `order_runtime.quote_frame`, compact slash-labeled details, no assistant-prose quote recovery, and commercial blocker handoff are verified.
- GitHub issues #49, #50, #51, and #52 were closed with production evidence comments.
- Docs updated: `docs/specs/dialogue-state-kernel.md`, `docs/specs/customer-facts-layer.md`, and `.codex/stages/tj-order-cutover/summary.md`.
- Graphify is not configured; no `graphify-out/GRAPH_REPORT.md` exists.

## Verification
- Rework local gates passed before first deploy: targeted 8 passed, engine/runtime 325 passed, ruff, format, mypy, and full pytest `1394 passed, 19 skipped`.
- Hotfix local gates passed: targeted regression 5 passed, classifier regression 6 passed, rework regression 9 passed, ruff, format, mypy, and full pytest `1395 passed, 19 skipped`.
- GitHub Actions run `27535297609` passed changes/lint/test/type-check/deploy.
- Production smoke passed: `uv run python scripts/verify_api.py --base-url https://noor.starec.ai` -> 8 passed, 0 failed.
- Live WhatsApp E2E passed on `+79262810921`: #52, #52quote, #42 original/equivalent, #49/#50/#51 quote `Fr3389`, and blocker2 verified-policy handoff.
- DB readback found no consecutive duplicate assistant replies; #50 is `order_runtime.quote_frame.status=quoted`, #52quote is `collecting_details`.

## Reviews
- `correctness_reviewer` findings for mixed-line loss and stale-frame lifecycle were fixed and tested.
- `improvement_reviewer` had no blocking findings.

## Next recommended
Next stage id: `tj-order-cutover`
Recommended action: stage closeout is complete after `run_stage_closeout.py` passes; next work should start a new stage for engine runtime-adapter hardening or resume `tj-gh21` only after Wazzup templates are approved.

## Starter prompt for next orchestrator
Use $orchestrator-stage. Start from `/home/me/code/treejar`; read `.codex/handoff.md`, `.codex/stages/tj-order-cutover/summary.md`, and Beads before further order/quote runtime changes.

## Explicit defers
- Follow-up hardening: replace remaining order/quote-specific `engine.py` branches with one runtime decision adapter.
- `tj-gh21` waits for approved Wazzup WABA EN/AR templates.
