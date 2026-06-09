---
schema_version: orchestration-artifact/v1
artifact_type: delegated-stream
task_id: tj-oq7a
stage_id: tj-gh51-order-quote-cutover
agent_type: code_mapper
subagent_model: inherit_orchestrator
reasoning_effort: role_default
model_reasoning_rationale: read-only code path mapping before order/quote cutover review
repo: treejar
branch: codex/tj-gh51-order-quote-cutover
base_branch: origin/main
base_commit: f41aba6
worktree: /home/me/code/treejar/.worktrees/tj-gh51-order-quote-cutover
write_zone:
  - read-only
success_criteria:
  - map order/quote ownership and legacy cutover risk paths
selected_docs:
  - AGENTS.md
selected_skills:
  - orchestrator-stage
selected_agents:
  - code_mapper
catalog_candidates:
  - none
parallel_group: review
depends_on_streams:
  - none
parallel_decision: parallel
status: accepted
delivery_method: manual integration
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: read-only spawned agent report preserved and agent closed
risk_level: medium
docs_impact: behavior
docs_reviewed: updated
docs_review_notes: stage summary and specs updated after accepted findings
verification:
  - read-only code mapping completed: passed
changed_files:
  - none (read-only review)
explicit_defers:
  - none
---

# Summary

Read-only code mapping for the GH #51 order/quote frame cutover. The original
agent report follows.

# Code Mapper Report: GH #51 Order/Quote Cutover

Agent/run: `019eab60-f5b4-70e0-9354-af4dc1dedd68` (`code_mapper`, read-only)
Beads: `tj-oq7a`
Date: 2026-06-09

## Scope

Map the current order/quote runtime and identify the recurring #51 failure path
before file-changing implementation.

## Findings

- Normal path before this cutover:
  `process_message()` -> dialogue kernel -> typed order runtime
  (`run_order_runtime`) -> bridge `_purchase_selection_from_order_runtime()` ->
  `_store_pending_quote_selection()` legacy metadata -> quote details via
  `_extract_quote_customer_details()`/`_store_extracted_quote_customer_details()`
  -> quote resume reads `pending_quote_selection` -> `create_quotation()`.
- `DialogueState.from_conversation()` imported legacy
  `quote_customer_details` and `pending_quote_selection.items` into slots and
  used `active_flow="quote_details"`.
- Legacy active paths found:
  `_store_pending_quote_selection`, `_store_pending_sales_order_quote`,
  `_store_pending_exact_quote`, and `_store_pending_quote_from_last_assistant_selection`.
- Prose heuristics found:
  `_last_assistant_asked_quote_customer_details()`,
  `_last_assistant_offered_quote_for_selection()`,
  `_quote_candidates_from_last_assistant_selection()`, and dialogue runner
  `_is_quote_details_context()`.
- Exact bad customer-facing response was `_pending_quote_missing_items_message()`,
  emitted when pending selection had no valid items/unresolved items or when
  current details existed after a quote-details prompt but no pending selection
  existed.

## Recommendation Accepted

- Canonical `QuoteFrame` should be the normal source of quote-ready items and
  details.
- `pending_quote_selection` should be read-only migration/rollback input, not
  the normal authority.
- Last-assistant prose recovery should remain repair-only.
- `quote_details` expected frames should carry item refs from the canonical
  frame and must not be created from assistant prose alone.

## Implementation Impact

Accepted into local implementation:

- `src/dialogue/order_state.py`: `QuoteLine`, `QuoteFrame`, metadata helpers.
- `src/llm/engine.py`: canonical quote frame writers/readers, repair cleanup,
  no-frame repair response.
- `src/dialogue/state.py`: quote-frame-to-selected-items migration.
- `src/llm/fact_extractor.py`: remove legacy singular `order.item` authority.
- Regression tests for #51 and related frame/facts contracts.

# Verification

- Read-only code mapping completed by spawned `code_mapper`: passed.

# Risks / Follow-ups

- None beyond the accepted review/fix work tracked in the stage summary.
