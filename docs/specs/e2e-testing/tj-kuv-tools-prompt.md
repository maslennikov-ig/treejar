# Subagent Task: E2E Pydantic-AI Tools integration tests
**Bead Issue**: tj-kuv
**Target Path**: `tests/test_e2e_tools.py`

## Context
You are an expert Python SDET. Your task is to implement integration tests for the Pydantic-AI tools used by the Treejar AI Sales Bot (CRM, Inventory, PDF). This corresponds to Bead issue **tj-kuv**.
The tools are defined in `src/llm/engine.py`.

## Requirements
1. Create `tests/test_e2e_tools.py`.
2. Write unit/integration tests for the `pydantic-ai` tools: `get_stock`, `lookup_customer`, `create_deal`, and `create_quotation`.
3. Use `unittest.mock.AsyncMock` to mock `ZohoCRMClient` and `ZohoInventoryClient` methods.
4. Use `pydantic_ai.models.test.TestModel` inside an override context (`sales_agent.override(...)`) if running full agent cycles, or invoke the tool methods directly using a mock `RunContext`.
5. Ensure PDF Generation (`create_quotation`) tests assert that `messaging_client.send_media` is actually called.
6. All code must pass `ruff check`, `mypy --strict`, and `pytest`.

Ensure you do this in the current git worktree. Follow RED-GREEN-REFACTOR strict TDD.
