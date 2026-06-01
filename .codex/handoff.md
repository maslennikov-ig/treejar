# Orchestrator Handoff
Updated: 2026-06-01
Current branch: `codex/tj-gh47-preference-context`

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
- Active local stage `tj-gh47` fixes GitHub #47 preference-answer over-escalation on branch `codex/tj-gh47-preference-context`; local implementation and tests passed, but it is not merged, pushed, deployed, production-E2E verified, or closed in GitHub yet.

## Next recommended
Next stage id: `tj-gh47`.
Recommended action: deliver `tj-gh47` after review: commit, push/merge, deploy, production smoke/E2E for GitHub #47, then comment and close #47 only with release evidence.

## Starter prompt for next orchestrator
Use $orchestrator-stage. Continue `tj-gh47` from branch `codex/tj-gh47-preference-context`. The local fix for GitHub #47 is implemented and verified locally; do not close GitHub #47 until merge/deploy/production evidence exists. `tj-nzob` remains the latest deployed runtime from commit `cefea6e6f9f37f3554af1980a68861705f6bc8e6` and GitHub Actions run `26502776229`.

## Explicit defers
- `tj-nzob`: live WhatsApp E2E was not run; local/parser tests and production API smoke passed after deploy.
- `tj-final27.6`: referral launch remains blocked pending written client referral policy or explicit exclusion.
- Dialogue kernel `enforce` rollout remains deferred; production is intentionally `shadow` only.
- `tj-gh47`: delivery and live production evidence are pending; GitHub #47 remains open.
