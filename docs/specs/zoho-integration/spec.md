# Specification: Zoho Integration (Week 4) & LLM Tools Completion

## 1. Overview
This specification outlines the remaining work for Week 4 of the Treejar AI Seller project. It focuses on exposing Zoho CRM and Zoho Inventory functions through the FastAPI backend and ensuring the LLM tools for checking stock and managing CRM deals are fully tested and functional.

## 2. Current State
- **Zoho CRM API Routers:** Endpoints for `GET /contacts/{phone}`, `POST /contacts/`, `POST /deals/`, and `PATCH /deals/{deal_id}` are **already implemented** in `src/api/v1/crm.py` and are thoroughly tested.
- **Zoho Inventory API Routers:** Endpoint for `GET /stock/{sku}` is implemented. However, bulk stock queries (`GET /stock/`) and sale-orders endpoints currently raise HTTP 501 Not Implemented.
- **LLM Tools:** `get_stock`, `lookup_customer`, and `create_deal` functions exist in `src/llm/engine.py`. They are wired up to the PydanticAI agent, but lack explicit unit tests in `tests/test_llm_engine.py` to guarantee their behavior against mock data without spinning up the entire agent.

## 3. Requirements

### 3.1. Inventory Bulk Stock API
- **Endpoint:** `GET /api/v1/inventory/stock/?skus=SKU1&skus=SKU2`
- **Behavior:** Should use the already existing `ZohoInventoryClient.get_stock_bulk(skus)` method to return a list of `StockLevel` objects.
- **Validation:** Should return 200 OK with data, or an empty array if none of the SKUs are found. Must not raise 501.

### 3.2. LLM Tools Verification & Testing
- **Goal:** Ensure `get_stock`, `lookup_customer`, and `create_deal` tools correctly interact with their dependencies (`ZohoInventoryClient` and `ZohoCRMClient`).
- **Behavior:** Write explicit unit tests in `tests/test_llm_engine.py` mimicking the style of `test_tools_search_products`. These tests must verify that the correct Zoho client methods are called and the correct text responses are returned to the LLM context. Make any necessary fixes to `src/llm/engine.py` if the tests reveal bugs.

### 3.3. Task Plan Update
- Mark the CRM endpoints in `docs/task-plan.md` as completed since they already exist in the codebase.
