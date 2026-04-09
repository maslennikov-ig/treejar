# Code Review: `tj-2bdj` Treejar Catalog Cutover

**Date**: 2026-04-09
**Scope**: Review of branch `codex/tj-2bdj-treejar-catalog-cutover` against `origin/main`, followed by a narrow local dofix for one blocking regression.
**Files**: 13 changed in agent slice, 2 changed in dofix

## Summary

|              | Critical | High | Medium | Low |
| ------------ | -------- | ---- | ------ | --- |
| Issues       | 0        | 1    | 0      | 0   |
| Improvements | —        | 0    | 0      | 0   |

**Verdict**: PASS after local dofix

## Issues

### High

#### 1. Legacy Zoho sync reintroduced a second source of truth for catalog rows

- **File**: `/home/me/code/treejar/.worktrees/codex-tj-2bdj-treejar-catalog-cutover/src/integrations/inventory/sync.py:218`
- **Problem**: The explicit legacy `sync_products_from_zoho()` path still rewrote `name_en`, `description_en`, `category`, `price`, `stock`, and `image_url`, and then ran stale deactivation against the shared `products` table.
- **Impact**: A manual Zoho sync could overwrite Treejar-backed customer-facing catalog data or deactivate Treejar-only products that are intentionally allowed to stay visible and escalate. That violated the newly fixed business rule: Treejar Catalog API is the only source of truth for catalog discovery, while Zoho is only for final stock/price confirmation before promises.
- **Fix**: Converted the Zoho path into enrichment-only refresh for existing SKUs:
  - update only `zoho_item_id`, `synced_at`, `updated_at`
  - no inserts for Zoho-only SKUs
  - no customer-facing field overwrite
  - no stale deactivation
  - no embedding regeneration

## Positive Patterns

- The Treejar client and canonical sync path were isolated cleanly from the existing runtime search/RAG stack.
- `zoho_item_id` preservation in the Treejar upsert was implemented correctly via `coalesce(...)`.
- Mismatch alert groundwork was added without prematurely rewiring the customer flow.

## Validation

- `git diff --check`: PASS
- `uv run ruff check src/integrations/inventory/sync.py tests/test_inventory_sync.py`: PASS
- `uv run ruff format --check src/integrations/inventory/sync.py tests/test_inventory_sync.py`: PASS
- `uv run mypy src/`: PASS
- `uv run pytest tests/test_inventory_sync.py tests/test_api_products.py tests/test_treejar_catalog.py tests/test_telegram_notifications.py tests/test_worker.py tests/test_zoho_sync.py -v --tb=short`: PASS (`45 passed`)
