# Implementation Plan: E2E Testing

## Approach
We will use **Subagent-Driven Development** as required for isolating parallel test definitions. Each area connects directly to an already-created `bd` issue.

### Technical Guidelines (Pydantic-AI Testing)
Based on recent `context7` research, tests that invoke `sales_agent.run` must use the following mocking pattern to prevent real LLM costs:

```python
from pydantic_ai.models.test import TestModel

# When testing specific tool logic or flow:
async def test_my_flow():
    test_model = TestModel(custom_output_text='Mocked LLM Response')
    # Because our process_message overrides the model passed inside run(),
    # override the agent globally with context or patch the model factory inside core.config
    with sales_agent.override(model=test_model):
        result = await sales_agent.run('Query', deps=mock_deps)
```

## Task Breakdown
The execution will be delegated to parallel Subagents using this plan.

### Task 1: REPL Simulation [COMPLETED]
- Bead Issue: **tj-ow3**
- Handled directly by Tech Lead.

### Task 2: RAG EmbeddingEngine semantics search tests
- Bead Issue: **tj-xw2**
- File to Create: `tests/test_e2e_rag.py`
- Test targets: Mocking `EmbeddingEngine.search`, testing `search_products` tool.

### Task 3: Pydantic-AI Tools integration tests
- Bead Issue: **tj-kuv**
- File to Create: `tests/test_e2e_tools.py`
- Test targets: Mocks for `ZohoCRMClient`, `ZohoInventoryClient`. Verifying `get_stock`, `lookup_customer`, `create_deal`, `create_quotation`.

### Task 4: SalesStage FSM traversal tests
- Bead Issue: **tj-exc**
- File to Create: `tests/test_e2e_fsm.py`
- Test targets: `advance_stage` tool. Validate the constraints in `ALLOWED_TRANSITIONS`.
