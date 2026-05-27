# Orchestrator Handoff
Updated: 2026-05-27
Current branch: `main`

## Current Truth
- Canonical host: `https://noor.starec.ai`; runtime path: `/opt/noor`.
- `main` matches `origin/main` at evidence commit `c4d59a40d9a65452e31b22b743124b6303b39506`; the docs-only evidence push was path-ignored by CI.
- Production runtime is `fba5df0a7c79e334b39ec4bd2dafa0cf4d6a2308`: `.release-sha=fba5df0a7c79e334b39ec4bd2dafa0cf4d6a2308`, `.release-run-id=26497377622`.
- `tj-mmj8`, `tj-4cm4`, `tj-8ma2`, and `tj-4xnf` are merged, deployed, live-E2E verified/triaged, cleaned, and closed in Beads.
- `tj-4xnf` fixed the remaining Zoho Inventory customer-resolution failure after prior duplicate-name fallback commit `e97bbb4`: synthetic phone suffixes no longer leak into Inventory lookup/create.
- Local `tj-4xnf` fix strips repo-owned `#...` suffixes only at the Zoho Inventory contact boundary, while preserving suffixed phones inside app conversation storage.
- Local verification passed: RED/GREEN synthetic suffix regression, `tests/test_llm_quotation.py` plus Inventory tests (`20 passed`), relevant engine quote tests (`46 passed`), ruff, format check, mypy, and full stage closeout (`1181 passed, 19 skipped`).
- `tj-nzob` was checked and is not solved: comma-separated brief parsing still misses `company=LLD`.
- `tj-4xnf` production E2E conversation `4c2156c6-1763-435e-aa3d-7965631a96f3` created quotation `Fr3316` / sale order `378603000022228007`; synthetic conversations were closed after evidence.
- Stage evidence: `.codex/stages/tj-4xnf/summary.md`, `.codex/stages/tj-4xnf/artifacts/tj-4xnf-local-implementation.md`, and `.codex/stages/tj-4xnf/artifacts/tj-4xnf-production-e2e.md`.

## Next recommended
Next stage id: `tj-nzob`.
Recommended action: fix comma-separated ordered quote brief parsing so `Lilia, LLD, Lfdsf@kfsl.ru, 2 street` preserves `company=LLD`.

## Starter prompt for next orchestrator
Use $orchestrator-stage. Continue from clean `main` at `c4d59a40d9a65452e31b22b743124b6303b39506`; production runtime remains code/evidence delivery SHA `fba5df0a7c79e334b39ec4bd2dafa0cf4d6a2308` via GitHub Actions run `26497377622`. Start `tj-nzob`: verify prior parser work, add RED/GREEN coverage for comma-separated ordered quote brief `Lilia, LLD, Lfdsf@kfsl.ru, 2 street`, keep slash/multiline/labeled brief behavior intact, run local gates, and do not deploy/live-test without explicit approval.

## Explicit defers
- `tj-nzob`: comma-separated ordered brief stores name/email/address but misses company; slash and multiline formats are already covered.
- `tj-final27.6`: referral launch remains blocked pending written client referral policy or explicit exclusion.
- Dialogue kernel `enforce` rollout remains deferred; production is intentionally `shadow` only.
