# Orchestrator Handoff

Updated: 2026-05-22
Current branch: `codex/tj-gh22-fu1-service-window`

## Current Truth

- Canonical host: `https://noor.starec.ai`; canonical runtime path: `/opt/noor`.
- Production release includes runtime commit `322bee30d667b245a143813dbd5fccbcf120eecf`; GitHub Actions run `26279825756` succeeded, including deploy; `/opt/noor/.release-sha` and `/opt/noor/.release-run-id` read back `322bee30d667b245a143813dbd5fccbcf120eecf` / `26279825756`; production smoke `scripts/verify_api.py --base-url https://noor.starec.ai` passed `7 passed, 0 failed`.
- Stages `tj-gh18` and `tj-gh19` are delivered, deployed, live E2E verified, Beads closed, and GitHub #39/#35/#40 are closed.
- Stage `tj-gh20` is delivered in production `shadow` mode only: `dialogue_kernel_mode=shadow`, `dialogue_kernel_trace_enabled=true`, `dialogue_kernel_enforced_flows=""`; keep `enforce` deferred.
- Stage `tj-gh21` is delivered for GitHub #11 post-quotation follow-up after Lilia's answers; local and production delivery evidence is in `.codex/stages/tj-gh21/`.
- Stage `tj-gh22` is delivered to production: FU1 is scheduled at 23h and can use free-form text only when the real 24h WhatsApp window is still open; FU2/FU3 still require Wazzup WABA templates.
- `tj-gh22.1` controlled E2E artifact is tracked at `.codex/stages/tj-gh22/artifacts/tj-gh22.1-e2e-execution.md`; S0 production smoke passed, live sends used approved `+79262810921` and channel `b49b1b9d-757f-4104-b56d-8f43d62cc515`.
- `tj-gh22.1` original blocker is resolved by `tj-gh23`: exact quote conversations no longer fall into `exact-quote-fallback` before quotation creation.
- Stage `tj-gh23` is delivered and live E2E verified: deterministic exact quote frame persistence through name gate, natural delivered-to address extraction, CH 616 suffix-SKU resolver hardening, full-text suffix disambiguation, and fail-open clarification for parser/resolver uncertainty.
- Live `tj-gh23` evidence:
  - `cf9f4ade-b261-4f56-b104-69062f861cdd`: word quantity `one Skyland Operative Chair CH 616 NEW black` -> name gate -> `exact-quote-deterministic` -> quotation `Fr3294`; approval -> `post-quotation-accepted`.
  - `e3d30ece-31b5-46a2-a948-dd10096a4bb7`: numeric `1 Skyland Operative Chair CH 616 NEW black` -> name gate -> `exact-quote-deterministic` -> quotation `Fr3295`.
  - `c397b396-b63a-4050-87b6-6b41eab72bea`: ambiguous `1 CH 616 chair` -> narrow exact item/SKU clarification, no escalation.
- Synthetic cleanup completed: old `tj-gh22-*` and new `tj-gh23-*` conversations are closed; pending/in-progress synthetic escalations are zero.
- GitHub #11 and Beads `tj-gh22.1` were closed by explicit owner request on 2026-05-22 after live production evidence. Quote creation is proven live; approval handoff works; ambiguous exact quote requests clarify without escalation. Residuals are documented as future follow-up risk, not closure blockers: FU1/FU2/FU3 template/config matrix was not fully time-tested, and one pre-acceptance delivery question avoided escalation but answered with a generic item/quantity clarification.
- Orchestration baseline is `balanced-v2.7`; use repo-local commands in `.codex/orchestrator.toml`.

## Next recommended

Next stage id: none for GitHub #11.

Recommended action: leave #11 closed. If the business wants stricter follow-up validation later, open a new focused Beads task for FU1/FU2/FU3 Wazzup template/config live testing and for the weak delivery-question answer.

## Starter prompt for next orchestrator

Use $orchestrator-stage for the next production task. Current delivered production release is `322bee30d667b245a143813dbd5fccbcf120eecf`, GitHub Actions run `26279825756`, and production smoke passed. GitHub #11 and `tj-gh22.1` are closed by owner request. `tj-gh23` quote creation is proven live on approved `+79262810921`: `Fr3294` and `Fr3295` were created; ambiguous `CH 616` now clarifies without escalation; synthetic cleanup is complete. If follow-up E2E is reopened, confirm production follow-up config/templates first and review the weak pre-acceptance delivery answer.

## Explicit defers

- `tj-b4n` / GitHub #24 remains provider-blocked pending an official Wazzup typing endpoint.
- Full production follow-up FU1/FU2/FU3 matrix was not fully time-tested before #11 closure; future validation needs explicit FU1 EN/AR free-form text configuration and approved Wazzup WABA FU2/FU3 template ids/codes for English and Arabic.
- Post-quotation pre-acceptance delivery-question answer quality remains a future follow-up candidate.
- Dialogue kernel `enforce` rollout remains deferred; production is intentionally `shadow` only.
