# Orchestrator Handoff

Updated: 2026-05-14
Current branch: `main`

## Current Truth

- Canonical host: `https://noor.starec.ai`; canonical runtime path: `/opt/noor`.
- Stage `tj-gh14` implements GitHub issues #34-#37 from `liliya12m`; delivery stage `tj-gh14-delivery` pushed `origin/codex/tj-gh14-new-issues`, fast-forwarded `main`, and pushed `origin/main` to `71cec58b55e10b0393bfab5c9dc0ff2ccac0e3aa`.
- GitHub Actions run `25863943847` succeeded for `changes`, `lint`, `test`, `type-check`, and `deploy`; deploy log reports active release `71cec58b55e10b0393bfab5c9dc0ff2ccac0e3aa` on `/opt/noor`.
- Safe post-deploy E2E passed: `scripts/verify_api.py --base-url https://noor.starec.ai` returned `7 passed, 0 failed`; targeted merged-main regression/E2E returned `6 passed`.
- No GitHub issue mutation, production config mutation, live WhatsApp/media/voice test, or `scripts/verify_wazzup.py` run has been performed for `tj-gh14`.
- Plan: `docs/plans/2026-05-14-liliya-gh34-37-stabilization.md`; stage summary: `.codex/stages/tj-gh14/summary.md`.
- Local Beads: `tj-gh14` epic plus `tj-gh14.1` (#34 bare quantity+SKU exact_quote), `tj-gh14.2` (#37 product+quantity no order_confirmation), `tj-gh14.3` (#36 name-gate pending request resume), and `tj-gh14.4` (#35 product media caption suppression).
- Implemented: bare `qty x SKU` / `SKU x qty` exact-quote parsing; SKU product signal in order handoff; `order_confirmation` tool veto for product/SKU+quantity without fulfillment evidence; bounded `name_gate_pending_request` store/consume; no generic name-capture opener when a prior request exists; deferred product media sends no customer-visible caption while retaining internal caption audit metadata.
- Delegation: worker `Newton` implemented #35 and was reviewed; explorer `Kierkegaard` analyzed #36 read-only and findings were independently verified before implementation.
- Verification: targeted post-format suite `29 passed`; full worker scope `25 passed`; wide modified LLM/escalation suite `158 passed`; full `ruff check`, full `ruff format --check`, `mypy`, full pytest `1016 passed, 19 skipped`, process verification, and stage closeout passed.
- Local Beads `tj-gh14`, `tj-gh14.1`, `tj-gh14.2`, `tj-gh14.3`, `tj-gh14.4`, `tj-gh14-delivery.1`, and `tj-gh14-delivery.2` are closed; `tj-gh14-delivery.3` remains open as the live WhatsApp/media/voice approval gate.
- Orchestration baseline is `balanced-v2.7`; use repo-local commands in `.codex/orchestrator.toml`.
- Production state is `71cec58b55e10b0393bfab5c9dc0ff2ccac0e3aa`.

## Next recommended

Next stage id: `tj-gh14-delivery.3` only if live WhatsApp/media/voice E2E is explicitly approved.
Recommended action: no further code delivery is pending. Ask before GitHub issue mutation, production config changes, or live WhatsApp/media/voice tests.

## Starter prompt for next orchestrator

Use $orchestrator-stage only if the user asks for live E2E, GitHub issue comments/closures, or another issue batch. Current delivered main is `71cec58b55e10b0393bfab5c9dc0ff2ccac0e3aa`.

## Explicit defers

- `tj-b4n` / GitHub #24 remains provider-blocked pending an official Wazzup typing endpoint.
- `tj-gh14-delivery.3`: live WhatsApp/media/voice E2E remains approval-gated.
- No GitHub issue mutation, production config mutation, live WhatsApp/media/voice test, broad production suite, or `scripts/verify_wazzup.py` run has been performed.
