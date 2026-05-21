# Stage tj-gh21 Summary

Status: delivered

project-index: reviewed-no-change - Wazzup integration behavior changed for template payload support, but repository navigation, entrypoints, and ownership boundaries in `.codex/project-index.md` remain accurate.

Scope: GitHub #11 post-quotation follow-up behavior after Lilia's answers.

Current decisions:
- Customer-facing runtime languages are English and Arabic only.
- Russian phrases may be recognized only as inbound customer signals, not used for bot/customer output.
- After quotation PDF, Noor asks whether the quotation works for the customer.
- A clear acceptance after quotation records approval and hands off to a manager.
- Follow-up cadence is 24h, 3d, 7d; after the final follow-up with no reply, the quotation is marked rejected/no response.
- Follow-up outside the 24h WABA service window must use Wazzup WABA template transport, not plain free-form text.
- Legacy language values such as `Russian`, `ru`, `Arabic`, `arabic`, and `العربية` are normalized at customer-facing runtime boundaries; unsupported/RU values fall back to English, Arabic markers use Arabic.

Verification:
- Targeted RED/GREEN tests passed for language normalization, Wazzup template payloads, proposal cadence, final no-response status, and post-quotation acceptance handoff.
- Broader LLM/messaging follow-up suites passed.
- Review-and-fix pass targeted suite passed: 246 passed.
- Full pytest passed after review fixes: 1114 passed, 19 skipped.
- Ruff check, ruff format --check, mypy, and orchestration process verification passed.
- Pre-delivery refresh after adding the client WABA setup guide passed: git diff check, ruff check, ruff format --check, mypy, full pytest 1114 passed/19 skipped, and process verification.

Review-and-fix pass:
- Three read-only visible Codex subagents reviewed correctness, improvement quality, and Wazzup/domain behavior.
- Accepted fixes: generic `yes/ok/fine/works` approval now requires Noor's explicit quotation approval question; generic acknowledgements outside that context return a short acknowledgement without manager handoff.
- Accepted fixes: new quotations reset stale terminal decision metadata; post-quotation acceptance runs before dialogue-kernel enforce return; explicit rejection persists rejected quotation metadata.
- Accepted fixes: FU3 no longer rejects immediately; it waits a 24h final response window before no-response closure.
- Accepted fixes: Arabic locale variants such as `ar-SA`/`ar_AE` remain Arabic; EN/AR follow-up config aliases are normalized; Arabic quotation PDF caption is localized; dead no-op scheduling helpers were removed.
- Deferred: ordered Wazzup template parameter mapping until actual approved template variables are known.

Delivery status:
- Delivery authorized by user on 2026-05-21.
- Merged by fast-forward push to `main` and deployed by GitHub Actions run `26226211978`.
- Deployed runtime commit: `1d42a39ac72e28d20d40a05514ef449be09071e0`.
- Production smoke passed: `scripts/verify_api.py --base-url https://noor.starec.ai` returned `7 passed, 0 failed`.
- SSH release-sha verification was not available from the local environment because `noor.starec.ai:22` timed out.
- Client setup guide added: `docs/client/wazzup-waba-followup-setup-guide.md`.
- Production follow-up sending remains blocked until approved Wazzup WABA template ids/codes are configured for English and Arabic.
