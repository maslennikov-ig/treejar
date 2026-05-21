---
schema_version: orchestration-artifact/v1
artifact_type: delegated-stream
task_id: tj-gh21
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
  - OPENROUTER_API_KEY=dummy uv run pytest tests/test_llm_prompts.py tests/test_proposal_followup.py tests/test_messaging_wazzup.py tests/test_response_adapter.py tests/test_llm_engine.py::test_process_message_post_quotation_acceptance_hands_off_to_manager tests/test_webhook.py::test_wazzup_webhook_read_status_records_proposal_read_without_reschedule tests/test_llm_quotation.py::test_create_quotation_tool -v --tb=short: passed
  - env DYLD_FALLBACK_LIBRARY_PATH="${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}" OPENROUTER_API_KEY=dummy uv run pytest tests/test_proposal_followup.py tests/test_messaging_wazzup.py tests/test_response_adapter.py tests/test_llm_prompts.py tests/test_webhook.py tests/test_llm_quotation.py tests/test_llm_engine.py -v --tb=short: passed
  - OPENROUTER_API_KEY=dummy uv run pytest tests/test_order_status.py tests/test_verified_answers.py::test_customer_facing_verified_answer_builders_normalize_legacy_arabic_markers tests/test_services_chat_batch.py::test_escalation_fallback_normalizes_legacy_arabic_language_marker tests/test_services_followup_details.py::test_feedback_request_normalizes_legacy_arabic_language_marker -q: passed
  - env DYLD_FALLBACK_LIBRARY_PATH="${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}" OPENROUTER_API_KEY=dummy uv run pytest tests/ -v --tb=short: passed (1107 passed, 19 skipped)
  - uv run ruff check src/ tests/: passed
  - uv run ruff format --check src/ tests/: passed
  - uv run mypy src/: passed
  - git diff --check: passed
  - scripts/orchestration/run_process_verification.sh: passed
changed_files:
  - src/services/customer_language.py
  - src/services/proposal_followup.py
  - src/integrations/messaging/wazzup.py
  - src/llm/engine.py
  - src/llm/order_status.py
  - src/llm/verified_answers.py
  - src/llm/prompts.py
  - src/llm/response_adapter.py
  - src/llm/communication_policy.py
  - src/services/chat.py
  - src/services/followup.py
  - tests/test_proposal_followup.py
  - tests/test_messaging_wazzup.py
  - tests/test_response_adapter.py
  - tests/test_llm_prompts.py
  - tests/test_llm_engine.py
  - tests/test_llm_quotation.py
  - tests/test_order_status.py
  - tests/test_verified_answers.py
  - tests/test_services_chat_batch.py
  - tests/test_services_followup_details.py
  - tests/test_webhook.py
explicit_defers:
  - production enablement requires actual Wazzup WABA template ids/codes for English and Arabic
---

# Summary

Implemented the local `tj-gh21` post-quotation hardening stream. Customer-facing language routing is now constrained to EN/AR, including legacy language values at fallback boundaries. Quotation messages ask for approval, acceptance after a sent quotation records approved metadata and escalates to manager, follow-up cadence is 24h/3d/7d, and Wazzup template sends use documented `templateId/templateValues` or `@template:` text payloads.

# Verification

Targeted regression tests, broader LLM/messaging follow-up suites, full pytest, ruff, format check, mypy, and orchestration process verification passed.

# Delivery / Cleanup

Delivery authorized; branch remains active until merge/deploy finishes.

# Risks / Follow-ups / Explicit Defers

Production follow-up sends must not be enabled until Treejar has configured approved WABA template identifiers or template codes in Wazzup for English and Arabic.
