# Orchestrator Handoff

Updated: 2026-05-14
Current baseline branch: `main`

## Current truth

- Canonical host: `https://noor.starec.ai`; canonical runtime path: `/opt/noor`.
- Stage `tj-gh14` is planned on branch `codex/tj-gh14-new-issues` for GitHub issues #34-#37 from `liliya12m`; no implementation, GitHub mutation, deploy, production config mutation, or live WhatsApp test has been done for this stage.
- Plan: `docs/plans/2026-05-14-liliya-gh34-37-stabilization.md`; stage summary: `.codex/stages/tj-gh14/summary.md`.
- Local Beads created: `tj-gh14` epic, plus `tj-gh14.1` (#34 bare quantity+SKU exact_quote), `tj-gh14.2` (#37 product+quantity no order_confirmation), `tj-gh14.3` (#36 name-gate pending request resume), and `tj-gh14.4` (#35 product media caption suppression).
- Stage `tj-gh12` is closed. After explicit approval, GitHub issues #21, #22, and #24-#33 were commented and closed; already closed #23 received a duplicate/context comment for #26.
- Main delivery `cc3fcf5a5f3e3dd13249aaf7091a1b0d975a180a`, first hotfix `91e61fca5390f857b5902f8476b5ee54a87dbf24`, second hotfix `0a283a42a94b10e77456f641ee0b87a789f13efd`, and third hotfix `df3f3b10f4ee0ab4ee36aa523d4e9cfa4beb2456` were deployed. Final approved text-only production E2E passed on `df3f3b1`.
- Orchestration baseline is reconciled to `balanced-v2.7` via `orchestration-setup`; repo verification commands and delivery policy remain in `.codex/orchestrator.toml`.
- Runtime changes cover Noor identity/name gate, SKU homoglyph/spaced-code parsing with price-phrase false-positive guards, pending sales-order quote resume, price-filtered product search, showroom Maps response, quotation required-data gating, compact quotation PDF, typing provider surface, and disabled-by-default proposal follow-up state/executor/read-status handling.
- Code review reports for `tj-gh12` are tracked under `docs/reports/code-reviews/2026-05/`; review follow-up Beads `tj-gh12.7` through `tj-gh12.14` were created and closed.
- Local Beads `tj-gh12` and `tj-b4n` are closed. `tj-b4n` / GitHub #24 was closed as provider-blocked/not-planned because public Wazzup sending docs do not expose a supported typing endpoint; no fake typing endpoint is called.
- Controlled live WhatsApp E2E was approved for `+79262810921` and started under `tj-gh12.15`. The original scenario A blocker was fixed by `tj-gh12.16`; production recheck on `91e61fc` passed with `name-gate`, escalation `none`, and no product media.
- Scenario B then found `tj-gh12.18`: a name-only reply after the name gate left `customer_name` empty and escalated to manager confirmation. The synthetic pending B conversation was resolved through the application-level `faq_private` manager-reply handler.
- Hotfix `tj-gh12.16` blocks first-turn unknown-name product/quotation/escalation/media side effects. Hotfix `tj-gh12.17` prevents private manager reply adaptation from adding unsupported price/stock/immediate-delivery claims absent from the manager draft. Hotfix `tj-gh12.18` captures natural-language name replies and short-circuits name-only replies without manager escalation.
- Hotfix `tj-gh12.19` normalizes leading quantity multiplier markers in `1 x CH-620`, so the existing missing-data quotation gate asks for company/specific delivery address instead of falling through to manager escalation.
- Synthetic conversation `d82cb1ca-4cde-4042-9f18-4c3129901f93` and escalation `e1c22bde-754d-4ef2-95dc-e4dc73aca8dc` from second post-deploy E2E were cleaned through the repo application service; readback showed both resolved.
- No production config mutation, template enablement, `scripts/verify_wazzup.py`, broad production suite, or voice/audio test was performed.

## Next recommended

Next stage id: `tj-gh14`.
Recommended action: implement `tj-gh14` from the saved plan if the user approves execution. Keep central `src/llm/engine.py` changes sequential; product-media caption work can be delegated only after the payload/audit shape is decided.

## Starter prompt for next orchestrator

Use $orchestrator-stage if implementing `tj-gh14`.
Focus: execute `docs/plans/2026-05-14-liliya-gh34-37-stabilization.md`. Review `src/llm/engine.py` exact quote parsing, `escalate_to_manager`, `name-gate`/`name-capture`, `src/llm/order_handoff.py`, `src/llm/prompts.py`, `src/services/chat.py`, `src/services/outbound_audit.py`, `src/integrations/messaging/wazzup.py`, and product media selection tests.
Documentation: Context7 checked `/pydantic/pydantic-ai` for agent tool behavior; local Wazzup code documents caption-as-second-text behavior.
Asset Routing: Skills used for planning: `orchestrator-stage`, `process-issues`, `writing-plans`. Agents/personas: none launched. Catalog candidates: none.
Boundaries: no GitHub issue comments/closures, deploys, production config mutations, live WhatsApp/media/voice tests, `scripts/verify_wazzup.py`, broad production suites, or template sends without separate approval for `tj-gh14`.

## Explicit defers

- `tj-b4n` / GitHub #24 remains provider-blocked pending an official Wazzup typing endpoint; proposal follow-up sends remain disabled until approved templates/config and confirmed Wazzup template transport schema are provided.
