# Stage tj-gh23 Summary

Status: delivered to production; exact quotation creation live E2E passed

Scope: harden exact quotation creation after live `tj-gh22.1` E2E found quote-ready CH 616 messages escalating before quotation creation.

Current decisions:
- Exact quote intent is captured deterministically before LLM fallback and persisted as `quote_intent_frame` through the first-turn name gate.
- Natural delivery phrases such as `delivered to Office 1202, Business Bay, Dubai`, `delivery to ...`, and `ship to ...` are stored as quotation customer address details.
- Word-quantity exact quote requests such as `one Skyland Operative Chair CH 616 NEW black...` keep quantity `1` and do not treat model number `616` as quantity.
- Catalog/SKU resolution handles `CH 616`, `CH-616`, `CH616`, and Cyrillic `СН 616` against unique suffix SKUs such as `CH 616 NEW black`; ambiguous suffix variants remain unresolved for customer clarification.
- When a stem SKU has multiple suffix products, the resolver uses the full customer item text to disambiguate only a unique best match. This fixed the live `CH 616 NEW black` edge found during first production E2E.
- Parser/resolver uncertainty stores pending exact quote state and asks a narrow catalog/SKU clarification instead of notifying the manager.

Verification:
- RED targeted tests failed before implementation for suffix SKU resolution, natural address extraction, word quantity parsing, name-gate quote resume, and fail-open exact quote clarification.
- Targeted GREEN exact/name-gate/SKU/quote regression pack passed: 65 passed, 141 deselected.
- Required #36/#37/#39/#40/#35/#11 regression pack passed: 53 passed.
- Production-discovered suffix disambiguation regression test failed before the hotfix and passed after the hotfix.
- `uv run ruff check src/ tests/` passed.
- `uv run ruff format --check src/ tests/` passed.
- `uv run mypy src/` passed.
- `OPENROUTER_API_KEY=dummy uv run pytest tests/ -v --tb=short` passed: 1127 passed, 19 skipped.
- `scripts/orchestration/run_process_verification.sh` passed.
- `scripts/orchestration/run_stage_closeout.py --stage tj-gh23` passed.

Delivery status:
- User explicitly authorized merge, deploy, production testing, and use of `+79262810921`.
- Pushed to `main` in two commits:
  - `ffad8fb939323baffe3776f9a95050a172fd05c8` - initial exact quotation frame hardening.
  - `322bee30d667b245a143813dbd5fccbcf120eecf` - production-found suffix SKU disambiguation hotfix.
- GitHub Actions run `26279825756` succeeded, including deploy.
- `/opt/noor/.release-sha` verified runtime `322bee30d667b245a143813dbd5fccbcf120eecf`; `/opt/noor/.release-run-id` verified `26279825756`.
- Production smoke passed: `uv run python scripts/verify_api.py --base-url https://noor.starec.ai` -> 7 passed, 0 failed.
- Live E2E on approved `+79262810921` and channel `b49b1b9d-757f-4104-b56d-8f43d62cc515` proved:
  - word quantity exact product creates quotation `Fr3294` after name gate in conversation `cf9f4ade-b261-4f56-b104-69062f861cdd`;
  - numeric quantity exact product creates quotation `Fr3295` after name gate in conversation `e3d30ece-31b5-46a2-a948-dd10096a4bb7`;
  - ambiguous `CH 616 chair` asks a narrow item/SKU clarification with no escalation in conversation `c397b396-b63a-4050-87b6-6b41eab72bea`;
  - approval after quotation routes to `post-quotation-accepted`, stops the proposal follow-up chain, and creates the expected manager handoff.
- Cleanup completed:
  - old `tj-gh22-*` synthetic pending escalations are resolved and conversations closed;
  - new `tj-gh23-*` synthetic conversations are closed;
  - pending/in-progress synthetic escalations for `tj-gh22-*` and `tj-gh23-*` are zero.

Residual / handoff:
- GitHub #11 should remain open. Quote creation is no longer the blocker, but the full follow-up E2E matrix still needs FU1 EN/AR free-form config confirmation and FU2/FU3 approved Wazzup WABA template ids/codes.
- A live pre-acceptance question, `Is delivery included in this quotation?`, was bot-handled without escalation, but the reply was semantically weak and re-asked for item/quantity. Track that under `tj-gh22.1` before closing #11.
