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
  - src/integrations/inventory/sync.py
  - src/llm/engine.py
  - src/services/notifications.py
  - tests/test_inventory_sync.py
  - tests/test_llm_engine.py
  - tests/test_product_images.py
  - .codex/stages/tj-final27/artifacts/tj-final27.1.md
  - .codex/stages/tj-final27/artifacts/tj-final27.10.md
---

# Summary

Implemented deterministic commercial truth handling for catalog-vs-Zoho split, then updated it after the client clarified the concrete field mapping. Treejar Catalog API remains the single customer-facing source of truth; Noor now maps public catalog `price` to `Product.price` even when `salePrice` exists. Zoho remains operational stock/item/order execution data. Zoho `rate` is not used as replacement customer price and is not treated as a price mismatch signal.

Context7 docs-first fact used: PydanticAI tool docstrings and parameter descriptions are model-visible tool schema/description, and `RunContext` dependencies provide runtime services to tools. Therefore the `search_products`, `get_stock`, and exact-quote runtime directives were updated as behavior-bearing LLM contracts, not comments.

# Business decision implemented

- Treejar Catalog API/catalog DB is the commercial customer-facing source of truth by default.
- Public catalog API `price` maps to the client's B2C/basePrice truth.
- Public catalog API `salePrice` is not the default Noor customer-facing price without a separate approved sale policy.
- Zoho is used for operational stock/item/order execution.
- Zoho `rate` is Selling Price / operational data for this integration and is not compared against catalog `price` as a Noor mismatch.
- If Zoho SaleOrder creation accepts a line `rate`, quotation line items are created at catalog price.
- If Zoho cannot confirm the catalog item or SaleOrder creation fails, auto-quotation fails closed and manager escalation/operational alert is created.

# Changed files

- `src/integrations/inventory/sync.py`: maps `Product.price` from public catalog `price`; keeps `salePrice` in raw source data instead of using it as the default price.
- `src/llm/engine.py`: uses catalog price for exact stock/quotation decisions, removes Zoho `rate` price-mismatch alerting, and keeps missing-in-Zoho exact commitments fail-closed.
- `src/services/notifications.py`: made catalog mismatch alert issue text explicit for missing-in-Zoho catalog item cases.
- `docs/07-knowledge-base-spec.md`: aligned catalog/Zoho source-of-truth rules with the client-confirmed `price` field decision.
- `tests/test_inventory_sync.py`: added regression coverage for `price` vs `salePrice` mapping.
- `tests/test_llm_engine.py`: added/updated catalog line-rate quotation and catalog-only blocked-quotation tests.
- `tests/test_product_images.py`: added catalog-only product discovery test for SKU `00-07024023`.

# Review fixes

Review blocker: one shared `catalog_mismatch_alerted` flag deduped both price-mismatch operational alerts and missing-in-Zoho exact-commitment escalation. In a mixed quotation, SKU A price mismatch could set the flag, then SKU B missing in Zoho would record metadata but return before `notify_manager_escalation()`.

Fix: `_notify_catalog_mismatch_and_escalate()` now uses the flag only to dedupe `notify_catalog_mismatch`; it always creates manager escalation for missing-in-Zoho exact commitment. After the client clarified that Zoho `rate` is not the B2C comparison field, the mixed-case regression was updated to assert that SKU A catalog `310.65` / Zoho `685` creates no price mismatch event, while SKU B catalog-only still creates the missing-in-Zoho event and manager escalation.

# Behavior before/after

Before:

- `get_stock` returned Zoho `rate` as the exact customer-facing price.
- `create_quotation` used Zoho `rate` for PDF/SaleOrder line items.
- Catalog-only missing-Zoho handling existed for stock lookup, but price mismatch was not audited or alerted deterministically.

After:

