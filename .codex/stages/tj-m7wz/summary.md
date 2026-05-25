# Stage tj-m7wz Summary

Status: local implementation and stage closeout complete; delivery and production E2E pending.

Scope: fix GitHub #41-#46 quotation regressions covering lost product/quantity context, quote resume after short customer replies, and unsafe customer-field provenance in generated quotation PDFs.

Current decisions:
- Missing-quantity product reference prompts persist a bounded `pending_product_reference_quantity` metadata frame.
- Bare numeric or word quantity replies consume that pending product reference and continue through the normal purchase-selection path instead of restarting with a generic opener.
- Quote item recovery now handles assistant prose confirmations such as `4 x SkyLand CH 140...`, not only Markdown table selections.
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

Review:
- Visible worker implemented the cohesive code stream in the dedicated worktree.
- First visible correctness review found one real gap: `_quote_missing_required_details` could still use stale CRM company to satisfy the company/individual gate.
- The review finding was reproduced with a failing test and fixed.
- Final visible correctness review found no blocking issues.

Delivery status:
- No production mutation, deploy, GitHub issue closure, or live WhatsApp test has been performed yet.
- User authorized live E2E on `+79262810921` after completion; production E2E still requires the fixed commit to be delivered to the runtime first.

Documentation:
- project-index: reviewed-no-change - no entrypoints, routes, directories, integrations, verification commands, or ownership boundaries changed.
- docs-reviewed: no-change-needed - behavior is covered by stage/handoff notes and regression tests; stable operator/API docs do not need changes.

Residual / handoff:
- Live production E2E must cover #41/#42, #43/#46, and #44/#45 after delivery, using approved `+79262810921`.
- No known in-scope code defers remain after local verification.
