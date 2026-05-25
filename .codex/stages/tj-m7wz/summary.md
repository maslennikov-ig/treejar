# Stage tj-m7wz Summary

Status: first production deploy exposed one residual live gap; local hotfix complete, second delivery pending.

Scope: fix GitHub #41-#46 quotation regressions covering lost product/quantity context, quote resume after short customer replies, and unsafe customer-field provenance in generated quotation PDFs.

Current decisions:
- Missing-quantity product reference prompts persist a bounded `pending_product_reference_quantity` metadata frame.
- Bare numeric or word quantity replies consume that pending product reference and continue through the normal purchase-selection path instead of restarting with a generic opener.
- Quote item recovery now handles assistant prose confirmations such as `4 x SkyLand CH 140...`, not only Markdown table selections.
- Quote item recovery also handles live availability prose such as `1,800 AED total for 4 units` when the prior assistant asks for quotation details.
- Customer detail replies are not treated as a new product selection while the previous assistant is waiting for quotation customer details.
- Terse slash-separated customer details such as `Lil / individual purchase / 2 street` store `individual purchase` as customer type instead of merging it into the customer name or company.
- Quotation required-detail checks use current quote metadata for company/customer type, delivery address, and email. Stale CRM/context values no longer satisfy the quote/PDF gate.
- Customer-facing quotation PDF fields use current quote metadata as source of truth; individual purchases render company as `Individual`, and email must be explicitly supplied for the current quote.

Verification:
- RED tests were added for GH #41/#42, GH #43, GH #45, GH #46, and the reviewer-found CRM-company fallback gap.
- Targeted quote regression pack passed: `82 passed, 122 deselected`.
- `uv run ruff check src/ tests/` passed.
- `uv run ruff format --check src/ tests/` passed.
- `uv run mypy src/` passed.
- First full `OPENROUTER_API_KEY=dummy uv run pytest tests/ -v --tb=short` exposed an isolated-worktree environment gap: `frontend/admin` lacked `esbuild`.
- `npm --prefix frontend/admin ci` installed local frontend test dependencies in the worktree; it emitted only the existing Node engine warning for Node 24 vs expected Node 22.x.
- Re-run `OPENROUTER_API_KEY=dummy uv run pytest tests/ -v --tb=short` passed: `1136 passed, 16 skipped`.
- `scripts/orchestration/run_process_verification.sh` passed.
- `scripts/orchestration/run_stage_closeout.py --stage tj-m7wz` passed.
- First production deploy of `474583c79815ce7aac52d8558f89e49cf375f85c` succeeded in GitHub Actions run `26399538830`; runtime readback and smoke passed.
- Live #41/#42 E2E passed on `+79262810921#tj-m7wz-qty-20260525a`: after name gate, CH 140 missing-quantity prompt resumed and bare `5` produced `Quantity: 5` selection confirmation.
- Live #43/#45 E2E found a residual gap before the hotfix: availability prose plus `Lil / individual purchase / 2 street` stored correct customer details, but also misinterpreted `2 street` as an unresolved product selection.
- RED hotfix test `test_process_message_terse_details_recovers_availability_quote_context` failed before the hotfix and passed after it.
- Targeted quote regression pack after hotfix passed: `83 passed, 122 deselected`.
- Full `OPENROUTER_API_KEY=dummy uv run pytest tests/ -v --tb=short` after hotfix passed: `1137 passed, 16 skipped`.

Review:
- Visible worker implemented the cohesive code stream in the dedicated worktree.
- First visible correctness review found one real gap: `_quote_missing_required_details` could still use stale CRM company to satisfy the company/individual gate.
- The review finding was reproduced with a failing test and fixed.
- Final visible correctness review found no blocking issues.

Delivery status:
- Production deploy and live WhatsApp testing are authorized for this stage.
- First deploy/live E2E was not sufficient to close the stage because it found the availability-prose detail parsing gap.
- A second hotfix deploy and live E2E rerun are pending.

Documentation:
- project-index: reviewed-no-change - no entrypoints, routes, directories, integrations, verification commands, or ownership boundaries changed.
- docs-reviewed: no-change-needed - behavior is covered by stage/handoff notes and regression tests; stable operator/API docs do not need changes.

Residual / handoff:
- Live production E2E must rerun #43/#46 and #44/#45 after the hotfix delivery, using approved `+79262810921`.
- No known in-scope code defers remain after local verification.
