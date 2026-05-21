# Orchestrator Handoff

Updated: 2026-05-21
Current branch: `codex/tj-gh22-fu1-service-window`

## Current Truth

- Canonical host: `https://noor.starec.ai`; canonical runtime path: `/opt/noor`.
- Production release includes runtime commit `000dcfbc32c6a0084678c0582c983392e3b27ea6`; GitHub Actions run `26233069352` succeeded, including deploy; production smoke `scripts/verify_api.py --base-url https://noor.starec.ai` passed `7 passed, 0 failed`.
- Direct `/opt/noor/.release-sha` SSH verification was unavailable from this local environment because SSH public-key authentication failed. Treat successful GitHub Actions deploy plus production API smoke as the current delivery evidence unless a host-side check is run separately.
- Stage `tj-gh18` is delivered, deployed, live E2E verified, and GitHub #39/#35 are closed.
- Stage `tj-gh19` is delivered, deployed, live E2E verified, Beads closed, and GitHub #40 is closed.
- Stage `tj-gh20` is delivered to production in `shadow` mode. Production `SystemConfig`: `dialogue_kernel_mode=shadow`, `dialogue_kernel_trace_enabled=true`, `dialogue_kernel_enforced_flows=""`.
- `tj-gh20` decision report: keep `shadow`, do not enable `enforce` yet; artifacts live under `.codex/stages/tj-gh20/`.
- Stage `tj-gh21` is delivered to production for GitHub #11 post-quotation follow-up after Lilia's answers.
- `tj-gh21` local behavior: customer-facing output remains English/Arabic only; after КП Noor asks if the quotation works; explicit acceptance hands off to manager; customer questions before acceptance remain bot-handled.
- `tj-gh21` review-and-fix pass completed: generic `yes/ok/fine/works` approval is gated by the previous explicit quotation approval prompt; stale quotation decision metadata resets on new КП; acceptance runs before dialogue-kernel enforce; FU3 waits 24h before no-response rejection; explicit rejection persists rejected metadata; Arabic locale variants stay Arabic.
- `tj-gh21` verification passed after review fixes and after adding the Wazzup WABA guide: targeted 246 tests, full pytest `1114 passed, 19 skipped`, ruff, format-check, mypy, git diff check, and process verification.
- `tj-gh21` client WABA setup guide added at `docs/client/wazzup-waba-followup-setup-guide.md`.
- `tj-gh21` production deployment succeeded: commit `1d42a39ac72e28d20d40a05514ef449be09071e0`, GitHub Actions run `26226211978`; production smoke `scripts/verify_api.py --base-url https://noor.starec.ai` passed `7 passed, 0 failed`.
- SSH release-sha verification was not available from the local environment (`noor.starec.ai:22` timed out); delivery is verified by successful GitHub Actions deploy plus production API smoke.
- Stage `tj-gh22` is delivered to production: FU1 is scheduled at 23h and can use free-form text only when the real 24h WhatsApp window is still open; FU2/FU3 still require Wazzup WABA templates. Verification passed before delivery: targeted 21 tests, full pytest `1115 passed, 19 skipped`, ruff, format-check, mypy, process verification, GitHub Actions deploy run `26233069352`, and production smoke `7 passed, 0 failed`.
- `tj-gh22` E2E execution plan is tracked at `docs/specs/e2e-testing/tj-gh22-post-quotation-followup-e2e-plan.md`. Live E2E has not been executed after this deploy; it requires an approved test window, approved number/channel/suffixes, FU1 EN/AR free-form config, and FU2/FU3 Wazzup WABA approved template ids/codes for full template-path validation.
- Orchestration baseline is `balanced-v2.7`; use repo-local commands in `.codex/orchestrator.toml`.

## Next recommended

Next stage id: `tj-gh22.1` for controlled production E2E execution, or continue `tj-gh21` only for Wazzup template configuration.

Recommended action: run the planned controlled E2E only after explicit approval for the test window/number/channel/suffixes and after configuring FU1 EN/AR free-form text. For complete 3-day/7-day follow-up validation, first collect approved Wazzup WABA EN/AR template ids/codes for FU2/FU3 using `docs/client/wazzup-waba-followup-setup-guide.md`. Keep broad production follow-up sending disabled until FU1 text and FU2/FU3 templates are configured.

## Starter prompt for next orchestrator

Use $orchestrator-stage to continue `tj-gh22.1` E2E execution. Current delivered production release includes runtime commit `000dcfbc32c6a0084678c0582c983392e3b27ea6`; `tj-gh20` remains in `shadow` mode only. `tj-gh21` runtime changes, Wazzup WABA client guide, and `tj-gh22` FU1 23h refinement are merged, deployed, and production-smoke verified. See `.codex/stages/tj-gh22/summary.md` and `docs/specs/e2e-testing/tj-gh22-post-quotation-followup-e2e-plan.md`.

## Explicit defers

- `tj-b4n` / GitHub #24 remains provider-blocked pending an official Wazzup typing endpoint.
- Full production follow-up sending for GitHub #11 remains blocked pending explicit FU1 EN/AR free-form text configuration and approved Wazzup WABA FU2/FU3 template ids/codes for English and Arabic. FU1 can be validated independently inside the 24h window after FU1 text is configured and an approved test run is opened.
- Dialogue kernel `enforce` rollout remains deferred; production is intentionally `shadow` only.
