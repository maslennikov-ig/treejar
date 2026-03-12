# Subagent Task: E2E SalesStage FSM traversal tests
**Bead Issue**: tj-exc
**Target Path**: `tests/test_e2e_fsm.py`

## Context
You are an expert Python SDET. Your task is to implement E2E tests for the SalesStage FSM traversal of the Treejar AI Sales Bot. This corresponds to Bead issue **tj-exc**.
The dialog engine allows specific state transitions defined by `ALLOWED_TRANSITIONS` in `src/llm/engine.py`. The tool `advance_stage` performs these transitions.

## Requirements
1. Create `tests/test_e2e_fsm.py`.
2. Write tests covering the `advance_stage` tool. 
3. Verify that advancing to a highly restricted stage (e.g. `GREETING` directly to `CLOSING`) returns the error string refusing the transition.
4. Verify that advancing to an allowed stage successfully updates `Conversation.sales_stage` in the context dependencies.
5. Provide an e2e multi-turn test simulating `GREETING -> QUALIFYING -> NEEDS_ANALYSIS`, using `pydantic_ai.models.test.TestModel` for mocked agent validation.
6. All code must pass `ruff check`, `mypy --strict`, and `pytest`.

Ensure you do this in the isolated git worktree. Do not skip testing edge cases (e.g., trying to step backwards where unsupported).
