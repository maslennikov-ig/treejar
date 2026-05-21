# Orchestrator Handoff

Updated: 2026-05-21
Current branch: `codex/tj-gh21-post-quotation-followup`

## Current Truth

- Canonical host: `https://noor.starec.ai`; canonical runtime path: `/opt/noor`.
- Production release is `9e967d5acd862e98c74b472c1d6fa102e686bf3f`; GitHub Actions run `26098722338` succeeded; `/opt/noor/.release-sha` matches.
- Stage `tj-gh18` is delivered, deployed, live E2E verified, and GitHub #39/#35 are closed.
- Stage `tj-gh19` is delivered, deployed, live E2E verified, Beads closed, and GitHub #40 is closed.
- Stage `tj-gh20` is delivered to production in `shadow` mode. Production `SystemConfig`: `dialogue_kernel_mode=shadow`, `dialogue_kernel_trace_enabled=true`, `dialogue_kernel_enforced_flows=""`.
- `tj-gh20` decision report: keep `shadow`, do not enable `enforce` yet; artifacts live under `.codex/stages/tj-gh20/`.
- Stage `tj-gh21` is in progress locally on `codex/tj-gh21-post-quotation-followup` for GitHub #11 post-quotation follow-up after Lilia's answers.
- `tj-gh21` local behavior: customer-facing output remains English/Arabic only; after КП Noor asks if the quotation works; explicit acceptance hands off to manager; customer questions before acceptance remain bot-handled; follow-up cadence is 24h/3d/7d using Wazzup template transport outside 24h.
- `tj-gh21` review-and-fix pass completed: generic `yes/ok/fine/works` approval is gated by the previous explicit quotation approval prompt; stale quotation decision metadata resets on new КП; acceptance runs before dialogue-kernel enforce; FU3 waits 24h before no-response rejection; explicit rejection persists rejected metadata; Arabic locale variants stay Arabic.
- `tj-gh21` verification passed after review fixes and after adding the Wazzup WABA guide: targeted 246 tests, full pytest `1114 passed, 19 skipped`, ruff, format-check, mypy, git diff check, and process verification.
- `tj-gh21` client WABA setup guide added at `docs/client/wazzup-waba-followup-setup-guide.md`; delivery is authorized and in progress.
- `tj-gh21` is not deployed yet; production behavior is unchanged from the `tj-gh20` release until the GitHub Actions deployment succeeds.
- Orchestration baseline is `balanced-v2.7`; use repo-local commands in `.codex/orchestrator.toml`.

## Next recommended

Next stage id: continue `tj-gh21` until merge/deploy decision.

Recommended action: complete merge/deploy for `tj-gh21`, run production smoke verification, then keep production follow-up sending disabled until Wazzup EN/AR approved template ids/codes are configured.

## Starter prompt for next orchestrator

Use $orchestrator-stage to continue `tj-gh21`. Current delivered production release is still `9e967d5acd862e98c74b472c1d6fa102e686bf3f`; `tj-gh20` is deployed in `shadow` mode only. Local `tj-gh21` review fixes and Wazzup WABA client guide are verified; merge/deploy is in progress. See `.codex/stages/tj-gh21/summary.md` and artifacts `tj-gh21-local-implementation.md`, `tj-gh21-review-fixes.md`.

## Explicit defers

- `tj-b4n` / GitHub #24 remains provider-blocked pending an official Wazzup typing endpoint.
- Production follow-up sending for GitHub #11 remains blocked pending approved Wazzup WABA template ids/codes for English and Arabic.
- Dialogue kernel `enforce` rollout remains deferred; production is intentionally `shadow` only.
