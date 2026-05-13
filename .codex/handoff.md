# Orchestrator Handoff

Updated: 2026-05-13
Current baseline branch: `main`

## Current truth

- Canonical host: `https://noor.starec.ai`; canonical runtime path: `/opt/noor`.
- Stage `tj-gh12` is the local Beads stage for GitHub issues #21, #22, #24-#33; GitHub issues were not commented on or closed.
- Work is on branch `codex/tj-gh12-new-issues` from `origin/main@838d3d65887947452b2e77e75c633848a37fa2b9`.
- Orchestration baseline is reconciled to `balanced-v2.7` via `orchestration-setup`; repo verification commands and delivery policy remain in `.codex/orchestrator.toml`.
- Runtime changes cover Noor identity/name gate, SKU homoglyph/spaced-code parsing with price-phrase false-positive guards, pending sales-order quote resume, price-filtered product search, showroom Maps response, quotation required-data gating, compact quotation PDF, typing provider surface, and disabled-by-default proposal follow-up state/executor/read-status handling.
- Code review reports for `tj-gh12` are tracked at `docs/reports/code-reviews/2026-05/CR-2026-05-12-tj-gh12-review.md` and `docs/reports/code-reviews/2026-05/CR-2026-05-13-tj-gh12-follow-up-review.md`; review follow-up Beads `tj-gh12.7` through `tj-gh12.14` were created and closed.
- Stage closeout now enforces required tracked artifacts when the repo contract says `artifact_required_for_stage_close = true`.
- Local Beads remains the task source of truth. `tj-b4n` / GitHub #24 is blocked at provider level because public Wazzup sending docs do not expose a supported typing endpoint; no fake typing endpoint is called.
- No deploy, production config mutation, live WhatsApp/media/voice test, GitHub issue mutation, or template enablement was performed.

## Next recommended

Next stage id: none until review or delivery is requested for `tj-gh12`.
Recommended action: review `codex/tj-gh12-new-issues`, then choose delivery path. If typing indicators are still required, obtain a supported Wazzup typing endpoint or provider confirmation before changing the current no-op provider method. If proposal follow-ups should send messages, provide approved WhatsApp templates/freeform copy, explicit enablement config, and confirmed Wazzup template transport schema before enabling template mode.

## Starter prompt for next orchestrator

Use $orchestrator-stage if continuing `tj-gh12`.
Focus: review the local Beads stage, especially `src/llm/engine.py`, `src/services/chat.py`, `src/services/proposal_followup.py`, `src/api/v1/webhook.py`, `src/worker.py`, quotation template changes, stage closeout artifact enforcement, and the Wazzup typing provider no-op.
Documentation: PydanticAI tool parameter schema behavior and Wazzup sending-message docs were checked; Wazzup public docs did not show a typing endpoint.
Asset Routing: Skills used: `orchestration-setup`, `orchestrator-stage`, `task-router`, `test-driven-development`, `verification-before-completion`. Agents/personas: built-in Codex subagents on PDF, typing, and proposal-followup streams. Catalog candidates: none.
Boundaries: no GitHub issue comments/closures, deploys, production config mutations, live WhatsApp/media/voice tests, or template sends without explicit approval.

## Explicit defers

- `tj-b4n` / GitHub #24 is blocked pending an official supported Wazzup typing endpoint; the local code exposes `send_typing()` and refresh-loop behavior but WazzupProvider intentionally no-ops.
- Proposal follow-up sends remain disabled by default until approved WhatsApp template names/freeform copy and enablement config are provided; scheduling/state/stop/read-status rules and a bounded executor are implemented locally. Template-mode sends additionally require confirmed Wazzup template transport schema via `template_transport_confirmed`.
