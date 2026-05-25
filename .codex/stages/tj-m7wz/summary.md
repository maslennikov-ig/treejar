# Stage tj-m7wz Summary

Status: delivered, deployed, and live E2E verified.

Scope: fix GitHub #41-#46 quotation regressions covering lost product/quantity
context, quote resume after short customer replies, and unsafe customer-field
provenance in generated quotation PDFs.

Current decisions:
- Missing-quantity product reference prompts persist a bounded
  `pending_product_reference_quantity` metadata frame.
- Bare numeric or word quantity replies consume that pending product reference
  and continue through the normal purchase-selection path instead of restarting
  with a generic opener.
- Quote item recovery handles assistant prose confirmations, availability quote
  offers, compact totals, proceed prompts, and final live order-summary phrasing
  such as `Your order: 4 chairs`.
- Customer detail replies are not treated as a new product selection while the
  previous assistant is waiting for quotation customer details.
- Terse slash-separated customer details such as
  `Lil / individual purchase / 2 street` store `individual purchase` as
  customer type instead of merging it into the customer name or company.
- Quotation required-detail checks use current quote metadata for company or
  customer type, delivery address, and email. Stale CRM/context values no longer
  satisfy the quote/PDF gate.
- Customer-facing quotation PDF fields use current quote metadata as source of
  truth; individual purchases render company as `Individual`, and email must be
  explicitly supplied for the current quote.
- Mixed item-correction-plus-customer-detail replies first update the product
  selection and keep product-like fragments out of terse delivery-address
  capture.
- Stale pending product-reference quantity frames are consumed only when the
  latest assistant turn actually asked for that product reference quantity.

Verification:
- RED tests were added for GH #41/#42, GH #43, GH #45, GH #46, reviewer-found
  CRM-company fallback, availability-prose recovery, proceed-prompt recovery,
  alternative table false positives, and final live order-summary phrasing.
- `uv run ruff check src/ tests/`: passed.
- `uv run ruff format --check src/ tests/`: passed.
- `uv run mypy src/`: passed.
- Targeted quote regression pack after final review-fix passed:
  `89 passed, 122 deselected`.
- `OPENROUTER_API_KEY=dummy uv run pytest tests/ -v --tb=short`: passed,
  `1143 passed, 16 skipped`.
- `scripts/orchestration/run_process_verification.sh --stage tj-m7wz`: passed.
- GitHub Actions run `26404203850` for
  `6d91fde34f85936bb018d9ac0a778a918c05c066`: success, including deploy.
- Runtime readback: `/opt/noor/.release-sha` =
  `6d91fde34f85936bb018d9ac0a778a918c05c066`; `/opt/noor/.release-run-id` =
  `26404203850`.
- Production smoke `uv run python scripts/verify_api.py --base-url
  https://noor.starec.ai`: `7 passed, 0 failed`.
- Live #43/#46/#44/#45 E2E on approved
  `+79262810921#tj-m7wz-resume11-20260525a`: details and buy intent resumed
  known 4 x CH 140 context, asked only for explicit email, created quotation
  `Fr3306`, and metadata contained `name=Lil`, `customer_type=individual`,
  `address=2 street`, and the explicit email only.
- Live provenance readback for `tj-m7wz-resume11`: metadata did not contain
  `Test LLC` or `test@test.com`; `proposal_followup.kp_message_id` =
  `9a9e4243-f6f1-4431-915c-68480e85614a`.
- Live #41/#42 final replay on approved
  `+79262810921#tj-m7wz-qty-final-20260525a`: after quantity clarification,
  bare `5` produced `selection-confirmation` with `Quantity: 5` for CH 140,
  not a generic opener.
- Live review-fix replay on approved
  `+79262810921#tj-m7wz-reviewfix-20260525a`: after a prior 4 x CH 140 offer,
  mixed reply
  `5 CH 140 / Lil / individual purchase / 2 street / lil.reviewfix.20260525@example.com`
  produced `selection-confirmation` with `Quantity: 5` for CH 140, then
  `Yes prepare the quotation` created `Fr3307`; metadata contained explicit
  `name=Lil`, `customer_type=individual`, `address=2 street`, explicit email,
  and no `Test LLC` / `test@test.com`.
- Production synthetic cleanup: all 15 `tj-m7wz` test conversations are
  `closed` with `escalation_status=none`.

Review:
- Visible worker implemented the cohesive code stream in the dedicated worktree.
- First visible correctness review found one real gap:
  `_quote_missing_required_details` could still use stale CRM company to satisfy
  the company/individual gate.
- The review finding was reproduced with a failing test and fixed.
- Final visible correctness review found two additional risks: mixed
  item-correction-plus-details and stale pending bare quantity. Both were
  reproduced with RED tests, fixed, deployed, and live-verified where
  production state made E2E meaningful.

Delivery status:
- Direct production delivery is complete on `main` at
  `6d91fde34f85936bb018d9ac0a778a918c05c066`.
- No GitHub issues were closed by Codex.
- Beads `tj-m7wz` and children are closed with final production evidence.

Documentation:
- project-index: reviewed-no-change - no entrypoints, routes, directories,
  integrations, verification commands, or ownership boundaries changed.
- docs-reviewed: no-change-needed - behavior is internal deterministic
  state/parsing and quote-field provenance; stable operator/API docs do not need
  changes. Stage artifacts and handoff were updated.
- graph-reviewed: no-change-needed - no structural code navigation or dependency
  graph change; focused files remain `src/llm/engine.py` and
  `tests/test_llm_engine.py`.

Residual / handoff:
- No known in-scope code defers remain.
