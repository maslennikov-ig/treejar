---
schema_version: orchestration-artifact/v1
artifact_type: local-implementation
task_id: tj-order-state.9.2/tj-order-state.9.6
stage_id: tj-order-state
repo: treejar
branch: codex/tj-order-state-refactor
base_branch: main
base_commit: 5c85a5b46d28320a1790196b48651ad6bc01a41f
worktree: /home/me/code/treejar
status: accepted
delivery_method: manual integration
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: implemented locally in the existing stage workspace; no spawned write workers used
risk_level: medium
verification:
  - targeted RED failed for missing trace, missing metadata trace, and English-only Arabic quote copy
  - targeted GREEN passed for order runtime trace, pre-retrieval selection, and Arabic missing-details gate
  - high-signal purchase-selection and quote suite passed: 73 passed, 196 deselected
  - exact-quote resume guard regression passed: 2 passed
  - changed-module suite passed: 334 passed
  - full repository pytest passed: 1335 passed, 19 skipped
  - stage closeout passed: stage closeout verification OK
changed_files:
  - src/dialogue/order_state.py
  - src/dialogue/order_runtime.py
  - src/llm/engine.py
  - tests/test_dialogue_order_runtime.py
  - tests/test_llm_engine.py
  - docs/specs/dialogue-state-kernel.md
  - docs/superpowers/plans/2026-06-08-order-state-runtime.md
explicit_defers:
  - none
---

# Summary

Implemented the two remaining `tj-order-state` follow-ups without adding a new
runtime dependency. The order runtime now emits a bounded Pydantic trace with
route, source, reason codes, line count, total latency, and per-node latency.
Plain static purchase selection now runs before FAQ and behavior-rule retrieval
when the message is not quote-like and no quote, pending quote selection,
exact-quote follow-up, or quote-intent frame is active.

The exact-quote missing-details safety gate now uses Arabic customer-facing copy
for Arabic conversations while preserving the same required fields and side
effect block.

# Verification

- RED command:
  `OPENROUTER_API_KEY=dummy uv run pytest tests/test_dialogue_order_runtime.py::test_order_runtime_trace_is_bounded_and_records_phase_latency tests/test_llm_engine.py::test_process_message_ch616_selection_confirms_without_manager_handoff tests/test_llm_engine.py::test_process_message_exact_quote_missing_details_uses_arabic_gate -v --tb=short`
  -> failed on missing trace, missing metadata trace, and English-only Arabic
  quote copy.
- GREEN command:
  same command -> `3 passed`.
- High-signal purchase-selection/quote command:
  `OPENROUTER_API_KEY=dummy uv run pytest tests/test_dialogue_order_runtime.py tests/test_llm_engine.py -v --tb=short -k "order_runtime or purchase_selection or selection_confirms or exact_quote_missing_details or quote_details or sales_order or stock_and_price or process_message_exact_quote"`
  -> `73 passed, 196 deselected`.
- Exact-quote resume guard regression:
  `OPENROUTER_API_KEY=dummy uv run pytest tests/test_llm_engine.py::test_process_message_name_only_reply_resumes_pending_exact_quote_request tests/test_llm_engine.py::test_process_message_exact_named_item_second_consultative_pass_resolves_to_catalog_sku -v --tb=short`
  -> `2 passed`.
- Changed-module suite:
  `OPENROUTER_API_KEY=dummy uv run pytest tests/test_dialogue_catalog_refs.py tests/test_dialogue_order_state.py tests/test_dialogue_order_runtime.py tests/test_fact_extractor.py tests/test_customer_memory_service.py tests/test_llm_engine.py -v --tb=short`
  -> `334 passed`.
- Quality gates:
  - `uv run ruff check src/ tests/` -> `All checks passed!`
  - `uv run ruff format --check src/ tests/` -> `293 files already formatted`
  - `uv run mypy src/` -> `Success: no issues found in 157 source files`
- Full local repository pytest:
  `env DYLD_FALLBACK_LIBRARY_PATH="${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}" OPENROUTER_API_KEY=dummy uv run pytest tests/ -v --tb=short`
  -> `1335 passed, 19 skipped`.
- Stage closeout:
  `scripts/orchestration/run_stage_closeout.py --stage tj-order-state`
  -> `stage closeout verification OK`; closeout reported that repo E2E command
  is not configured, so live/API E2E was skipped.

# Risks / Follow-ups

No explicit defers for these two tasks. Live WhatsApp/API E2E, deploy, and
production mutation remain outside this local implementation unless explicitly
approved.
