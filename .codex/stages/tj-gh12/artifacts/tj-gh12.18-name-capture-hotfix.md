---
schema_version: orchestration-artifact/v1
artifact_type: delegated-stream
task_id: tj-gh12.18
stage_id: tj-gh12
repo: treejar
branch: codex/tj-gh12-name-gate-hotfix-clean
base_branch: main
base_commit: 91e61fca5390f857b5902f8476b5ee54a87dbf24
worktree: /home/me/code/treejar/.worktrees/codex-tj-gh12-name-gate-hotfix-clean
status: accepted
delivery_method: manual integration
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: "Implemented locally in the hotfix worktree; production recheck pending after deploy."
risk_level: high
verification:
  - "uv run pytest tests/test_llm_engine.py::test_process_message_name_only_reply_after_name_gate_does_not_escalate -q": failed before fix, passed after fix
  - "uv run pytest tests/test_llm_engine.py -q": passed, 125 passed
  - "uv run pytest tests/test_llm_engine.py tests/test_response_adapter.py tests/test_webhook_manager.py tests/test_services_chat_batch.py tests/test_messaging_wazzup.py tests/test_proposal_followup.py tests/test_llm_quotation.py tests/services/test_quotation_template.py tests/services/test_pdf_generator.py -q": passed, 202 passed
  - "uv run ruff check src/ tests/": passed
  - "uv run ruff format --check src/ tests/": passed
  - "uv run mypy src/": passed
  - "env DYLD_FALLBACK_LIBRARY_PATH=\"${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}\" uv run pytest tests/ -v --tb=short": passed, 1005 passed and 19 skipped
changed_files:
  - src/llm/engine.py
  - tests/test_llm_engine.py
  - .codex/stages/tj-gh12/artifacts/tj-gh12.15-post-hotfix-live-e2e.md
  - .codex/stages/tj-gh12/artifacts/tj-gh12.18-name-capture-hotfix.md
explicit_defers:
  - "Post-deploy live B-H E2E remains pending until this fix is deployed and the name-only reply scenario is rechecked."
---

# Summary

Fixed the production blocker found during post-hotfix E2E: after the first-turn name gate, a name-only reply such as `My name is E2E Tester.` now extracts and stores the customer name, returns a local `name-capture` acknowledgement, and does not invoke the LLM or manager escalation path.

The same extraction also stores natural-language names in quotation customer metadata, while preserving the original first-turn product side-effect guard.

# Verification

RED/GREEN regression:

```text
tests/test_llm_engine.py::test_process_message_name_only_reply_after_name_gate_does_not_escalate
```

Fresh local verification after the fix:

```text
uv run pytest tests/test_llm_engine.py -q -> 125 passed
uv run pytest impacted suite -q -> 202 passed
uv run ruff check src/ tests/ -> passed
uv run ruff format --check src/ tests/ -> passed
uv run mypy src/ -> passed
uv run pytest tests/ -v --tb=short -> 1005 passed, 19 skipped
```

# Delivery / Cleanup

Ready for a second fast-forward hotfix deploy from `codex/tj-gh12-name-gate-hotfix-clean`, followed by live recheck of the name-only reply and then B-H continuation.

# Risks / Follow-ups / Explicit Defers

Live B-H coverage is still paused until production includes this fix. The previous B blocker conversation was resolved via the application-level manager-reply handler and remains documented in `tj-gh12.15-post-hotfix-live-e2e.md`.
