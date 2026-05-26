# Orchestrator Handoff
Updated: 2026-05-26
Current branch: `codex/tj-8ma2-sales-order-brief-resume`

## Current Truth
- Canonical host: `https://noor.starec.ai`; runtime path: `/opt/noor`.
- Main branch: docs-only live-E2E evidence is committed on top of
  `a2fa23b1b43164b619c1192813180d9ec69f40bd`; production runtime remains the
  code delivery commit below.
- Production runtime is `77f96f3a483b201a70c969177b8203585f6b5682` from GitHub Actions run `26460815449`; deploy job passed.
- `tj-4cm4` fixes exact quote clarification resume for pending `5 x CH 620` when the customer replies `The exact SKU is CH 620 grey, quantity 5.`
- The fix resolves the clarified SKU, preserves quantity 5, avoids storing `quantity 5` as address, and resumes quote creation/detail gating instead of asking for item(s)/quantity again.
- Local verification passed: targeted RED/GREEN, related exact quote/sales-order tests, `tests/test_llm_engine.py` (`219 passed`), ruff check, ruff format check, mypy.
- Full Python suite excluding frontend dashboard regressions passed: `1168 passed, 19 skipped`.
- After temporary `npm ci --prefix frontend/admin`, full stage closeout passed with full pytest `1179 passed, 19 skipped`; local Node emitted an expected engine warning because v24.15.0 is outside `>=22.12.0 <23`.
- Process verification and stage closeout passed; GitHub Actions run `26460815449` passed, runtime readback matched `77f96f3`, and production smoke passed `8/0`.
- Fast-forward merge/push/deploy completed; local feature branch was deleted.
- Approved live WhatsApp E2E passed on suffix `+79262810921#tj-4cm4-live-20260526-193430`: the original CH 620 clarification flow created `Quotation Fr3314`, readback preserved `Dubai test street 2` as address, and the synthetic conversation was closed.
- Beads `tj-4cm4` is closed.
- Stage evidence: `.codex/stages/tj-4cm4/summary.md`, `.codex/stages/tj-4cm4/artifacts/tj-4cm4-local-implementation.md`, and `.codex/stages/tj-4cm4/artifacts/tj-4cm4-production-e2e.md`.
- `tj-8ma2` local TDD fix is ready on branch `codex/tj-8ma2-sales-order-brief-resume`: resolved sales-order quote follow-up now stores the resolved item selection before asking for customer details, so the following brief details can create the quotation instead of becoming an unresolved item.
- `tj-8ma2` local verification passed: RED/GREEN regression, related quote-resume tests (`7 passed`), full `tests/test_llm_engine.py` (`220 passed`), ruff check, ruff format check, mypy, process verification, and broad Python suite excluding frontend dashboard (`1169 passed, 19 skipped`).
- `tj-8ma2` is not merged, pushed, deployed, or live-E2E tested.

## Next recommended
Next stage id: `tj-8ma2`.
Recommended action: decide whether to merge/push/deploy `tj-8ma2` and then run a bounded live E2E retest, or keep it local and move to `tj-nzob`.

## Starter prompt for next orchestrator
Use $orchestrator-stage. Continue from branch `codex/tj-8ma2-sales-order-brief-resume`; local fix for `tj-8ma2` is implemented and verified locally but not merged/pushed/deployed/live-tested. If delivery is approved, merge to main, push, wait for CI/deploy, smoke production, then run a bounded live E2E retest of the sales-order resume plus multiline brief path.

## Explicit defers
- `tj-8ma2`: merge/push/deploy/live E2E pending explicit owner approval.
- `tj-nzob`: comma-separated ordered brief stores name/email/address but misses company; handle separately.
- `tj-mmj8`: Fr3309 is deployed and verified; Beads closure was previously left pending explicit owner approval.
- `tj-final27.6`: referral launch remains blocked pending written client referral policy or explicit exclusion.
- Dialogue kernel `enforce` rollout remains deferred; production is intentionally `shadow` only.
