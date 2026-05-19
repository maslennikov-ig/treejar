# Stage tj-gh20: Dialogue State Kernel

Updated: 2026-05-19
Status: local implementation verified; delivery deferred
Branch: `codex/tj-gh20-dialogue-state-kernel`
Worktree: `/home/me/code/treejar/.worktrees/codex-tj-gh20-dialogue-state-kernel`
Base: `origin/main` at `f22545b7260e77ffe2d00f8ef4f24aa40a20f4f6`
Beads: `tj-gh20`, `tj-gh20.1` through `tj-gh20.7`

## Goal

Introduce a LangGraph-backed Dialogue State Kernel while keeping
`process_message` legacy behavior as the default and safe fallback.

The first release is a framework migration and observability layer:

- `legacy` is default and graph execution short-circuits before LangGraph runs.
- `shadow` writes bounded traces under `metadata_["dialogue_kernel"]["traces"]`
  and performs no kernel side effects.
- `enforce` handles only explicitly allowlisted flows; exact SKU+quantity
  selection is recognized but delegated to legacy until the kernel owns stock,
  price, and quotation side effects end to end.

## Parallel Decomposition Matrix

| Stream | Goal | Owner | Write zone | Dependencies | Verification | Model/reasoning | Decision | Reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A `tj-gh20.1` docs/evals | Spec, rollout policy, replay fixture corpus | worker Peirce | `docs/specs/*`, `tests/fixtures/dialogue/*`, `.codex/stages/tj-gh20/summary.md` | none | JSON validation, fixture contract tests | inherited | parallel accepted | Disjoint docs/fixture write zone. |
| B `tj-gh20.2-.3` state/reducer/catalog | Pydantic state, pure reducer, SKU/model resolver | worker Boole + orchestrator review | `src/dialogue/state.py`, `src/dialogue/reducer.py`, `src/dialogue/catalog_refs.py`, tests | none | dialogue state/catalog unit tests, ruff, mypy | high | parallel accepted with follow-up fixes | Disjoint from engine integration until bridge. |
| C `tj-gh20.4-.5` runner/integration | LangGraph runner, config, engine bridge, v1 flows | orchestrator sequential | `src/dialogue/runner.py`, `src/core/config.py`, `src/llm/engine.py`, tests | B interface | targeted runner/engine tests | inherited | sequential | Central `process_message` routing and metadata sync required one owner. |
| D `tj-gh20.6` evaluator/review | Replay harness and independent code review | explorer Pasteur + orchestrator | read-only review, fixture tests | after A/B/C green | review findings, replay tests | high | accepted findings fixed | Review found real rollout-safety issues; orchestrator verified and fixed them. |
| E `tj-gh20.7` delivery | Production shadow deploy, synthetic E2E, decision report | pending | deployment/runtime config | explicit approval required | production smoke/E2E | n/a | deferred | No deploy/prod mutation/GitHub closure was authorized in this task. |

## Implemented

- Added `langgraph>=1.0,<2.0`; did not add
  `langgraph-checkpoint-postgres`.
- Added `src/dialogue/` modules for state, reducer, catalog reference parsing,
  and the LangGraph runner.
- Added config defaults: `dialogue_kernel_mode=legacy`,
  `dialogue_kernel_trace_enabled=true`, and empty
  `dialogue_kernel_enforced_flows`.
- Integrated the runner into `process_message` with:
  - default legacy fallback;
  - shadow traces with legacy route recording;
  - enforce allowlist handling for name gate, quote details, product reference
    clarification, and post-quotation hold;
  - legacy metadata sync for quote-detail collection.
- Added tests for default no-op legacy mode, shadow trace safety, enforce
  allowlist behavior, known-customer hydration, legacy quote metadata hydration,
  SKU/model parsing, exact quantity delegation, replay fixtures, and engine
  integration.

## Review Findings Accepted And Fixed

- Legacy mode originally still invoked LangGraph; fixed with early short-circuit.
- State originally ignored `Conversation.customer_name` and legacy quote
  metadata; fixed with `DialogueState.from_conversation`.
- Exact SKU+quantity turns could have been intercepted by `product_selection`;
  fixed by quantity parsing plus handled=false legacy delegation.
- Post-quotation hold originally ignored legacy `last_quote_status` and
  `pending_quote_selection`; fixed through state hydration.
- Verified-policy handoff responses originally missed `legacy_route` trace
  recording; fixed in the handoff response builder.
- Replay fixtures originally only validated shape; selected scenarios now run
  through the kernel runner.

## Verification So Far

- `python -m json.tool tests/fixtures/dialogue/dialogue_state_kernel_replay.json`
  passed.
- `OPENROUTER_API_KEY=dummy uv run pytest tests/test_dialogue_runner.py tests/test_dialogue_catalog_refs.py tests/test_dialogue_state.py tests/test_dialogue_replay_fixtures.py ... -v --tb=short`
  passed: `31 passed`.
- Targeted `ruff check`, `ruff format --check`, and `mypy src/dialogue src/core/config.py`
  passed after the accepted review fixes.
- Full static gates passed: `ruff check`, `ruff format --check`, `mypy src/`,
  and `git diff --check`.
- Full pytest passed after all review fixes:
  `1098 passed, 19 skipped`.

## Explicit Defers

- `tj-gh20.7`: merge/deploy, production `shadow` E2E, decision report, and any
  enforce rollout require separate explicit approval.
- GitHub #11 remains pending Lilia's answers; this stage only models a safe
  post-quotation hold and does not close #11.
