---
schema_version: orchestration-artifact/v1
artifact_type: delegated-stream
task_id: tj-gh12.16-17
stage_id: tj-gh12
repo: treejar
branch: codex/tj-gh12-name-gate-hotfix-clean
base_branch: main
base_commit: cc3fcf5a5f3e3dd13249aaf7091a1b0d975a180a
worktree: /home/me/code/treejar/.worktrees/codex-tj-gh12-name-gate-hotfix-clean
status: accepted
delivery_method: manual integration
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: "Implemented locally in the hotfix worktree; no child branch cleanup needed."
risk_level: high
verification:
  - "uv run pytest tests/test_llm_engine.py::test_process_message_first_turn_unknown_name_blocks_exact_sku_side_effects -q: failed before fix, passed after fix"
  - "uv run pytest tests/test_response_adapter.py::test_adapt_manager_response_falls_back_when_adapter_invents_price_stock -q: failed before fix, passed after fix"
  - "uv run pytest tests/test_llm_engine.py tests/test_response_adapter.py tests/test_webhook_manager.py tests/test_services_chat_batch.py tests/test_messaging_wazzup.py tests/test_proposal_followup.py tests/test_llm_quotation.py tests/services/test_quotation_template.py tests/services/test_pdf_generator.py -q: passed, 201 passed"
  - "uv run ruff check src/ tests/: passed"
  - "uv run ruff format --check src/ tests/: passed"
  - "uv run mypy src/: passed"
  - "env DYLD_FALLBACK_LIBRARY_PATH=\"${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}\" uv run pytest tests/ -v --tb=short: passed, 1004 passed, 19 skipped"
changed_files:
  - .codex/handoff.md
  - .codex/stages/tj-gh12/summary.md
  - src/llm/engine.py
  - src/llm/response_adapter.py
  - tests/test_llm_engine.py
  - tests/test_response_adapter.py
  - .codex/stages/tj-gh12/artifacts/tj-gh12.15-live-e2e.md
  - .codex/stages/tj-gh12/artifacts/tj-gh12.16-17-hotfix.md
explicit_defers:
  - "Post-deploy live E2E B-H remains pending until this hotfix is deployed and scenario A is rechecked."
---

# Summary

Fixed two defects found during controlled production E2E:

- `tj-gh12.16`: first-turn unknown-name requests now short-circuit before product, quotation, exact-quote fallback, escalation, or deferred media side effects. The response model is `name-gate`, the reply is only the Noor/name question, and `deferred_product_media` stays empty.
- `tj-gh12.17`: private manager response adaptation now falls back to the manager draft when the adapter introduces risky unsupported claims such as price, stock, or immediate-delivery facts absent from the draft.

# Verification

RED/GREEN was run for both defects:

```text
tests/test_llm_engine.py::test_process_message_first_turn_unknown_name_blocks_exact_sku_side_effects
tests/test_response_adapter.py::test_adapt_manager_response_falls_back_when_adapter_invents_price_stock
```

Full local verification after both fixes:

```text
uv run ruff check src/ tests/ -> passed
uv run ruff format --check src/ tests/ -> passed
uv run mypy src/ -> passed
uv run pytest tests/ -v --tb=short -> 1004 passed, 19 skipped
```

# Delivery / Cleanup

Ready for merge/deploy from `codex/tj-gh12-name-gate-hotfix-clean`, followed by post-deploy live E2E scenario A recheck and then the remaining scoped B-H checks if A passes.

# Risks / Follow-ups / Explicit Defers

The first production E2E run already sent product media and one cleanup manager reply to the approved test number. The synthetic conversation is resolved and pending count is zero, but evidence is preserved in `tj-gh12.15-live-e2e.md`.
