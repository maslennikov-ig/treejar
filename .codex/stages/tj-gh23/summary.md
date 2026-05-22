# Stage tj-gh23 Summary

Status: local implementation verified; delivery and live E2E not run

Scope: harden exact quotation creation after live `tj-gh22.1` E2E found quote-ready CH 616 messages escalating before quotation creation.

Current decisions:
- Exact quote intent is captured deterministically before LLM fallback and persisted as `quote_intent_frame` through the first-turn name gate.
- Natural delivery phrases such as `delivered to Office 1202, Business Bay, Dubai`, `delivery to ...`, and `ship to ...` are stored as quotation customer address details.
- Word-quantity exact quote requests such as `one Skyland Operative Chair CH 616 NEW black...` keep quantity `1` and do not treat model number `616` as quantity.
- Catalog/SKU resolution handles `CH 616`, `CH-616`, `CH616`, and Cyrillic `СН 616` against unique suffix SKUs such as `CH 616 NEW black`; ambiguous suffix variants remain unresolved for customer clarification.
- Parser/resolver uncertainty stores pending exact quote state and asks a narrow catalog/SKU clarification instead of notifying the manager.

Verification:
- RED targeted tests failed before implementation for suffix SKU resolution, natural address extraction, word quantity parsing, name-gate quote resume, and fail-open exact quote clarification.
- Targeted GREEN exact/name-gate/SKU/quote regression pack passed: 65 passed, 141 deselected.
- Required #36/#37/#39/#40/#35/#11 regression pack passed: 53 passed.
- `uv run ruff check src/ tests/` passed.
- `uv run ruff format --check src/ tests/` passed.
- `uv run mypy src/` passed.
- `OPENROUTER_API_KEY=dummy uv run pytest tests/ -v --tb=short` passed: 1126 passed, 19 skipped.
- `scripts/orchestration/run_process_verification.sh` passed.

Delivery status:
- No merge, push, deploy, GitHub issue closure, production mutation, or live WhatsApp E2E was performed.
- `tj-gh22.1` production E2E remains blocked until this fix is delivered and deployed with explicit current authorization.
- The three synthetic pending exact-quote escalations from the investigation still need cleanup or resolution before claiming E2E completion.
