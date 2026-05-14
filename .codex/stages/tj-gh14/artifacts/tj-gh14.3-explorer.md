---
schema_version: orchestration-artifact/v1
artifact_type: delegated-stream
task_id: tj-gh14.3
stage_id: tj-gh14
repo: treejar
branch: codex/tj-gh14-new-issues
base_branch: origin/main
base_commit: 27ac4fae74fe3fc201522b5ceedbf76477f58e4f
worktree: /home/me/code/treejar/.worktrees/codex-tj-gh14-new-issues
status: accepted
delivery_method: manual integration
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: Read-only explorer; no extra worktree or branch was created.
risk_level: low
verification:
  - "Orchestrator reviewed cited code paths in src/llm/engine.py, src/services/escalation_state.py, src/services/chat.py, and tests."
changed_files:
  - .codex/stages/tj-gh14/artifacts/tj-gh14.3-explorer.md
explicit_defers:
  - none
---

# Summary

Read-only explorer checked GitHub #36. The relevant bug was not an actual
`sales_stage` reset after escalation resolution. The reset-like customer-visible
behavior came from the static first-turn name gate and static name-only
`name-capture` branch in `src/llm/engine.py`, which previously discarded the
customer's prior substantive request.

# Accepted Findings

- Store a bounded pending first-turn request in `Conversation.metadata_` under a
  dedicated key, separate from `quote_customer_details` and
  `pending_quote_selection`.
- On the subsequent name-only reply, store the name, consume the pending request,
  and continue the normal routing path with the prior request as the effective
  user query.
- Resolved escalation handling does not write `sales_stage`; a regression test
  should assert the current stage is preserved.

# Verification

The orchestrator implemented and verified these findings in local code. The
wide modified LLM/escalation suite passed: `158 passed`.

# Risks / Follow-ups / Explicit Defers

No explicit defers. The original visible "reset" symptom was covered as a
name-gate resume bug plus a resolved-escalation stage preservation regression.
