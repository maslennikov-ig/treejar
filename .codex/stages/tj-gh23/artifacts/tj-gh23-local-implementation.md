---
schema_version: orchestration-artifact/v1
artifact_type: delegated-stream
task_id: tj-gh23
stage_id: tj-gh23
repo: treejar
branch: codex/tj-gh22-fu1-service-window
base_branch: origin/main
base_commit: ec3a7829b1511a4db25ea8aa210d0b3219cf845d
worktree: /home/me/code/treejar/.worktrees/codex-tj-gh14-main-merge
status: accepted
delivery_method: manual integration
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: no child worktree merge cleanup was required; visible explorer subagents were read-only
risk_level: high
verification:
  - OPENROUTER_API_KEY=dummy uv run pytest tests/test_dialogue_catalog_refs.py::test_resolve_catalog_references_matches_unique_suffix_sku tests/test_llm_engine.py::test_extract_quote_customer_details_accepts_natural_delivery_address tests/test_llm_engine.py::test_extract_exact_quote_candidate_keeps_word_quantity_from_model_number tests/test_llm_engine.py::test_process_message_first_turn_unknown_name_quote_ready_resumes_deterministically tests/test_llm_engine.py::test_process_message_exact_quote_unresolved_item_clarifies_without_escalation -v --tb=short: failed before implementation, then passed
  - OPENROUTER_API_KEY=dummy uv run pytest tests/test_llm_engine.py tests/test_dialogue_catalog_refs.py -k "exact_quote or quote_customer_details or pending_quote or name_only_reply_resumes_pending_name_gate_request or first_turn_unknown_name or ch616_selection or novo_model_number or customer_details_resume or terse_details or media_captions or brand_quantity or catalog_ref" -v --tb=short: passed (65 passed, 141 deselected)
  - OPENROUTER_API_KEY=dummy uv run pytest <required regression pack for #36/#37/#39/#40/#35/#11> -v --tb=short: passed (53 passed)
  - uv run ruff check src/ tests/: passed
  - uv run ruff format --check src/ tests/: passed
  - uv run mypy src/: passed
  - OPENROUTER_API_KEY=dummy uv run pytest tests/ -v --tb=short: passed (1126 passed, 19 skipped)
  - scripts/orchestration/run_process_verification.sh: passed
changed_files:
  - .codex/handoff.md
  - .codex/stages/tj-gh22/summary.md
  - .codex/stages/tj-gh23/summary.md
  - .codex/stages/tj-gh23/artifacts/tj-gh23-local-implementation.md
  - src/dialogue/catalog_refs.py
  - src/llm/engine.py
  - tests/test_dialogue_catalog_refs.py
  - tests/test_llm_engine.py
explicit_defers:
  - tj-gh23.5: production E2E on +79262810921 remains blocked until explicit merge/deploy authorization and deployed runtime
  - tj-gh22.1: post-quotation follow-up E2E remains blocked until quotation creation is proven live
  - live synthetic pending exact-quote escalations from tj-gh22.1 must be cleaned or resolved before claiming E2E completion
---

# Summary

Implemented the local exact quotation hardening for `tj-gh23`. The exact quote path now stores a deterministic frame before LLM fallback, preserves quote details through the name gate, parses natural delivery addresses, avoids model-number quantity misreads for word quantities, resolves unique CH 616 suffix SKUs, and asks narrow clarifications for parser/resolver uncertainty instead of creating manager escalation.

# Verification

The new RED tests failed first, then passed after implementation. Targeted exact/name-gate/SKU tests, the required regression pack, full ruff, format-check, mypy, full pytest, and process verification passed locally.

# Delivery / Cleanup

No delivery action was performed. The implementation remains local in `/home/me/code/treejar/.worktrees/codex-tj-gh14-main-merge` and needs explicit authorization before merge, push, deploy, or live E2E.

# Risks / Follow-ups / Explicit Defers

Production E2E still must prove quotation creation before post-quotation follow-up testing resumes. The three synthetic pending exact-quote escalations from the live investigation must be cleaned or resolved before claiming E2E complete.
