# Orchestrator Handoff
Updated: 2026-05-26
Current branch: `main`

## Current Truth
- Canonical host: `https://noor.starec.ai`; runtime path: `/opt/noor`.
- Local `main` matches `origin/main` at `80e6f4371da44f163406f76f30f858e94d35da4a`.
- Production runtime matches: `.release-sha=80e6f4371da44f163406f76f30f858e94d35da4a`, `.release-run-id=26462939020`.
- GitHub Actions run `26462939020` succeeded including deploy; smoke passed: `/api/v1/health` healthy and `verify_api.py --base-url https://noor.starec.ai` -> `8 passed, 0 failed`.
- `tj-mmj8`, `tj-4cm4`, and `tj-8ma2` are merged, deployed, live-E2E verified/triaged, cleaned, and closed in Beads.
- `tj-8ma2` target live evidence: conversation `bdee58ee-8b56-414e-96bc-55de1b659a77` preserved `CH 620 grey x5` in `pending_quote_selection` and stored `Lilia / LLD / Lfdsf@kfsl.ru / 2 street` as quote details without turning the brief into an unresolved item.
- Four synthetic `tj-8ma2` conversations and two pending synthetic escalations were closed/resolved; merged local branches `codex/tj-8ma2-sales-order-brief-resume` and `codex/tj-final27-artifact-normalization` were deleted.
- Stage evidence: `.codex/stages/tj-mmj8/summary.md`, `.codex/stages/tj-4cm4/summary.md`, `.codex/stages/tj-8ma2/summary.md`.

## Next recommended
Next stage id: `tj-4xnf` or `tj-nzob`.
Recommended action: fix `tj-4xnf` first if full quote creation after sales-order resume is more urgent; pick `tj-nzob` first if comma-separated brief parsing is more urgent.

## Starter prompt for next orchestrator
Use $orchestrator-stage. Start from clean `main` at `80e6f4371da44f163406f76f30f858e94d35da4a`. For `tj-4xnf`, investigate why `resolve_inventory_customer_id` did not recover from Zoho Inventory `create_contact` HTTP 400 in live conversation `bdee58ee-8b56-414e-96bc-55de1b659a77` after `create_quotation` was called with `CH 620 grey x5`. Preserve exact quote fail-closed safety, add TDD coverage, run local gates, and do not deploy or send live WhatsApp without explicit owner approval.

## Explicit defers
- `tj-4xnf`: exact quotation can still fail closed when Zoho Inventory `create_contact` returns HTTP 400 and fallback does not recover.
- `tj-nzob`: comma-separated ordered brief stores name/email/address but misses company; slash and multiline formats are already covered.
- `tj-final27.6`: referral launch remains blocked pending written client referral policy or explicit exclusion.
- Dialogue kernel `enforce` rollout remains deferred; production is intentionally `shadow` only.
