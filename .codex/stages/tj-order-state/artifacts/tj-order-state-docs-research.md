---
schema_version: orchestration-artifact/v1
artifact_type: delegated-stream
task_id: tj-order-state.1
stage_id: tj-order-state
agent_type: docs_researcher
subagent_model: inherit_orchestrator
reasoning_effort: role_default
model_reasoning_rationale: version-sensitive framework documentation research
repo: treejar
branch: codex/tj-order-state-refactor
base_branch: main
base_commit: 5c85a5b46d28320a1790196b48651ad6bc01a41f
worktree: read-only spawned Codex workspace
write_zone:
  - none
success_criteria:
  - source-backed recommendation for LangGraph/PydanticAI runtime decision
selected_docs:
  - LangGraph official docs
  - PydanticAI official docs
  - Rasa official docs
  - Parlant official docs
selected_skills:
  - /home/me/.agents/skills/task-router/SKILL.md
selected_agents:
  - docs_researcher
catalog_candidates:
  - none
parallel_group: A
depends_on_streams:
  - none
parallel_decision: parallel
status: accepted
delivery_method: manual integration
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: read-only spawned stream changed no files
risk_level: low
docs_impact: docs-only
docs_reviewed: updated
docs_review_notes: source links added to specs and stage summary
verification:
  - official docs lookup: passed
changed_files:
  - none
explicit_defers:
  - none
---

# Summary

The docs researcher confirmed that current official guidance supports the
existing LangGraph + Pydantic/PydanticAI approach. Rasa and Parlant are useful
architecture references for flow/repair/journey design but do not justify a new
runtime framework in this repository.

# Scope / Routing

Read-only docs stream. Selected sources were official LangGraph, PydanticAI,
Rasa, and Parlant docs. No catalog lookup was needed because installed
`docs_researcher` fit the task.

# Verification

The stream returned source-backed links and no file changes.

# Delivery / Cleanup

Accepted by orchestrator as documentation input. Cleanup is not applicable.

# Risks / Follow-ups / Explicit Defers

No explicit defers.