- SKU `00-07024023` uses public catalog `price=310.65 AED` as customer-facing catalog price and does not expose `685.00 AED` as replacement price.
- Quotation line item `rate` is catalog price when catalog product exists, even when Zoho `rate` differs.
- Zoho `rate` differences do not write `conversation.metadata_["catalog_zoho_mismatches"]` and do not emit Telegram operational alerts.
- Catalog-only item can still be shown as a catalog option, but quotation creation is blocked and manager escalation/alert is created.

# Verification

- Baseline before changes: `uv run --extra dev python -m pytest -s tests/test_llm_engine.py tests/test_treejar_catalog.py tests/test_order_review_flow.py tests/test_product_images.py -q` -> passed, 69 passed.
- RED confirmation: targeted new-test command failed before implementation with 3 failed and 1 passed.
- Review RED confirmation: `uv run --extra dev python -m pytest -s tests/test_llm_engine.py::test_tools_create_quotation_mixed_price_mismatch_then_catalog_only_escalates -q` failed before the fix because `notify_manager_escalation` was awaited 0 times.
- Review fix spot check: `uv run --extra dev python -m pytest -s tests/test_llm_engine.py::test_tools_create_quotation_mixed_price_mismatch_then_catalog_only_escalates tests/test_llm_engine.py::test_tools_create_quotation_blocks_catalog_only_item_and_escalates -q` -> passed, 2 passed.
- Client clarification RED confirmation: `uv run --extra dev python -m pytest -s tests/test_inventory_sync.py::test_normalize_treejar_product_uses_catalog_price_not_sale_price tests/test_llm_engine.py::test_tools_get_stock_does_not_alert_when_zoho_rate_differs_from_catalog_price -q` -> failed before implementation with 2 failed.
- Client clarification spot check: `uv run --extra dev python -m pytest -s tests/test_inventory_sync.py tests/test_llm_engine.py::test_tools_get_stock_catalog_price_remains_customer_truth_when_zoho_rate_differs tests/test_llm_engine.py::test_tools_get_stock_does_not_alert_when_zoho_rate_differs_from_catalog_price tests/test_llm_engine.py::test_tools_create_quotation_uses_catalog_line_rate_when_zoho_rate_differs tests/test_llm_engine.py::test_tools_create_quotation_blocks_when_catalog_line_rate_override_fails tests/test_llm_engine.py::test_tools_create_quotation_ignores_zoho_rate_diff_and_catalog_only_escalates tests/test_llm_engine.py::test_tools_create_quotation_blocks_catalog_only_item_and_escalates -q` -> passed, 18 passed.
- Final targeted behavior: `uv run --extra dev python -m pytest -s tests/test_llm_engine.py tests/test_treejar_catalog.py tests/test_order_review_flow.py tests/test_product_images.py -q` -> passed, 75 passed.
- Notification regression: `uv run --extra dev python -m pytest -s tests/test_telegram_notifications.py -q` -> passed, 21 passed.
- `uv run ruff check src/ tests/` -> passed, `All checks passed!`.
- `uv run ruff format --check src/ tests/` -> passed, `232 files already formatted`.
- `uv run mypy src/` -> passed, `Success: no issues found in 124 source files`.
- `git diff --check` -> passed.
- `uv run python scripts/orchestration/validate_artifact.py .codex/stages/tj-final27/artifacts/tj-final27.1.md` -> passed, `artifact validation OK`.

# Risks / Follow-ups

- This uses the current local Zoho client contract where `create_sale_order(..., items=[{"rate": ...}])` sends line-level rates. If live Zoho rejects catalog line rates, the existing exception path fails closed and escalates instead of sending a mismatched quotation.
- `salePrice` remains stored in raw catalog source data only. It should not be activated for Noor customer-facing pricing until the client provides an explicit sale policy.
- No production/staging checks, deploys, Wazzup verification, scheduled AI Quality Controls, or unsolicited media tests were run.

# Any client decisions still pending

- None for the default B2C price path. Client clarified that the source is the catalog and the correct public catalog field is `price`, corresponding to B2C/basePrice upstream.
