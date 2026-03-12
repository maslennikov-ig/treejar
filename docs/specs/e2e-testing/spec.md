# E2E Testing Specification: AI Dialog Engine

## Goal
Comprehensive end-to-end testing of the dialog engine's core capabilities:
1. RAG Semantics Search (`EmbeddingEngine`).
2. Pydantic-AI Tools integration (CRM, Inventory, PDF generation).
3. SalesStage Finite State Machine (FSM) edge-to-edge traversal.

## Requirements
- Tests must be written using `pytest` and `pytest-asyncio`.
- Execution must run entirely in a local Git Worktree isolated from production databases or APIs.
- External API calls (Wazzup, Zoho) must be mocked.
- Pydantic-AI models must be mocked intelligently using `pydantic_ai.models.test.TestModel` to prevent actual LLM token consumption and latency.

## Scenarios
### 1. RAG Semantics Search (tj-xw2)
- Validate `search_products` tool logic properly calls `EmbeddingEngine`.
- Validate that the semantic search logic triggers fallback or empty results when items are irrelevant.
- Validate that prices are correctly formatted using the `apply_discount` logic based on user segments.

### 2. Tools Integration (tj-kuv)
- `get_stock_availability`: Must query the inventory client.
- `lookup_customer`: Must retrieve the correct segment from the CRM client.
- `create_deal`: Must create CRM contacts properly if missing, then create the deal.
- `create_quotation`: Must aggregate items, apply VAT, and generate a Weasyprint PDF properly.

### 3. FSM Traversal (tj-exc)
- The dialog should enforce allowed transitions (e.g., `GREETING -> QUALIFYING`, `SOLUTION -> QUOTING`).
- Valid transitions should persist the stage to the DB `Conversation` model.
- Invalid transitions should raise errors or handle gracefully without stranding the user.
