---
schema_version: orchestration-artifact/v1
artifact_type: delegated-stream
task_id: tj-final27.17
stage_id: tj-final27
agent_type: n/a
subagent_model: n/a
reasoning_effort: n/a
model_reasoning_rationale: local orchestrator fix; no subagent launched because the defect had one narrow write zone and production retest depends on deploy approval
repo: treejar
branch: codex/tj-final27-price-objection-selection
base_branch: main
base_commit: 9bf8a20d3f6c1dd64b72cd41de3fdf9b6f13108c
worktree: /home/me/code/treejar
write_zone:
  - src/llm/engine.py
  - tests/test_llm_engine.py
success_criteria:
  - scripts/bot_test.py smoke markers cannot be parsed as SKU or selected item evidence
  - price/value objections after SKU answers do not create pending quote selection from a synthetic marker
  - existing purchase-selection and price-objection tests still pass
selected_docs:
  - docs/testing/final-controlled-e2e-runbook-2026-04-29.md
  - .codex/stages/tj-final27/artifacts/tj-final27.9.md
selected_skills:
  - orchestrator-stage
  - superpowers:systematic-debugging
  - superpowers:test-driven-development
selected_agents:
  - none
catalog_candidates:
  - none
parallel_group: local-fix
depends_on_streams:
  - none
parallel_decision: local
status: accepted
delivery_method: n/a
accepted_by_orchestrator: yes
cleanup_status: pending
cleanup_notes: Keep branch until the fix is merged, deployed, and production retested.
risk_level: medium
docs_impact: behavior
docs_reviewed: updated
docs_review_notes: Stage artifact, stage summary, handoff, and Beads were updated; durable client docs do not need behavior copy changes until production retest completes.
verification:
  - uv run --extra dev pytest tests/test_llm_engine.py::test_extract_word_quantity_purchase_selection_ignores_smoke_marker -q: failed before implementation as expected
  - uv run --extra dev pytest tests/test_llm_engine.py::test_extract_word_quantity_purchase_selection_ignores_smoke_marker -q: passed
  - uv run --extra dev pytest tests/test_llm_engine.py::test_extract_word_quantity_purchase_selection_ignores_smoke_marker tests/test_llm_engine.py::test_extract_purchase_selection_accepts_numeric_hyphenated_sku tests/test_llm_engine.py::test_process_message_price_objection_uses_compact_sales_fallback tests/test_llm_engine.py::test_process_message_stale_pending_quantity_does_not_consume_later_number -q: passed
  - uv run --extra dev pytest tests/test_llm_engine.py -q: passed, 218 passed
  - uv run ruff check src/ tests/: passed
  - uv run ruff format --check src/ tests/: passed
  - uv run mypy src/: passed
  - scripts/orchestration/run_process_verification.sh --stage tj-final27: passed
changed_files:
  - src/llm/engine.py
  - tests/test_llm_engine.py
explicit_defers:
  - production retest of tj-final27.17 requires explicit push/deploy approval because https://noor.starec.ai still runs main@000798e
---

# Summary

The 2026-05-26 controlled text-only E2E found that a price/value objection after a SKU answer was routed to `selection-confirmation`. Root cause was not the business phrase itself: `scripts/bot_test.py` appends markers like `[smoke:bf823564]`, and the word-quantity purchase-selection parser did not strip that marker before SKU extraction. The parser interpreted `bf823564` as SKU `BF-823564` inside `a better value option? [smoke:bf823564]`.

The local fix strips synthetic test markers before purchase-selection parsing. The new regression test reproduced the failure before the fix and passes after it.

# Scope / Routing

This was kept local because the defect had one narrow write zone: `src/llm/engine.py` and `tests/test_llm_engine.py`. No subagent was launched. The work used the final E2E runbook and the current `tj-final27.9` artifact as evidence.

# Verification

Local verification passed:

- RED: `test_extract_word_quantity_purchase_selection_ignores_smoke_marker` failed because `[smoke:bf823564]` was parsed as SKU `BF-823564`.
- GREEN: the same test passed after stripping synthetic markers before purchase-selection parsing.
- Targeted selection/price tests passed.
- Full `tests/test_llm_engine.py` passed: `218 passed`.
- `ruff`, format-check, `mypy`, and stage process verification passed.

# Delivery / Cleanup

The fix is accepted locally on branch `codex/tj-final27-price-objection-selection`. It is not pushed, merged to deployed `main`, or deployed. Keep the branch until production retest is approved and completed.

# Risks / Follow-ups / Explicit Defers

Production retest is still pending. `https://noor.starec.ai` still runs `main@000798e`, so repeating the live price-objection scenario before deploy would only reproduce the old bug.
