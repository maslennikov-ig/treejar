# Orchestrator Handoff
Updated: 2026-05-27
Current branch: `main`

## Current Truth
- Canonical host: `https://noor.starec.ai`; runtime path: `/opt/noor`.
- `main` includes delivered `tj-nzob` runtime commit `cefea6e6f9f37f3554af1980a68861705f6bc8e6`; any later docs-only evidence commit is not part of the deployed runtime.
- Production runtime is `cefea6e6f9f37f3554af1980a68861705f6bc8e6`: `.release-sha=cefea6e6f9f37f3554af1980a68861705f6bc8e6`, `.release-run-id=26502776229`.
- `tj-mmj8`, `tj-4cm4`, `tj-8ma2`, and `tj-4xnf` are merged, deployed, live-E2E verified/triaged, cleaned, and closed in Beads.
- `tj-4xnf` fixed the remaining Zoho Inventory customer-resolution failure after prior duplicate-name fallback commit `e97bbb4`: synthetic phone suffixes no longer leak into Inventory lookup/create.
- Local `tj-4xnf` fix strips repo-owned `#...` suffixes only at the Zoho Inventory contact boundary, while preserving suffixed phones inside app conversation storage.
- Local verification passed: RED/GREEN synthetic suffix regression, `tests/test_llm_quotation.py` plus Inventory tests (`20 passed`), relevant engine quote tests (`46 passed`), ruff, format check, mypy, and full stage closeout (`1181 passed, 19 skipped`).
- `tj-nzob` is merged, pushed, deployed, production-smoked, locally cleaned, and closed in Beads: comma-separated ordered brief parsing now preserves `company=LLD`; GitHub Actions run `26502776229` passed `changes`, `lint`, `test`, `type-check`, and `deploy`; production smoke passed `8 passed, 0 failed`; live WhatsApp E2E was not run.
- `tj-4xnf` production E2E conversation `4c2156c6-1763-435e-aa3d-7965631a96f3` created quotation `Fr3316` / sale order `378603000022228007`; synthetic conversations were closed after evidence.
- Stage evidence: `.codex/stages/tj-4xnf/summary.md`, `.codex/stages/tj-4xnf/artifacts/tj-4xnf-local-implementation.md`, and `.codex/stages/tj-4xnf/artifacts/tj-4xnf-production-e2e.md`.
- Current `tj-nzob` evidence: `.codex/stages/tj-nzob/summary.md` and `.codex/stages/tj-nzob/artifacts/tj-nzob-local-implementation.md`.

## Next recommended
Next stage id: none selected.
Recommended action: optionally run a controlled live WhatsApp E2E for `tj-nzob` if real-model production evidence is desired; otherwise continue with the next open Beads priority.

## Starter prompt for next orchestrator
Use $orchestrator-stage. Continue from clean `main` after delivered runtime commit `cefea6e6f9f37f3554af1980a68861705f6bc8e6` and GitHub Actions deploy run `26502776229`. `tj-nzob` is merged, deployed, production-smoked, and the local feature branch was deleted. Do not run live WhatsApp E2E unless explicitly authorized for the current turn.

## Explicit defers
- `tj-nzob`: live WhatsApp E2E was not run; local/parser tests and production API smoke passed after deploy.
- `tj-final27.6`: referral launch remains blocked pending written client referral policy or explicit exclusion.
- Dialogue kernel `enforce` rollout remains deferred; production is intentionally `shadow` only.
