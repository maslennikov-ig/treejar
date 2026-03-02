# Zoho Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement the missing bulk stock API endpoint, add explicit tests for the Zoho LLM tools, and update the task plan.

**Architecture:** We will update the `inventory.py` router to call the existing `get_stock_bulk` method in the Zoho Inventory client. We will also add unit tests to `test_llm_engine.py` using `AsyncMock`.

**Tech Stack:** FastAPI, Pytest, PydanticAI.

---

### Task 1: Implement Bulk Stock API Endpoint

**Files:**
- Modify: `src/api/v1/inventory.py`
- Modify: `tests/test_api_inventory.py`

**Step 1: Write the failing test**
Update `test_get_stock_levels_not_implemented` (or create a new one) in `tests/test_api_inventory.py` to mock `get_stock_bulk` and test `GET /api/v1/inventory/stock/?skus=A&skus=B` returning 200 instead of 501.

**Step 2: Run test to verify it fails**
Run: `uv run pytest tests/test_api_inventory.py -v`

**Step 3: Write minimal implementation**
Update `src/api/v1/inventory.py` `get_stock_levels` (around line 47). Remove the `raise HTTPException(status_code=501)` and implement the logic using `inventory.get_stock_bulk(skus)`.

**Step 4: Run test to verify it passes**
Run: `uv run pytest tests/test_api_inventory.py -v`

**Step 5: Commit**
```bash
git add src/api/v1/inventory.py tests/test_api_inventory.py
git commit -m "feat: implement bulk stock check API endpoint"
```

### Task 2: Write tests for LLM tools (check_stock, lookup_customer, create_deal)

**Files:**
- Modify: `tests/test_llm_engine.py`

**Step 1: Write the failing tests**
Add `test_tools_get_stock`, `test_tools_lookup_customer`, and `test_tools_create_deal` at the end of `tests/test_llm_engine.py`. 
Use the `mock_deps` fixture, instantiate a `RunContext`, mock the `ZohoInventoryClient` and `ZohoCRMClient` inside `SalesDeps`, and call the tool functions directly. Assert the correct methods were awaited on the mocks.

**Step 2: Run tests to verify they fail/pass**
Run: `uv run pytest tests/test_llm_engine.py -v`

**Step 3: Fix tools if needed**
If the tests reveal any minor type issues or bugs in `src/llm/engine.py`, fix them. Otherwise, just ensure the tests pass.

**Step 4: Commit**
```bash
git add tests/test_llm_engine.py src/llm/engine.py
git commit -m "test: add explicit tests for CRM/Inventory LLM tools"
```

### Task 3: Update documentation

**Files:**
- Modify: `docs/task-plan.md`

**Step 1: Update task plan**
Mark the Week 4 CRM API endpoints (`GET /contacts`, `POST /contacts`, `POST /deals`, `PATCH /deals`) and Bulk query inventory as `[x]`. Mark Week 4 LLM tools and Inventory check as fully completed `[x]`.

**Step 2: Commit**
```bash
git add docs/task-plan.md
git commit -m "docs: mark Week 4 CRM and Inventory tasks as completed"
```
