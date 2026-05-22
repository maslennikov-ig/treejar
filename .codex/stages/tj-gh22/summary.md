# Stage tj-gh22 Summary

Status: delivered; GitHub #11 closed by owner request after production quote/post-quote evidence

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
- Execution artifact added: `.codex/stages/tj-gh22/artifacts/tj-gh22.1-e2e-execution.md`.
- S0 production smoke was freshly executed and passed: `uv run python scripts/verify_api.py --base-url https://noor.starec.ai` -> 7 passed, 0 failed.
- After the user confirmed permissions and approved `+79262810921`, live synthetic sends were executed through production channel `b49b1b9d-757f-4104-b56d-8f43d62cc515`.
- Product/SKU name-gate sanity passed in conversation `c11ac597-9452-4e79-8dd9-50261dbcd768`: `Hello, I need 6 CH 616` -> name gate -> `Alex` -> product/catalog answer with no escalation.
- Exact quotation creation failed before post-quotation follow-up could be tested:
  - `baa857a8-cc87-4d4f-85c3-aa5a746fcbc1`: word-quantity exact quote request ended in `z-ai/glm-5|exact-quote-fallback` and pending escalation.
  - `d6fa2284-0029-4019-b304-285e9d352e6f`: numeric `1 CH 616` exact quote request ended in `z-ai/glm-5|exact-quote-fallback` and pending escalation.
  - `c11ac597-9452-4e79-8dd9-50261dbcd768`: after product answer, `Please prepare a quotation for 3 CH 616 chairs...` also ended in `exact-quote-fallback`.
- Root cause is tracked in new Beads stage `tj-gh23`: exact quotation frame parser/resolver/address/fallback policy. GitHub #11 should remain open until quote creation and post-quotation follow-up E2E both pass.
- Supporting local follow-up/regression pack passed: 53 tests covering post-quotation handoff/guards, follow-up stop/template/freeform/no-response paths, EN/AR language normalization, and #36/#37/#39/#40/#35 regression symptoms.

Update 2026-05-22:
- `tj-gh23` was delivered to production in runtime `322bee30d667b245a143813dbd5fccbcf120eecf`; GitHub Actions run `26279825756` succeeded including deploy; production smoke passed `7 passed, 0 failed`.
- The previous exact quotation blocker is resolved live:
  - word quantity exact product created quotation `Fr3294` in conversation `cf9f4ade-b261-4f56-b104-69062f861cdd`;
  - numeric exact product created quotation `Fr3295` in conversation `e3d30ece-31b5-46a2-a948-dd10096a4bb7`;
  - ambiguous `CH 616 chair` now asks exact item/SKU clarification without escalation in conversation `c397b396-b63a-4050-87b6-6b41eab72bea`.
- Post-quotation approval was live-tested in `cf9f4ade-b261-4f56-b104-69062f861cdd`: model `post-quotation-accepted`, expected manager handoff created, proposal follow-up stopped with `stop_reason=quotation_accepted`.
- A pre-acceptance delivery question was bot-handled without escalation, but the answer was weak and re-asked for item/quantity.
- Synthetic `tj-gh22-*` and `tj-gh23-*` pending escalations were cleaned; pending/in-progress synthetic escalations are zero.
- GitHub #11 was closed by explicit owner request on 2026-05-22. Beads `tj-gh22.1` was also closed with the same caveat: the FU1/FU2/FU3 time-delayed/template matrix and weak delivery-question answer are documented as future follow-up risk, not closure blockers.
