---
schema_version: orchestration-artifact/v1
artifact_type: delegated-stream
task_id: tj-gh21-review-fixes
stage_id: tj-gh21
repo: treejar
branch: codex/tj-gh21-post-quotation-followup
base_branch: origin/main
base_commit: 6b03389254fe5a7f7c1cb51a85f3180a3bb671b1
worktree: /home/me/code/treejar/.worktrees/codex-tj-gh14-main-merge
status: accepted
delivery_method: merge
accepted_by_orchestrator: yes
cleanup_status: blocked
cleanup_notes: branch/worktree intentionally retained until authorized merge and deployment finish
risk_level: medium
verification:
  - OPENROUTER_API_KEY=dummy uv run pytest tests/test_customer_language.py tests/test_proposal_followup.py tests/test_llm_engine.py::test_process_message_post_quotation_acceptance_hands_off_to_manager tests/test_llm_engine.py::test_post_quotation_generic_ok_after_non_approval_answer_does_not_handoff tests/test_llm_engine.py::test_post_quotation_acceptance_runs_before_dialogue_kernel_enforce tests/test_llm_quotation.py::test_create_quotation_preserves_real_sale_order_identifiers_from_flat_response -v --tb=short: passed
  - OPENROUTER_API_KEY=dummy uv run pytest tests/test_customer_language.py tests/test_proposal_followup.py tests/test_llm_engine.py tests/test_llm_quotation.py tests/test_services_chat_batch.py tests/test_messaging_wazzup.py -v --tb=short: passed (246 passed)
  - uv run ruff check src/ tests/: passed
  - uv run ruff format --check src/ tests/: passed
  - uv run mypy src/: passed
  - env DYLD_FALLBACK_LIBRARY_PATH="${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}" OPENROUTER_API_KEY=dummy uv run pytest tests/ -v --tb=short: passed (1114 passed, 19 skipped)
  - git diff --check: passed
  - scripts/orchestration/run_process_verification.sh: passed
changed_files:
  - src/services/customer_language.py
  - src/services/proposal_followup.py
  - src/llm/engine.py
  - tests/test_customer_language.py
  - tests/test_proposal_followup.py
  - tests/test_llm_engine.py
  - tests/test_llm_quotation.py
explicit_defers:
  - ordered Wazzup template parameter mapping is deferred until actual approved Wazzup template variables are known
  - production follow-up sending remains blocked until approved WABA template ids/codes for English and Arabic are configured
---

# Summary

Completed a review-and-fix pass for `tj-gh21` after three independent read-only subagent reviews. The pass accepted concrete correctness and maintainability findings, rejected/deferred broader refactors that need real Wazzup template variables, and verified the resulting changes locally.

# Review Findings

Accepted correctness findings:
- Generic `yes`/`ok`/`fine`/`works` could approve a quotation without the customer answering an explicit approval prompt.
- New quotations could inherit stale approved/rejected metadata from a previous quotation.
- `dialogue_kernel_mode=enforce` could return from `post_quotation_hold` before deterministic acceptance handling.
- Final FU3 marked the quotation rejected at send time instead of after a final response window.
- Explicit customer rejection stopped follow-up but did not persist rejected quotation decision metadata.
- Arabic locale variants such as `ar-SA` and `ar_AE` fell back to English.

Accepted improvements:
- Normalize EN/AR follow-up config aliases without accepting RU as a customer-facing output language.
- Localize quotation PDF caption for Arabic conversations.
- Remove dead no-op follow-up scheduling leftovers.

Deferred findings:
- Ordered Wazzup template parameter mapping is useful only after real template variables are known. Current follow-up template sends use no parameters, so changing the contract now would add churn without reducing current risk.
- A broader quotation decision service boundary refactor is sensible later, but this pass kept the fix focused on verified defects.

# Fix Summary

Post-quotation acceptance is now context-gated: short generic acknowledgements approve only when the previous assistant message explicitly asked whether the quotation works. The same short replies outside that context now produce a brief acknowledgement and do not notify the manager.

Follow-up metadata is safer: sending a new quotation resets terminal decision state to a fresh pending active quotation, explicit rejection writes rejected metadata, and the final follow-up opens a 24h final response window before no-response rejection.

Language behavior remains EN/AR-only for customer output, with Arabic locale variants normalized consistently.

# Verification

Passed:
- Targeted RED/GREEN review suite.
- Expanded LLM/quotation/follow-up/messaging suite: 246 passed.
- `uv run ruff check src/ tests/`.
- `uv run ruff format --check src/ tests/`.
- `uv run mypy src/`.
- Full pytest: 1114 passed, 19 skipped.
- `git diff --check`.
- `scripts/orchestration/run_process_verification.sh`.

# Risks / Follow-ups

Production follow-up sending remains blocked until approved Wazzup WABA template ids/codes are configured for English and Arabic.

Ordered Wazzup template parameter mapping is deferred until actual approved template variables are known. Current follow-up template sends pass no variables, so this is not a current send-path defect.
