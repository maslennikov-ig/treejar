# Orchestrator Handoff

Updated: 2026-05-21
Current branch: `codex/tj-gh22-fu1-service-window`

## Current Truth

- Canonical host: `https://noor.starec.ai`; canonical runtime path: `/opt/noor`.
- Production release includes runtime commit `3f0ed132a12f90c6d2087f40697f0fcdc0c2b3a6`; GitHub Actions run `26233690578` succeeded, including deploy; production smoke `scripts/verify_api.py --base-url https://noor.starec.ai` passed `7 passed, 0 failed`.
- Direct `/opt/noor/.release-sha` SSH verification was unavailable locally because SSH public-key authentication failed; delivery evidence is GitHub Actions deploy plus production API smoke.
- Stages `tj-gh18` and `tj-gh19` are delivered, deployed, live E2E verified, Beads closed, and GitHub #39/#35/#40 are closed.
- Stage `tj-gh20` is delivered in production `shadow` mode only: `dialogue_kernel_mode=shadow`, `dialogue_kernel_trace_enabled=true`, `dialogue_kernel_enforced_flows=""`; keep `enforce` deferred.
- Stage `tj-gh21` is delivered for GitHub #11 post-quotation follow-up after Lilia's answers; local and production delivery evidence is in `.codex/stages/tj-gh21/`, and GitHub #11 remains open pending live follow-up E2E.
- Stage `tj-gh22` is delivered to production: FU1 is scheduled at 23h and can use free-form text only when the real 24h WhatsApp window is still open; FU2/FU3 still require Wazzup WABA templates.
- `tj-gh22.1` controlled E2E artifact is tracked at `.codex/stages/tj-gh22/artifacts/tj-gh22.1-e2e-execution.md`; S0 production smoke passed, live sends used approved `+79262810921` and channel `b49b1b9d-757f-4104-b56d-8f43d62cc515`.
- `tj-gh22.1` blocker: product/SKU name-gate path worked, but exact quote conversations `baa857a8-cc87-4d4f-85c3-aa5a746fcbc1`, `d6fa2284-0029-4019-b304-285e9d352e6f`, and `c11ac597-9452-4e79-8dd9-50261dbcd768` ended in `exact-quote-fallback` with pending escalation before quotation creation.
- Stage `tj-gh23` is locally implemented and stage closeout passed: deterministic exact quote frame persistence through name gate, natural delivered-to address extraction, CH 616 suffix-SKU resolver hardening, and fail-open clarification for parser/resolver uncertainty.
- Orchestration baseline is `balanced-v2.7`; use repo-local commands in `.codex/orchestrator.toml`.

## Next recommended

Next stage id: `tj-gh23.5`, then resume `tj-gh22.1` controlled production E2E after quote creation is proven live.

Recommended action: get explicit authorization for merge/deploy/live E2E, clean or resolve the three synthetic pending exact-quote escalations, prove quotation creation on approved `+79262810921`, then continue post-quotation follow-up E2E. Do not close GitHub #11 yet.

## Starter prompt for next orchestrator

Use $orchestrator-stage to continue `tj-gh23.5` delivery/E2E. Current delivered production release includes runtime commit `3f0ed132a12f90c6d2087f40697f0fcdc0c2b3a6`; `tj-gh20` remains in `shadow` mode only. Local `tj-gh23` closeout passed in worktree `/home/me/code/treejar/.worktrees/codex-tj-gh14-main-merge`, but merge/deploy/live E2E were not authorized. After deployment, prove exact quotation creation on approved `+79262810921`, then resume `tj-gh22.1` post-quotation E2E.

## Explicit defers

- `tj-b4n` / GitHub #24 remains provider-blocked pending an official Wazzup typing endpoint.
- Full production follow-up E2E for GitHub #11 remains blocked by `tj-gh23.5` delivery/live quote-creation proof, then by explicit FU1 EN/AR free-form text configuration and approved Wazzup WABA FU2/FU3 template ids/codes for English and Arabic.
- Dialogue kernel `enforce` rollout remains deferred; production is intentionally `shadow` only.
