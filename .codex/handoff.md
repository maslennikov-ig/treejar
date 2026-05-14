# Orchestrator Handoff

Updated: 2026-05-14
Current branch: `main`

## Current Truth

- Canonical host: `https://noor.starec.ai`; canonical runtime path: `/opt/noor`.
- Stage `tj-gh14` implements GitHub issues #34-#37 from `liliya12m`; delivery stage `tj-gh14-delivery` pushed `origin/codex/tj-gh14-new-issues`, fast-forwarded `main`, and pushed `origin/main` through hotfix release `7075be5831dd0e09e29a319d842003f24c6dcf0f`.
- GitHub Actions runs `25863943847`, `25871636762`, and `25872745415` succeeded; final deploy reports active release `7075be5831dd0e09e29a319d842003f24c6dcf0f` on `/opt/noor`.
- Safe post-deploy E2E passed: `scripts/verify_api.py --base-url https://noor.starec.ai` returned `7 passed, 0 failed`; final hotfix local full pytest returned `1019 passed, 19 skipped`.
- Live WhatsApp E2E was explicitly approved for `+79262810921` and passed. Quote suffix `79262810921#tj-gh14-live-quote-20260514165102` returned `name-gate` then `z-ai/glm-5|exact-quote-missing-details` with escalation `none` and pending `CH-190` quantity `5`. Product suffix `79262810921#tj-gh14-live-product-20260514165102` returned product options for `I need 5 office chairs.`, escalation `none`, and product media captions stayed audit-only (`customer_visible=false`, no provider caption message id).
- No GitHub issue mutation, production config mutation, or `scripts/verify_wazzup.py` run has been performed for `tj-gh14`.
- Plan: `docs/plans/2026-05-14-liliya-gh34-37-stabilization.md`; stage summary: `.codex/stages/tj-gh14/summary.md`.
- Local Beads: `tj-gh14` epic plus `tj-gh14.1` (#34 bare quantity+SKU exact_quote), `tj-gh14.2` (#37 product+quantity no order_confirmation), `tj-gh14.3` (#36 name-gate pending request resume), and `tj-gh14.4` (#35 product media caption suppression).
- Implemented: bare `qty x SKU` / `SKU x qty` exact-quote parsing; SKU product signal in order handoff; `order_confirmation` tool veto for product/SKU+quantity without fulfillment evidence; bounded `name_gate_pending_request` store/consume; no generic name-capture opener when a prior request exists; deferred product media sends no customer-visible caption while retaining internal caption audit metadata.
- Delegation: worker `Newton` implemented #35 and was reviewed; explorer `Kierkegaard` analyzed #36 read-only and findings were independently verified before implementation.
- Verification: targeted post-format suite `29 passed`; full worker scope `25 passed`; wide modified LLM/escalation suite `158 passed`; full `ruff check`, full `ruff format --check`, `mypy`, full pytest `1016 passed, 19 skipped`, process verification, and stage closeout passed.
- Local Beads `tj-gh14`, `tj-gh14.1`, `tj-gh14.2`, `tj-gh14.3`, `tj-gh14.4`, `tj-gh14-delivery.1`, `tj-gh14-delivery.2`, `tj-gh14-delivery.3`, and `tj-gh14-delivery.4` are closed.
- Orchestration baseline is `balanced-v2.7`; use repo-local commands in `.codex/orchestrator.toml`.
- Production state is `7075be5831dd0e09e29a319d842003f24c6dcf0f`.

## Next recommended

Next stage id: none.
Recommended action: no further code delivery is pending. Ask before GitHub issue mutation, production config changes, or additional live WhatsApp/media/voice tests.

## Starter prompt for next orchestrator

Use $orchestrator-stage only if the user asks for GitHub issue comments/closures, another live E2E cycle, or another issue batch. Current delivered main is `7075be5831dd0e09e29a319d842003f24c6dcf0f`.

## Explicit defers

- `tj-b4n` / GitHub #24 remains provider-blocked pending an official Wazzup typing endpoint.
- No GitHub issue mutation, production config mutation, broad production suite, or `scripts/verify_wazzup.py` run has been performed.
