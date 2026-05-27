# Orchestrator Handoff
Updated: 2026-05-27
Current branch: `codex/tj-nzob-comma-brief`

## Current Truth
- Canonical host: `https://noor.starec.ai`; runtime path: `/opt/noor`.
- `main` matches `origin/main` at evidence commit `c6185f2c85373ed9409abd30208554411d70ec75`; the docs-only evidence push was path-ignored by CI.
- Production runtime is `fba5df0a7c79e334b39ec4bd2dafa0cf4d6a2308`: `.release-sha=fba5df0a7c79e334b39ec4bd2dafa0cf4d6a2308`, `.release-run-id=26497377622`.
- `tj-mmj8`, `tj-4cm4`, `tj-8ma2`, and `tj-4xnf` are merged, deployed, live-E2E verified/triaged, cleaned, and closed in Beads.
- `tj-4xnf` fixed the remaining Zoho Inventory customer-resolution failure after prior duplicate-name fallback commit `e97bbb4`: synthetic phone suffixes no longer leak into Inventory lookup/create.
- Local `tj-4xnf` fix strips repo-owned `#...` suffixes only at the Zoho Inventory contact boundary, while preserving suffixed phones inside app conversation storage.
- Local verification passed: RED/GREEN synthetic suffix regression, `tests/test_llm_quotation.py` plus Inventory tests (`20 passed`), relevant engine quote tests (`46 passed`), ruff, format check, mypy, and full stage closeout (`1181 passed, 19 skipped`).
- `tj-nzob` local implementation is complete on `codex/tj-nzob-comma-brief`: comma-separated ordered brief parsing now preserves `company=LLD`; local ruff, format, mypy, targeted tests, `tests/test_llm_engine.py`, full pytest (`1182 passed, 19 skipped`), and `scripts/orchestration/run_stage_closeout.py --stage tj-nzob` passed after installing frontend admin dependencies; not merged, pushed, deployed, live-E2E tested, or closed.
- `tj-4xnf` production E2E conversation `4c2156c6-1763-435e-aa3d-7965631a96f3` created quotation `Fr3316` / sale order `378603000022228007`; synthetic conversations were closed after evidence.
- Stage evidence: `.codex/stages/tj-4xnf/summary.md`, `.codex/stages/tj-4xnf/artifacts/tj-4xnf-local-implementation.md`, and `.codex/stages/tj-4xnf/artifacts/tj-4xnf-production-e2e.md`.
- Current `tj-nzob` evidence: `.codex/stages/tj-nzob/summary.md` and `.codex/stages/tj-nzob/artifacts/tj-nzob-local-implementation.md`.

## Next recommended
Next stage id: `tj-nzob`.
Recommended action: request explicit approval before merge/push/deploy/live E2E for `tj-nzob`.

## Starter prompt for next orchestrator
Use $orchestrator-stage. Continue from branch `codex/tj-nzob-comma-brief` based on `main`/`origin/main` at `c6185f2c85373ed9409abd30208554411d70ec75`; production runtime remains SHA `fba5df0a7c79e334b39ec4bd2dafa0cf4d6a2308` via GitHub Actions run `26497377622`. `tj-nzob` local gates and stage closeout passed. Next safe step is to request/confirm explicit approval before merge, push, deploy, production smoke, live WhatsApp E2E, Beads closure, or branch cleanup.

## Explicit defers
- `tj-nzob`: merge, push, deploy, production smoke, live WhatsApp E2E, Beads closure, and branch cleanup remain pending explicit approval after local verification.
- `tj-final27.6`: referral launch remains blocked pending written client referral policy or explicit exclusion.
- Dialogue kernel `enforce` rollout remains deferred; production is intentionally `shadow` only.
