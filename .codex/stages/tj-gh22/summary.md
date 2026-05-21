# Stage tj-gh22 Summary

Status: delivered; production smoke passed; E2E planned

Scope: GitHub #11 follow-up timing refinement: send FU1 before the WhatsApp/WABA 24h customer-service window usually closes, while keeping FU2/FU3 template-based.

Current decisions:
- FU1 is scheduled at approximately 23 hours after КП send time instead of 24 hours.
- Runtime still checks the real last customer inbound timestamp before sending. If the 24h window is open and FU1 free-form text is configured, FU1 uses free-form text.
- If FU1 is due but the 24h window is already closed or unsafe, it uses the existing WABA template path when a confirmed template is configured; otherwise it stays blocked rather than sending an unsafe free-form message.
- FU2 and FU3 remain outside the 24h window and require Wazzup WABA templates.
- The Wazzup client setup guide now asks for mandatory FU2/FU3 EN/AR templates only, with optional FU1 fallback templates.

Verification:
- RED test run before implementation failed on the old 24h FU1 schedule: `OPENROUTER_API_KEY=dummy uv run pytest tests/test_proposal_followup.py -v --tb=short` failed 7 tests as expected.
- Targeted GREEN passed: `OPENROUTER_API_KEY=dummy uv run pytest tests/test_proposal_followup.py tests/test_webhook.py::test_wazzup_webhook_read_status_records_proposal_read_without_reschedule tests/test_llm_prompts.py::test_build_system_prompt_includes_compact_communication_policy -v --tb=short` -> 21 passed.
- `uv run ruff check src/ tests/` passed.
- `uv run ruff format --check src/ tests/` passed.
- `uv run mypy src/` passed.
- Full pytest passed: `OPENROUTER_API_KEY=dummy uv run pytest tests/ -v --tb=short` -> 1115 passed, 19 skipped.
- `scripts/orchestration/run_process_verification.sh` passed.

Delivery status:
- Branch `codex/tj-gh22-fu1-service-window` was pushed and fast-forwarded into `main`.
- Runtime commit: `3f0ed132a12f90c6d2087f40697f0fcdc0c2b3a6`.
- GitHub Actions run `26233690578` succeeded, including deploy.
- Production smoke passed: `uv run python scripts/verify_api.py --base-url https://noor.starec.ai` -> 7 passed, 0 failed.
- Direct `/opt/noor/.release-sha` SSH verification was unavailable from the local environment because SSH public-key authentication failed. Delivery evidence is successful GitHub Actions deploy plus production API smoke.
- Full E2E execution plan added: `docs/specs/e2e-testing/tj-gh22-post-quotation-followup-e2e-plan.md`.

E2E status:
- Planned, not executed in this turn.
- Live WhatsApp sends require explicit approved run window, approved number/channel/suffixes, and access to record conversation/outbound audit evidence.
- FU1 live send requires configured EN/AR free-form texts.
- FU2/FU3 live send requires approved Wazzup WABA EN/AR template ids/codes; otherwise only blocked/fallback behavior can be verified.
