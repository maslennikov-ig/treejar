---
task_id: tj-final27.1
stage_id: tj-final27
repo: treejar
branch: codex/tj-final27-catalog-zoho-truth
base_branch: main
base_commit: c67341f3482a677a7ad71dc3969c7db018d14234
worktree: /home/me/code/treejar/.worktrees/codex-tj-final27-catalog-zoho-truth
status: returned
verification:
  - "uv run --extra dev python -m pytest -s tests/test_llm_engine.py tests/test_treejar_catalog.py tests/test_order_review_flow.py tests/test_product_images.py -q: passed, 75 passed"
  - "uv run --extra dev python -m pytest -s tests/test_telegram_notifications.py -q: passed, 21 passed"
  - "uv run ruff check src/ tests/: passed"
  - "uv run ruff format --check src/ tests/: passed"
  - "uv run mypy src/: passed"
  - "git diff --check: passed"
  - "uv run python scripts/orchestration/validate_artifact.py .codex/stages/tj-final27/artifacts/tj-final27.1.md: passed"
changed_files:
  - docs/07-knowledge-base-spec.md
  - src/llm/engine.py
  - src/services/notifications.py
  - tests/test_llm_engine.py
  - tests/test_product_images.py
  - .codex/stages/tj-final27/artifacts/tj-final27.1.md
---

# Summary

Implemented deterministic commercial truth handling for catalog-vs-Zoho split. Treejar Catalog price now remains the customer-facing price when a catalog product exists; Zoho remains operational stock/item/order execution data. Zoho `rate` is not silently used as replacement customer price.

Context7 docs-first fact used: PydanticAI tool docstrings and parameter descriptions are model-visible tool schema/description, and `RunContext` dependencies provide runtime services to tools. Therefore the `search_products`, `get_stock`, and exact-quote runtime directives were updated as behavior-bearing LLM contracts, not comments.

# Business decision implemented

- Treejar Catalog API/catalog DB is the commercial customer-facing source of truth by default.
- Zoho is used for operational stock/item/order execution.
- If catalog price and Zoho rate differ, customer-facing price remains catalog price.
- If Zoho SaleOrder creation accepts a line `rate`, quotation line items are created at catalog price.
- If Zoho cannot confirm the catalog item or SaleOrder creation fails, auto-quotation fails closed and manager escalation/operational alert is created.

# Changed files

- `src/llm/engine.py`: added narrow commercial price decision helper, mismatch metadata audit, operational alerts, catalog line-rate quotation behavior, and updated LLM tool/runtime contracts.
- `src/services/notifications.py`: made catalog mismatch alert issue text explicit for both missing-in-Zoho and price-rate mismatch cases.
- `docs/07-knowledge-base-spec.md`: aligned catalog/Zoho source-of-truth rules with the new default business decision.
- `tests/test_llm_engine.py`: added mismatch, catalog line-rate quotation, and catalog-only blocked-quotation tests.
- `tests/test_product_images.py`: added catalog-only product discovery test for SKU `00-07024023`.

# Review fixes

Review blocker: one shared `catalog_mismatch_alerted` flag deduped both price-mismatch operational alerts and missing-in-Zoho exact-commitment escalation. In a mixed quotation, SKU A price mismatch could set the flag, then SKU B missing in Zoho would record metadata but return before `notify_manager_escalation()`.

Fix: `_notify_catalog_mismatch_and_escalate()` now uses the flag only to dedupe `notify_catalog_mismatch`; it always creates manager escalation for missing-in-Zoho exact commitment. Added regression test `test_tools_create_quotation_mixed_price_mismatch_then_catalog_only_escalates`, which covers SKU A catalog `264` / Zoho `685` plus SKU B catalog-only in the same quotation run. The test asserts fail-closed response, two metadata mismatch events, bounded operational-alert count, and guaranteed manager escalation for SKU B.

# Behavior before/after

Before:

- `get_stock` returned Zoho `rate` as the exact customer-facing price.
- `create_quotation` used Zoho `rate` for PDF/SaleOrder line items.
- Catalog-only missing-Zoho handling existed for stock lookup, but price mismatch was not audited or alerted deterministically.

After:

- SKU `00-07024023` style mismatch keeps `264.00 AED` as customer-facing catalog price and does not expose `685.00 AED` as replacement price.
- Quotation line item `rate` is catalog price when catalog product exists, including mismatch cases.
- Catalog/Zoho mismatch writes `conversation.metadata_["catalog_zoho_mismatches"]` and emits a Telegram operational alert.
- Catalog-only item can still be shown as a catalog option, but quotation creation is blocked and manager escalation/alert is created.

# Verification

- Baseline before changes: `uv run --extra dev python -m pytest -s tests/test_llm_engine.py tests/test_treejar_catalog.py tests/test_order_review_flow.py tests/test_product_images.py -q` -> passed, 69 passed.
- RED confirmation: targeted new-test command failed before implementation with 3 failed and 1 passed.
- Review RED confirmation: `uv run --extra dev python -m pytest -s tests/test_llm_engine.py::test_tools_create_quotation_mixed_price_mismatch_then_catalog_only_escalates -q` failed before the fix because `notify_manager_escalation` was awaited 0 times.
- Review fix spot check: `uv run --extra dev python -m pytest -s tests/test_llm_engine.py::test_tools_create_quotation_mixed_price_mismatch_then_catalog_only_escalates tests/test_llm_engine.py::test_tools_create_quotation_blocks_catalog_only_item_and_escalates -q` -> passed, 2 passed.
- Final targeted behavior: `uv run --extra dev python -m pytest -s tests/test_llm_engine.py tests/test_treejar_catalog.py tests/test_order_review_flow.py tests/test_product_images.py -q` -> passed, 75 passed.
- Notification regression: `uv run --extra dev python -m pytest -s tests/test_telegram_notifications.py -q` -> passed, 21 passed.
- `uv run ruff check src/ tests/` -> passed, `All checks passed!`.
- `uv run ruff format --check src/ tests/` -> passed, `232 files already formatted`.
- `uv run mypy src/` -> passed, `Success: no issues found in 124 source files`.
- `git diff --check` -> passed.
- `uv run python scripts/orchestration/validate_artifact.py .codex/stages/tj-final27/artifacts/tj-final27.1.md` -> passed, `artifact validation OK`.

# Risks / Follow-ups

- This uses the current local Zoho client contract where `create_sale_order(..., items=[{"rate": ...}])` sends line-level rates. If live Zoho rejects catalog line rates, the existing exception path fails closed and escalates instead of sending a mismatched quotation.
- No production/staging checks, deploys, Wazzup verification, scheduled AI Quality Controls, or unsolicited media tests were run.

# Any client decisions still pending

- Final client confirmation of mismatch policy is still pending. This implementation follows the explicit default decision in the task prompt: catalog price is customer-facing truth and Zoho rate is operational only.
