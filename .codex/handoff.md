# Orchestrator Handoff

Updated: 2026-05-13
Current baseline branch: `main`

## Current truth

- Canonical host: `https://noor.starec.ai`; canonical runtime path: `/opt/noor`.
- Stage `tj-gh12` is the local Beads stage for GitHub issues #21, #22, #24-#33; GitHub issues were not commented on or closed.
- Main delivery `cc3fcf5a5f3e3dd13249aaf7091a1b0d975a180a` was deployed. Post-deploy E2E found a first-turn name-gate side-effect blocker; hotfix work is on `codex/tj-gh12-name-gate-hotfix-clean` from `main@cc3fcf5a5f3e3dd13249aaf7091a1b0d975a180a`.
- Orchestration baseline is reconciled to `balanced-v2.7` via `orchestration-setup`; repo verification commands and delivery policy remain in `.codex/orchestrator.toml`.
- Runtime changes cover Noor identity/name gate, SKU homoglyph/spaced-code parsing with price-phrase false-positive guards, pending sales-order quote resume, price-filtered product search, showroom Maps response, quotation required-data gating, compact quotation PDF, typing provider surface, and disabled-by-default proposal follow-up state/executor/read-status handling.
- Code review reports for `tj-gh12` are tracked at `docs/reports/code-reviews/2026-05/CR-2026-05-12-tj-gh12-review.md` and `docs/reports/code-reviews/2026-05/CR-2026-05-13-tj-gh12-follow-up-review.md`; review follow-up Beads `tj-gh12.7` through `tj-gh12.14` were created and closed.
- Stage closeout now enforces required tracked artifacts when the repo contract says `artifact_required_for_stage_close = true`.
- Local Beads remains the task source of truth. `tj-b4n` / GitHub #24 is blocked at provider level because public Wazzup sending docs do not expose a supported typing endpoint; no fake typing endpoint is called.
- Controlled live WhatsApp E2E was approved for `+79262810921` and started under `tj-gh12.15`. Scenario A failed because product media/escalation side effects occurred before customer name capture; the synthetic pending conversation was resolved through the normal manager path and final `tj-gh12-e2e` pending count was `0`.
- Hotfix `tj-gh12.16` blocks first-turn unknown-name product/quotation/escalation/media side effects. Hotfix `tj-gh12.17` prevents private manager reply adaptation from adding unsupported price/stock/immediate-delivery claims absent from the manager draft.
- No GitHub issue mutation, production config mutation, template enablement, `scripts/verify_wazzup.py`, broad production suite, or voice/audio test was performed.

## Next recommended

Next stage id: `tj-gh12`.
Recommended action: deploy the hotfix branch, rerun live E2E scenario A, then continue the scoped B-H checks only if A passes. If typing indicators are still required, obtain a supported Wazzup typing endpoint or provider confirmation before changing the current no-op provider method. If proposal follow-ups should send messages, provide approved WhatsApp templates/freeform copy, explicit enablement config, and confirmed Wazzup template transport schema before enabling template mode.

## Starter prompt for next orchestrator

Use $orchestrator-stage if continuing `tj-gh12`.
Focus: deploy/recheck `tj-gh12.16` and `tj-gh12.17`, then resume `tj-gh12.15` E2E. Review `src/llm/engine.py` first-turn `name-gate`, `src/llm/response_adapter.py` risky-claim fallback, `src/services/chat.py`, `src/services/proposal_followup.py`, `src/api/v1/webhook.py`, `src/worker.py`, quotation template changes, stage closeout artifact enforcement, and the Wazzup typing provider no-op.
Documentation: PydanticAI tool parameter schema behavior and Wazzup sending-message docs were checked; Wazzup public docs did not show a typing endpoint.
Asset Routing: Skills used: `orchestration-setup`, `orchestrator-stage`, `task-router`, `test-driven-development`, `verification-before-completion`. Agents/personas: built-in Codex subagents on PDF, typing, and proposal-followup streams. Catalog candidates: none.
Boundaries: current user approval covers hotfix deploy and controlled text WhatsApp E2E on `+79262810921`; still no GitHub issue comments/closures, production config mutations, voice/audio tests, `scripts/verify_wazzup.py`, broad production suites, or template sends without separate approval.

## Explicit defers

- `tj-b4n` / GitHub #24 is blocked pending an official supported Wazzup typing endpoint; the local code exposes `send_typing()` and refresh-loop behavior but WazzupProvider intentionally no-ops.
- Proposal follow-up sends remain disabled by default until approved WhatsApp template names/freeform copy and enablement config are provided; scheduling/state/stop/read-status rules and a bounded executor are implemented locally. Template-mode sends additionally require confirmed Wazzup template transport schema via `template_transport_confirmed`.
