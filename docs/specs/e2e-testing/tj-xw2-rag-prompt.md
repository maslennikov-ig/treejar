# Subagent Task: E2E RAG EmbeddingEngine semantics search tests
**Bead Issue**: tj-xw2
**Target Path**: `tests/test_e2e_rag.py`

## Context
You are an expert Python SDET. Your task is to implement the E2E RAG Pipeline tests for the Treejar AI Sales Bot. This corresponds to Bead issue **tj-xw2**.
We are using `pydantic-ai`, `pytest`, `pytest-asyncio`, and `unittest.mock`. 
The `search_products` tool is defined in `src/llm/engine.py`.

## Requirements
1. Create `tests/test_e2e_rag.py`.
2. Write tests that mock `EmbeddingEngine.search` to return fixed `Product` instances (from `src.schemas.product`).
3. Use `pydantic_ai.models.test.TestModel` to evaluate the agent's behavior globally (refer to docs: `with sales_agent.override(model=TestModel(custom_output_text="...")): ...`) or test the `perform_search_products` tool directly using RunContext.
4. Ensure the test verifies the `apply_discount` logic where a given CRM Segment correctly alters the formatted price string outputted by the tool.
5. All code must pass `ruff check`, `mypy --strict`, and `pytest`.

Ensure you do this in the `e2e-repl-simulation` worktree. Follow RED-GREEN-REFACTOR.
