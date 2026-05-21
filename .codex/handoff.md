# Orchestrator Handoff

Updated: 2026-05-21
Current branch: `codex/tj-gh22-fu1-service-window`

## Current Truth

- Canonical host: `https://noor.starec.ai`; canonical runtime path: `/opt/noor`.
- Production release is `9e967d5acd862e98c74b472c1d6fa102e686bf3f`; GitHub Actions run `26098722338` succeeded; `/opt/noor/.release-sha` matches.
- Stage `tj-gh18` is delivered, deployed, live E2E verified, and GitHub #39/#35 are closed.
- Stage `tj-gh19` is delivered, deployed, live E2E verified, Beads closed, and GitHub #40 is closed.
- Stage `tj-gh20` is delivered to production in `shadow` mode. Production `SystemConfig`: `dialogue_kernel_mode=shadow`, `dialogue_kernel_trace_enabled=true`, `dialogue_kernel_enforced_flows=""`.
- `tj-gh20` decision report: keep `shadow`, do not enable `enforce` yet; artifacts live under `.codex/stages/tj-gh20/`.
- Stage `tj-gh21` is delivered to production for GitHub #11 post-quotation follow-up after Lilia's answers.
- `tj-gh21` local behavior: customer-facing output remains English/Arabic only; after КП Noor asks if the quotation works; explicit acceptance hands off to manager; customer questions before acceptance remain bot-handled; follow-up cadence is 24h/3d/7d using Wazzup template transport outside 24h.
- `tj-gh21` review-and-fix pass completed: generic `yes/ok/fine/works` approval is gated by the previous explicit quotation approval prompt; stale quotation decision metadata resets on new КП; acceptance runs before dialogue-kernel enforce; FU3 waits 24h before no-response rejection; explicit rejection persists rejected metadata; Arabic locale variants stay Arabic.
- `tj-gh21` verification passed after review fixes and after adding the Wazzup WABA guide: targeted 246 tests, full pytest `1114 passed, 19 skipped`, ruff, format-check, mypy, git diff check, and process verification.
- `tj-gh21` client WABA setup guide added at `docs/client/wazzup-waba-followup-setup-guide.md`.
- `tj-gh21` production deployment succeeded: commit `1d42a39ac72e28d20d40a05514ef449be09071e0`, GitHub Actions run `26226211978`; production smoke `scripts/verify_api.py --base-url https://noor.starec.ai` passed `7 passed, 0 failed`.
- SSH release-sha verification was not available from the local environment (`noor.starec.ai:22` timed out); delivery is verified by successful GitHub Actions deploy plus production API smoke.
- Stage `tj-gh22` is verified locally on `codex/tj-gh22-fu1-service-window`: FU1 is scheduled at 23h and can use free-form text only when the real 24h WhatsApp window is still open; FU2/FU3 still require Wazzup WABA templates. Local verification passed: targeted 21 tests, full pytest `1115 passed, 19 skipped`, ruff, format-check, mypy, and process verification.
- Orchestration baseline is `balanced-v2.7`; use repo-local commands in `.codex/orchestrator.toml`.

## Next recommended

Next stage id: continue `tj-gh22` for delivery, or continue `tj-gh21` only for Wazzup template configuration.

Recommended action: review and deliver `tj-gh22` when authorized. Then collect approved Wazzup WABA EN/AR template ids/codes for FU2/FU3 using `docs/client/wazzup-waba-followup-setup-guide.md`, and configure production follow-up sending. Keep production follow-up sending disabled until FU1 text and FU2/FU3 templates are configured.

## Starter prompt for next orchestrator

Use $orchestrator-stage to continue `tj-gh22`. Current delivered production release includes commit `1d42a39ac72e28d20d40a05514ef449be09071e0`; `tj-gh20` remains in `shadow` mode only. `tj-gh21` runtime changes and Wazzup WABA client guide are merged, deployed, and production-smoke verified. `tj-gh22` FU1 23h refinement is local-only and verified; see `.codex/stages/tj-gh22/summary.md`.

## Explicit defers

- `tj-b4n` / GitHub #24 remains provider-blocked pending an official Wazzup typing endpoint.
- Production follow-up sending for GitHub #11 remains blocked pending explicit FU1 EN/AR free-form text configuration and approved Wazzup WABA FU2/FU3 template ids/codes for English and Arabic.
- Dialogue kernel `enforce` rollout remains deferred; production is intentionally `shadow` only.
