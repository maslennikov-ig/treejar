---
schema_version: orchestration-artifact/v1
artifact_type: live-e2e
task_id: tj-8r79
stage_id: tj-order-state
repo: treejar
branch: main
base_branch: main
base_commit: 5c85a5b46d28320a1790196b48651ad6bc01a41f
worktree: /home/me/code/treejar
status: accepted
delivery_method: merge
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: approved live phone ending 0921 reset to blank active conversation after final E2E
risk_level: high
verification:
  - local ruff, format, mypy, and full pytest passed
  - GitHub Actions run 27146046204 passed lint, test, type-check, deploy
  - production marker matched SHA 770da1721837496c70a5e28902c26e8f275cafc9
  - production API smoke passed 8/0
  - final live WhatsApp E2E matrix passed
changed_files:
  - src/llm/engine.py
  - tests/test_llm_engine.py
  - .codex/stages/tj-order-state/artifacts/tj-order-state-live-e2e.md
  - .codex/stages/tj-order-state/summary.md
  - .codex/handoff.md
explicit_defers:
  - GitHub issue closure was not performed in this run
---

# Summary

Date: 2026-06-08
Stage: `tj-order-state`
Beads: `tj-8r79`
Approved channel: live WhatsApp test number ending `0921`
Canonical host: `https://noor.starec.ai`

Final live E2E for `tj-order-state` was run on the approved live WhatsApp test
number ending `0921` after production deployment.

## Deployment

- Final production SHA: `770da1721837496c70a5e28902c26e8f275cafc9`.
- Final deploy run: `27146046204`.
- Production marker check:
  `/opt/noor/.release-sha` -> `770da1721837496c70a5e28902c26e8f275cafc9`;
  `/opt/noor/.release-run-id` -> `27146046204`.
- Production compose check: `app`, `worker`, `nginx`, `db`, and `redis` were
  up after deploy.
- API smoke after final deploy:
  `uv run python scripts/verify_api.py --base-url https://noor.starec.ai`
  -> `8 passed, 0 failed`.

# Verification

- RED before first live-fix:
  `tests/test_llm_engine.py::test_process_message_stock_price_question_returns_catalog_option_list`
  failed because stock+price inquiry returned an incomplete LLM response.
- GREEN after first live-fix:
  targeted stock/price, stock-and-price guard, and ordinal selection tests
  -> `3 passed`.
- RED before second live-fix:
  `tests/test_llm_engine.py::test_process_message_ambiguous_ch616_selection_returns_catalog_options`
  failed because `4 CH 616 chairs` produced manager-verification text.
- GREEN after second live-fix:
  targeted ambiguous CH616, stock+price, and ordinal selection tests
  -> `3 passed`.
- High-signal order regression pack after second fix:
  `uv run pytest tests/test_llm_engine.py -k 'stock_price or stock_and_price or ordinal_selection or purchase_selection or ch616 or pending_quantity_descriptor or missing_quantity_reference or quote_details_only_model_position or captures_product_preference or product_preference_frame' -q`
  -> `50 passed, 221 deselected`.
- Final local gates:
  - `uv run ruff check src/ tests/` -> passed.
  - `uv run ruff format --check src/ tests/` -> passed.
  - `uv run mypy src/` -> passed.
  - `uv run pytest tests/ -v --tb=short` -> `1345 passed, 19 skipped`.
- Final GitHub Actions run `27146046204`:
  `lint`, `test`, `type-check`, and `deploy` all completed successfully.

## Live Scenario Results

All final live scenarios below ran against production SHA
`770da1721837496c70a5e28902c26e8f275cafc9`.

| ID | Scenario | Result |
| --- | --- | --- |
| D1 | `What is the stock and price for 2 CH 616 chairs?` | Passed. Response model `z-ai/glm-5\|stock-price-options`; listed CH 616 NEW black and CH 616 black with price and stock; escalation remained `none`. |
| D2 | `The first option please.` after D1 | Passed. Response model `z-ai/glm-5\|selection-confirmation`; selected CH 616 NEW black qty 2; total `590.00 AED`; escalation remained `none`. |
| A | `2 SKYLAND NOVO 2400 Meeting Table and 4 CH 616 NEW black chairs` | Passed. Response model `z-ai/glm-5\|selection-confirmation`; preserved both lines and quantities; total `4,660.00 AED`; escalation remained `none`. |
| B | Compact quote details after A | Passed. Response model `z-ai/glm-5\|quote-resume`; quotation `Fr3362` created and sent; sale order id `378603000022421848` recorded in archived metadata. |
| C1 | `SKYLAND NOVO 2400 Meeting Table` without quantity | Passed. Response model `z-ai/glm-5\|product-quantity-clarify`; asked for quantity only. |
| C2 | `Only SKYLAND NOVO 2400 2 position` after C1 | Passed. Response model `z-ai/glm-5\|selection-confirmation`; selected exact meeting table qty 2; total `3,480.00 AED`; escalation remained `none`. |
| E1 | `I need 4 CH 616 chairs.` | Passed after second fix. Response model `z-ai/glm-5\|selection-confirmation`; returned catalog options with prices/stocks instead of manager verification; escalation remained `none`. |
| E2 | `The first option please.` after E1 | Passed. Response model `z-ai/glm-5\|selection-confirmation`; selected CH 616 NEW black qty 4; total `1,180.00 AED`; escalation remained `none`. |

# Risks / Follow-ups

## Cleanup

- The approved live phone was reset after final E2E.
- Cleanup created a blank active conversation
  `48e0ab68-cc4f-43a6-a3fd-87be8c3609b7`.
- Production quote artifacts created during live validation remain in Zoho:
  at minimum `Fr3361` and `Fr3362`.

## Review Notes

- The two live-discovered defects were fixed with existing catalog, Product,
  Zoho inventory, and static response helpers; no new runtime framework or
  large regex branch was added.
- `stock+price` inquiry and ambiguous `CH 616` selection now share the same
  catalog-backed option resolver and WhatsApp-friendly option formatter.

docs-reviewed: updated - this artifact, stage summary, and handoff now include
production deployment, live E2E evidence, and cleanup status.
graph-reviewed: no-change-needed - Graphify is not configured; no
`graphify-out/GRAPH_REPORT.md` or `[knowledge_graph]` configuration exists.
