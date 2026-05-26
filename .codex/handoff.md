# Orchestrator Handoff
Updated: 2026-05-26
Current branch: `main`

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

## Next recommended
Next stage id: `tj-8ma2`.
Recommended action: continue with the separate sales-order quote-resume bug from the Fr3309 production E2E, or choose `tj-nzob` if comma-separated company parsing is higher priority.

## Starter prompt for next orchestrator
Use $orchestrator-stage. Continue from `main`; `tj-4cm4` is merged, pushed, deployed, live-E2E verified, and closed in Beads. Next unresolved follow-ups from the Fr3309 production E2E are `tj-8ma2` and `tj-nzob`.

## Explicit defers
- `tj-8ma2`: sales-order quote resume can reinterpret customer brief as unresolved item; handle separately.
- `tj-nzob`: comma-separated ordered brief stores name/email/address but misses company; handle separately.
- `tj-mmj8`: Fr3309 is deployed and verified; Beads closure was previously left pending explicit owner approval.
- `tj-final27.6`: referral launch remains blocked pending written client referral policy or explicit exclusion.
- Dialogue kernel `enforce` rollout remains deferred; production is intentionally `shadow` only.
