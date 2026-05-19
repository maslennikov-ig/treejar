# Stage tj-gh20: Dialogue State Kernel

Updated: 2026-05-19
Status: delivered to production in shadow mode
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
| E `tj-gh20.7` delivery | Production shadow deploy, synthetic E2E, decision report | orchestrator | deployment/runtime config, `.codex/stages/tj-gh20/artifacts/tj-gh20.7-delivery.md` | explicit approval received | production smoke/E2E | n/a | completed | Deployed with customer-visible behavior still legacy; shadow traces provide decision evidence before any enforce rollout. |

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
- Delivery commit `9e967d5acd862e98c74b472c1d6fa102e686bf3f` was
  fast-forwarded to `main` and deployed by GitHub Actions run `26098722338`.
- Production `/opt/noor/.release-sha` matches
  `9e967d5acd862e98c74b472c1d6fa102e686bf3f`.
- Production smoke passed:
  `uv run python scripts/verify_api.py --base-url https://noor.starec.ai`
  -> `7 passed, 0 failed`.
- Production `SystemConfig` is set to `dialogue_kernel_mode=shadow`,
  `dialogue_kernel_trace_enabled=true`, and empty
  `dialogue_kernel_enforced_flows`.
- Synthetic production E2E with mock messaging passed for name-gate resume,
  quote-detail context preservation, `NOVO 2400` non-quantity parsing,
  `CH 616` quantity parsing, product reference clarification, and
  side-effect-free shadow traces.

## Delivery Decision

- Keep production in `shadow` mode. Do not switch to `enforce` yet.
- Shadow traces show the kernel is equal or better for the tested
  name-gate, product/SKU, and quote-details flows while still allowing legacy
  to perform all customer-visible behavior.
- The post-quotation hold scenario showed a useful mismatch: the kernel would
  preserve quotation context, while legacy answered with a manager-confirm
  message. Because GitHub #11 is still waiting for Lilia's policy answers, this
  remains a tracked defer rather than an enforce rollout.

## Explicit Defers

- Enforce rollout remains deferred until shadow evidence is reviewed and #11
  follow-up policy questions are answered.
- GitHub #11 remains pending Lilia's answers; this stage only models a safe
  post-quotation hold and does not close #11.
