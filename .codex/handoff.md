# Orchestrator Handoff

Updated: 2026-05-14
Current branch: `codex/tj-gh14-new-issues`

## Current Truth

- Canonical host: `https://noor.starec.ai`; canonical runtime path: `/opt/noor`.
- Stage `tj-gh14` implements GitHub issues #34-#37 from `liliya12m` on branch `codex/tj-gh14-new-issues`; no GitHub issue mutation, deploy, production config mutation, or live WhatsApp/media/voice test has been done for this stage.
- Delivery stage `tj-gh14-delivery` is in progress for current-task approved push/merge plus safe post-merge E2E; manual deploy, production config mutation, GitHub issue mutation, and live WhatsApp/media/voice tests remain approval-gated.
- Plan: `docs/plans/2026-05-14-liliya-gh34-37-stabilization.md`; stage summary: `.codex/stages/tj-gh14/summary.md`.
- Local Beads: `tj-gh14` epic plus `tj-gh14.1` (#34 bare quantity+SKU exact_quote), `tj-gh14.2` (#37 product+quantity no order_confirmation), `tj-gh14.3` (#36 name-gate pending request resume), and `tj-gh14.4` (#35 product media caption suppression).
- Implemented: bare `qty x SKU` / `SKU x qty` exact-quote parsing; SKU product signal in order handoff; `order_confirmation` tool veto for product/SKU+quantity without fulfillment evidence; bounded `name_gate_pending_request` store/consume; no generic name-capture opener when a prior request exists; deferred product media sends no customer-visible caption while retaining internal caption audit metadata.
- Delegation: worker `Newton` implemented #35 and was reviewed; explorer `Kierkegaard` analyzed #36 read-only and findings were independently verified before implementation.
- Verification: targeted post-format suite `29 passed`; full worker scope `25 passed`; wide modified LLM/escalation suite `158 passed`; full `ruff check`, full `ruff format --check`, `mypy`, full pytest `1016 passed, 19 skipped`, process verification, and stage closeout passed.
- Local Beads `tj-gh14`, `tj-gh14.1`, `tj-gh14.2`, `tj-gh14.3`, and `tj-gh14.4` are closed.
- Orchestration baseline is `balanced-v2.7`; use repo-local commands in `.codex/orchestrator.toml`.
- Previous production state remains `df3f3b10f4ee0ab4ee36aa523d4e9cfa4beb2456` from `tj-gh12` hotfixes; do not assume `tj-gh14` is deployed.

## Next recommended

Next stage id: `tj-gh14`.
Recommended action: continue `tj-gh14-delivery`: push feature branch, merge/push `main`, then run safe post-merge E2E. Ask before manual deploy, production config changes, GitHub issue mutation, or live WhatsApp/media/voice tests.

## Starter prompt for next orchestrator

Use $orchestrator-stage. Continue `tj-gh14` on `codex/tj-gh14-new-issues`; implementation is verified and Beads are closed, so prepare delivery only after explicit approval.

## Explicit defers

- `tj-b4n` / GitHub #24 remains provider-blocked pending an official Wazzup typing endpoint.
- No `tj-gh14` deploy, GitHub issue mutation, production config mutation, live WhatsApp/media/voice test, broad production suite, or `scripts/verify_wazzup.py` run has been performed.
