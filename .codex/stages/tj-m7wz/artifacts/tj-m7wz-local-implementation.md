---
schema_version: orchestration-artifact/v1
artifact_type: delegated-stream
task_id: tj-m7wz
stage_id: tj-m7wz
repo: treejar
branch: codex/tj-gh42-quote-context-provenance
base_branch: origin/main
base_commit: 29d16ec8d13ef8c7fb367289a27bf49c72026bea
worktree: /home/me/code/treejar/.worktrees/codex-tj-gh42-quote-context-provenance
status: accepted
delivery_method: merge
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: production synthetic conversations were closed; stage worktree retained only for final bookkeeping commit
risk_level: high
verification:
  - PYTHONPATH=. OPENROUTER_API_KEY=dummy uv run --extra dev pytest tests/test_llm_engine.py::test_process_message_quote_offer_details_do_not_stop_at_detail_capture -v --tb=short: failed before final order-summary fix, then passed
  - PYTHONPATH=. OPENROUTER_API_KEY=dummy uv run --extra dev pytest tests/test_llm_engine.py::test_process_message_quote_offer_details_do_not_stop_at_detail_capture tests/test_llm_engine.py::test_process_message_quote_details_recovers_proceed_with_units_context tests/test_llm_engine.py::test_quote_candidates_ignore_alternative_price_table_and_use_quote_offer -v --tb=short: passed
  - PYTHONPATH=. OPENROUTER_API_KEY=dummy uv run --extra dev pytest tests/test_llm_engine.py::test_process_message_quote_details_item_correction_updates_selection_first tests/test_llm_engine.py::test_process_message_stale_pending_quantity_does_not_consume_later_number -v --tb=short: failed before reviewer-fix, then passed
  - PYTHONPATH=. OPENROUTER_API_KEY=dummy uv run --extra dev pytest tests/test_llm_engine.py -k "quantity or quote or quotation or individual or availability" -v --tb=short: passed (89 passed, 122 deselected)
  - uv run ruff check src/ tests/: passed
  - uv run ruff format --check src/ tests/: passed
  - uv run mypy src/: passed
  - OPENROUTER_API_KEY=dummy uv run pytest tests/ -v --tb=short: passed (1143 passed, 16 skipped)
  - scripts/orchestration/run_process_verification.sh --stage tj-m7wz: passed
  - gh run watch 26404203850 --exit-status: passed
  - ssh noor-server 'cat /opt/noor/.release-sha; cat /opt/noor/.release-run-id': 6d91fde34f85936bb018d9ac0a778a918c05c066 / 26404203850
  - uv run python scripts/verify_api.py --base-url https://noor.starec.ai: passed (7 passed, 0 failed)
  - live E2E resume11 on +79262810921: passed, quotation Fr3306, explicit customer fields only
  - live E2E qty-final on +79262810921: passed, bare quantity 5 resumed CH 140 context
  - live E2E reviewfix on +79262810921: passed, mixed 5 CH 140 correction selected quantity 5 and quotation Fr3307 used explicit fields only
changed_files:
  - .codex/handoff.md
  - .codex/stages/tj-m7wz/summary.md
  - .codex/stages/tj-m7wz/artifacts/tj-m7wz-local-implementation.md
  - .codex/stages/tj-m7wz/artifacts/tj-m7wz-production-e2e.md
  - src/llm/engine.py
  - tests/test_llm_engine.py
explicit_defers:
  - none
---

# Summary

Implemented quotation-context and PDF-provenance fixes for GitHub #41-#46 in
the dedicated `tj-m7wz` worktree. The bot now persists pending product
references when asking for quantity, resolves bare quantity replies into the
prior product context, recovers quote items from prose and live availability
confirmations, treats `individual purchase` as customer type, and prevents
stale CRM/test company/email data from satisfying or rendering customer-facing
quotation PDF fields.

The final reviewer-fix also handles a mixed product-correction-plus-details
reply deterministically before quote resume and clears stale pending quantity
state unless the latest assistant turn actually asked for that quantity.

# Verification

The new regression tests were written before the corresponding implementation
or hotfix. Targeted quote regression tests, ruff, format check, mypy, full
pytest, process verification, CI/deploy, production smoke, and live E2E on the
approved number passed.

# Delivery

Production is running
`6d91fde34f85936bb018d9ac0a778a918c05c066` from GitHub Actions run
`26404203850`.

# Risks / Follow-ups

No in-scope code defers remain. GitHub issues were not closed by Codex.
