---
schema_version: orchestration-artifact/v1
artifact_type: delegated-stream
task_id: tj-memory.1
stage_id: tj-memory
agent_type: n/a
subagent_model: n/a
reasoning_effort: n/a
model_reasoning_rationale: Local architecture/spec work; no delegated stream used.
repo: treejar
branch: codex/tj-memory-customer-facts-layer
base_branch: origin/main
base_commit: d49abcfc0606102b2098880245723e6fda999193
worktree: /home/me/code/treejar
write_zone:
  - docs/specs/customer-facts-layer.md
  - docs/superpowers/plans/2026-06-04-customer-facts-layer.md
  - .codex/stages/tj-memory/summary.md
  - .codex/stages/tj-memory/artifacts/tj-memory.1-spec.md
success_criteria:
  - Customer facts layer architecture is documented.
  - Implementation plan and Beads task graph exist.
  - Profile/current-order/past-order boundary is explicit.
  - Fast-model extraction and rollout policy are specified.
selected_docs:
  - docs/specs/dialogue-state-kernel.md
  - docs/specs/dialogue-state-kernel-evals.md
selected_skills:
  - orchestrator-stage
  - task-router
  - superpowers:brainstorming
  - superpowers:writing-plans
  - senior-architect
selected_agents:
  - none - spec/task graph work stayed local; implementation may use db-migration-specialist, worker, and reviewers later.
catalog_candidates:
  - none - installed repo skills and agents are sufficient.
parallel_group: n/a
depends_on_streams:
  - none
parallel_decision: local
status: accepted
delivery_method: manual integration
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: No child worktree or delegated branch was created for this local spec stream.
risk_level: medium
docs_impact: structural
docs_reviewed: updated
docs_review_notes: New spec and plan document the architecture before implementation.
verification:
  - "uv run python scripts/orchestration/validate_artifact.py .codex/stages/tj-memory/artifacts/tj-memory.1-spec.md": passed
  - "scripts/orchestration/run_process_verification.sh": passed
changed_files:
  - docs/specs/customer-facts-layer.md
  - docs/superpowers/plans/2026-06-04-customer-facts-layer.md
  - .codex/stages/tj-memory/summary.md
  - .codex/stages/tj-memory/artifacts/tj-memory.1-spec.md
explicit_defers:
  - Production deploy/enforce mode requires separate approval and production evidence.
  - tj-gh21 remains blocked on approved Wazzup WABA EN/AR templates.
---

# Summary

Created the architecture specification, implementation plan, and Beads task graph
for the Customer Facts and Order Memory Layer.

# Verification

Verification is run from the orchestrator after this artifact is written.

# Risks / Follow-ups

The next implementation step changes database schema and central LLM routing.
Use dedicated worktrees and keep `src/llm/engine.py` integration sequential.
