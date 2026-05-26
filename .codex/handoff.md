# Orchestrator Handoff
Updated: 2026-05-26
Current branch: `codex/tj-4cm4-exact-sku-resume`

## Current Truth
- Canonical host: `https://noor.starec.ai`; runtime path: `/opt/noor`.
- Main branch: `main@57e4bd303494c5d822dcdfc4b8381a62cbf0ead8`, pushed on 2026-05-26.
- Production runtime remains `40ee6928adfa60f3f3297cf6e52af63c6960fdd8` from `tj-final27.17`; smoke passed after manual deploy.
- Current local stage `tj-4cm4` fixes exact quote clarification resume for pending `5 x CH 620` when the customer replies `The exact SKU is CH 620 grey, quantity 5.`
- The fix resolves the clarified SKU, preserves quantity 5, avoids storing `quantity 5` as address, and resumes quote creation/detail gating instead of asking for item(s)/quantity again.
- Local verification passed: targeted RED/GREEN, related exact quote/sales-order tests, `tests/test_llm_engine.py` (`219 passed`), ruff check, ruff format check, mypy.
- Full Python suite excluding frontend dashboard regressions passed: `1168 passed, 19 skipped`.
- Full `pytest tests/ -q` is blocked only by absent `frontend/admin/node_modules` / missing Node package `esbuild`; node deps were not installed to avoid disk growth during cleanup work.
- Process verification passed; stage closeout is blocked until merge/delivery approval because accepted streams require delivery mini-closeout.
- No merge, push, deploy, live WhatsApp E2E, or Beads closure was performed for `tj-4cm4`.
- Stage evidence: `.codex/stages/tj-4cm4/summary.md` and `.codex/stages/tj-4cm4/artifacts/tj-4cm4-local-implementation.md`.

## Next recommended
Next stage id: `tj-4cm4`.
Recommended action: request explicit approval for merge/push/deploy and a bounded live E2E retest of the original CH 620 grey clarification scenario.

## Starter prompt for next orchestrator
Use $orchestrator-stage. Continue from branch `codex/tj-4cm4-exact-sku-resume`; local exact SKU clarification fix is implemented and verified, but not merged, pushed, deployed, or live-tested.

## Explicit defers
- `tj-4cm4`: merge/push/deploy/live WhatsApp E2E require explicit approval.
- `tj-8ma2`: sales-order quote resume can reinterpret customer brief as unresolved item; handle separately.
- `tj-nzob`: comma-separated ordered brief stores name/email/address but misses company; handle separately.
- `tj-mmj8`: Fr3309 is deployed and verified; Beads closure was previously left pending explicit owner approval.
- `tj-final27.6`: referral launch remains blocked pending written client referral policy or explicit exclusion.
- Dialogue kernel `enforce` rollout remains deferred; production is intentionally `shadow` only.
