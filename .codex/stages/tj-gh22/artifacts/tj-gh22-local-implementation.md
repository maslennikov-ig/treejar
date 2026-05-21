---
schema_version: orchestration-artifact/v1
artifact_type: delegated-stream
task_id: tj-gh22
stage_id: tj-gh22
repo: treejar
branch: codex/tj-gh22-fu1-service-window
base_branch: origin/main
base_commit: 32dabb352e8aa8cb584ca575651835a82aef2e0b
worktree: /home/me/code/treejar/.worktrees/codex-tj-gh14-main-merge
status: accepted
delivery_method: merge
accepted_by_orchestrator: yes
cleanup_status: blocked
cleanup_notes: branch/worktree retained pending delivery authorization
risk_level: low
verification:
  - OPENROUTER_API_KEY=dummy uv run pytest tests/test_proposal_followup.py -v --tb=short: failed before implementation as expected on old 24h FU1 schedule
  - OPENROUTER_API_KEY=dummy uv run pytest tests/test_proposal_followup.py tests/test_webhook.py::test_wazzup_webhook_read_status_records_proposal_read_without_reschedule tests/test_llm_prompts.py::test_build_system_prompt_includes_compact_communication_policy -v --tb=short: passed (21 passed)
  - uv run ruff check src/ tests/: passed
  - uv run ruff format --check src/ tests/: passed
  - uv run mypy src/: passed
  - OPENROUTER_API_KEY=dummy uv run pytest tests/ -v --tb=short: passed (1115 passed, 19 skipped)
  - scripts/orchestration/run_process_verification.sh: passed
changed_files:
  - src/services/proposal_followup.py
  - src/llm/communication_policy.py
  - tests/test_proposal_followup.py
  - tests/test_webhook.py
  - tests/test_llm_prompts.py
  - docs/client/wazzup-waba-followup-setup-guide.md
explicit_defers:
  - production follow-up sending still requires explicit configuration of FU1 free-form text and approved Wazzup WABA template ids/codes for FU2/FU3
---

# Summary

Implemented the FU1 service-window refinement locally. FU1 now becomes due at 23 hours instead of 24 hours, and the existing send planner still verifies the actual WhatsApp free-form window from the last customer inbound message before sending.

# Notes

This does not make unsafe free-form sends possible: if the real 24h window has closed, the code still requires a WABA template or blocks the send. The client WABA guide now asks for mandatory FU2/FU3 templates only, with optional FU1 fallback templates.
