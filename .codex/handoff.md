# Orchestrator Handoff
Updated: 2026-05-26
Current branch: `codex/tj-4xnf-zoho-customer-fallback`

## Current Truth
- Canonical host: `https://noor.starec.ai`; runtime path: `/opt/noor`.
- Base `main` / `origin/main`: `069e4f91bb5b2d1b4c4b1c6b45d1e5caac11bc94`.
- Production runtime remains code commit `80e6f4371da44f163406f76f30f858e94d35da4a`: `.release-sha=80e6f4371da44f163406f76f30f858e94d35da4a`, `.release-run-id=26462939020`.
- `tj-mmj8`, `tj-4cm4`, and `tj-8ma2` are merged, deployed, live-E2E verified/triaged, cleaned, and closed in Beads.
- `tj-4xnf` is now the active local stage. Prior duplicate-name fallback commit `e97bbb4` is present, but fresh `tj-8ma2` live evidence showed a different remaining failure: synthetic phone suffix leaked into Zoho Inventory customer lookup/create.
- Local `tj-4xnf` fix strips repo-owned `#...` suffixes only at the Zoho Inventory contact boundary, while preserving suffixed phones inside app conversation storage.
- Local verification passed: RED/GREEN synthetic suffix regression, `tests/test_llm_quotation.py` plus Inventory tests (`20 passed`), relevant engine quote tests (`46 passed`), ruff, format check, mypy, and full stage closeout (`1181 passed, 19 skipped`).
- `tj-nzob` was checked and is not solved: comma-separated brief parsing still misses `company=LLD`.
- Stage evidence: `.codex/stages/tj-4xnf/summary.md` and `.codex/stages/tj-4xnf/artifacts/tj-4xnf-local-implementation.md`.

## Next recommended
Next stage id: `tj-4xnf`.
Recommended action: decide whether to merge/push/deploy and run bounded live E2E for the same sales-order quote path.

## Starter prompt for next orchestrator
Use $orchestrator-stage. Continue from branch `codex/tj-4xnf-zoho-customer-fallback`. Local fix strips synthetic `#...` suffixes before Zoho Inventory customer lookup/create. Verify with repo gates, then if owner approves delivery, merge to `main`, push, wait for CI/deploy, smoke production, and live-E2E retest conversation shape `sales order 5 x CH 620` -> `5 x CH 620 grey` -> `Lilia / LLD / Lfdsf@kfsl.ru / 2 street`.

## Explicit defers
- `tj-4xnf`: merge/push/deploy/live E2E pending explicit owner approval.
- `tj-nzob`: comma-separated ordered brief stores name/email/address but misses company; slash and multiline formats are already covered.
- `tj-final27.6`: referral launch remains blocked pending written client referral policy or explicit exclusion.
- Dialogue kernel `enforce` rollout remains deferred; production is intentionally `shadow` only.
