---
task_id: tj-final27.10
stage_id: tj-final27
repo: treejar
branch: codex/tj-final27-catalog-zoho-truth
base_branch: main
base_commit: c67341f3482a677a7ad71dc3969c7db018d14234
worktree: /home/me/code/treejar/.worktrees/codex-tj-final27-catalog-zoho-truth
status: returned
verification:
  - "uv run --extra dev python -m pytest -s tests/test_inventory_sync.py::test_normalize_treejar_product_uses_catalog_price_not_sale_price tests/test_llm_engine.py::test_tools_get_stock_does_not_alert_when_zoho_rate_differs_from_catalog_price -q: failed before implementation, 2 failed"
  - "uv run --extra dev python -m pytest -s tests/test_inventory_sync.py tests/test_llm_engine.py::test_tools_get_stock_catalog_price_remains_customer_truth_when_zoho_rate_differs tests/test_llm_engine.py::test_tools_get_stock_does_not_alert_when_zoho_rate_differs_from_catalog_price tests/test_llm_engine.py::test_tools_create_quotation_uses_catalog_line_rate_when_zoho_rate_differs tests/test_llm_engine.py::test_tools_create_quotation_blocks_when_catalog_line_rate_override_fails tests/test_llm_engine.py::test_tools_create_quotation_ignores_zoho_rate_diff_and_catalog_only_escalates tests/test_llm_engine.py::test_tools_create_quotation_blocks_catalog_only_item_and_escalates -q: passed, 18 passed"
  - "uv run --extra dev python -m pytest -s tests/test_inventory_sync.py tests/test_llm_engine.py tests/test_treejar_catalog.py tests/test_order_review_flow.py tests/test_product_images.py tests/test_telegram_notifications.py -q: passed, 109 passed"
  - "uv run ruff check src/ tests/: passed"
  - "uv run ruff format --check src/ tests/: passed"
  - "uv run mypy src/: passed"
  - "git diff --check: passed"
  - "uv run python scripts/orchestration/validate_artifact.py .codex/stages/tj-final27/artifacts/tj-final27.1.md && uv run python scripts/orchestration/validate_artifact.py .codex/stages/tj-final27/artifacts/tj-final27.10.md: passed"
changed_files:
  - docs/07-knowledge-base-spec.md
  - src/integrations/inventory/sync.py
  - src/llm/engine.py
  - tests/test_inventory_sync.py
  - tests/test_llm_engine.py
  - .codex/stages/tj-final27/artifacts/tj-final27.1.md
  - .codex/stages/tj-final27/artifacts/tj-final27.10.md
---

# Summary

Client clarified that the public catalog remains the single commercial truth and its `price` field maps to upstream B2C/basePrice. Noor now stores catalog `price` as `Product.price` even when `salePrice` exists.

# Business decision implemented

- Use public catalog API `price` as the default B2C/customer-facing price.
- Treat public catalog API `salePrice` as secondary raw source data until the client approves a separate sale policy.
- Do not compare Zoho `rate` against catalog `price`; `rate` is not the B2C truth for Noor.
- Keep missing-in-Zoho catalog items fail-closed for quotation/SaleOrder with manager escalation and operational alert.

# Changed behavior

- `sync_products_from_treejar_catalog` no longer lets `salePrice` override catalog `price`.
- `get_stock` and `create_quotation` use catalog price and ignore Zoho `rate` differences for mismatch/audit/alert purposes.
- Existing catalog-only missing-in-Zoho behavior remains protected by tests.

# Verification

- RED: `uv run --extra dev python -m pytest -s tests/test_inventory_sync.py::test_normalize_treejar_product_uses_catalog_price_not_sale_price tests/test_llm_engine.py::test_tools_get_stock_does_not_alert_when_zoho_rate_differs_from_catalog_price -q` failed before implementation.
- Focused GREEN: `uv run --extra dev python -m pytest -s tests/test_inventory_sync.py tests/test_llm_engine.py::test_tools_get_stock_catalog_price_remains_customer_truth_when_zoho_rate_differs tests/test_llm_engine.py::test_tools_get_stock_does_not_alert_when_zoho_rate_differs_from_catalog_price tests/test_llm_engine.py::test_tools_create_quotation_uses_catalog_line_rate_when_zoho_rate_differs tests/test_llm_engine.py::test_tools_create_quotation_blocks_when_catalog_line_rate_override_fails tests/test_llm_engine.py::test_tools_create_quotation_ignores_zoho_rate_diff_and_catalog_only_escalates tests/test_llm_engine.py::test_tools_create_quotation_blocks_catalog_only_item_and_escalates -q` passed, 18 passed.
- Extended behavior: `uv run --extra dev python -m pytest -s tests/test_inventory_sync.py tests/test_llm_engine.py tests/test_treejar_catalog.py tests/test_order_review_flow.py tests/test_product_images.py -q` passed, 88 passed.
- Notifications: `uv run --extra dev python -m pytest -s tests/test_telegram_notifications.py -q` passed, 21 passed.
- Final combined behavior/notification set: `uv run --extra dev python -m pytest -s tests/test_inventory_sync.py tests/test_llm_engine.py tests/test_treejar_catalog.py tests/test_order_review_flow.py tests/test_product_images.py tests/test_telegram_notifications.py -q` passed, 109 passed.
- `uv run ruff check src/ tests/` passed.
- `uv run ruff format --check src/ tests/` passed.
- `uv run mypy src/` passed.
- `git diff --check` passed.
- Artifact validation passed for `tj-final27.1.md` and `tj-final27.10.md`.

# Risks / Follow-ups

- `salePrice` is intentionally not used as default customer-facing price. A separate client-approved sale policy is needed before activating it in Noor.
- If Zoho rejects catalog-priced SaleOrder line items, the existing create-quotation path fails closed and escalates to a manager.
- No prod/staging/deploy/push was performed.

# Notes

- No prod/staging/deploy/push was performed.
- Full final verification commands are run by the orchestrator before closeout.
