---
schema_version: orchestration-artifact/v1
artifact_type: local-implementation
task_id: tj-s1qi
stage_id: tj-order-cutover-review-fix
agent_type: n/a
subagent_model: n/a
reasoning_effort: n/a
model_reasoning_rationale: local orchestrator accepted findings and implemented fixes
repo: treejar
branch: codex/tj-order-cutover-review-fix
base_branch: origin/main
base_commit: b03227e86db838678551deca98234d6b925144f3
worktree: /home/me/code/treejar/.worktrees/tj-order-cutover-review-fix
write_zone:
  - src/dialogue/order_state.py
  - src/dialogue/order_runtime.py
  - src/llm/engine.py
  - tests/test_dialogue_order_runtime.py
  - tests/test_llm_engine.py
  - .codex/handoff.md
  - .codex/stages/tj-order-cutover-review-fix
success_criteria:
  - accepted must-fix leaks are fixed test-first
  - target order runtime and llm engine tests pass
  - docs-reviewed and graph-reviewed decisions recorded
selected_docs:
  - AGENTS.md
  - .codex/orchestrator.toml
  - .codex/handoff.md
  - .codex/stages/tj-order-cutover/summary.md
  - .codex/stages/tj-order-adapter-hardening/summary.md
selected_skills:
  - orchestrator-stage
  - task-router
  - code-review
  - test-driven-development
  - systematic-debugging
  - verification-before-completion
  - orchestration-closeout
selected_agents:
  - correctness_reviewer
  - improvement_reviewer
  - architect_reviewer
catalog_candidates:
  - none
parallel_group: local-fix
depends_on_streams:
  - correctness-review
  - improvement-review
  - architecture-review
parallel_decision: local
status: accepted
delivery_method: manual integration
accepted_by_orchestrator: yes
cleanup_status: blocked
cleanup_notes: local feature branch/worktree retained because delivery was not requested
risk_level: medium
docs_impact: behavior
docs_reviewed: no-change-needed
docs_review_notes: existing docs already state typed runtime ownership and trace fields
verification:
  - target pytest: 330 passed
  - ruff check: passed
  - ruff format check: passed
  - mypy: passed
changed_files:
  - src/dialogue/order_state.py
  - src/dialogue/order_runtime.py
  - src/llm/engine.py
  - tests/test_dialogue_order_runtime.py
  - tests/test_llm_engine.py
  - .codex/handoff.md
  - .codex/stages/tj-order-cutover-review-fix
explicit_defers:
  - tj-order-cutover.10
  - tj-1ha9
  - tj-hqsa
  - tj-v2k9
---

# Summary

Implemented three accepted review fixes locally:

- canonical quote-frame presence now blocks invalid-frame legacy fallback;
- non-answerable typed quantity frames suppress stale legacy quantity metadata;
- `legacy_migration_read` is now set when runtime load consumes legacy metadata.

# Verification

Fresh target tests and local code gates passed after implementation and
formatting. Full repo pytest and delivery were not run because this was a local
review-and-fix branch and external delivery was not requested.

# Delivery / Cleanup

No push, commit, deploy, production mutation, or live WhatsApp E2E was run.
The worktree and local branch are retained for user review.

# Risks / Follow-ups

Remaining accepted follow-ups are tracked as `tj-order-cutover.10`, `tj-1ha9`,
`tj-hqsa`, and `tj-v2k9`. External delivery is deferred until explicit approval.
