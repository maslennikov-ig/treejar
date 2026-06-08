---
schema_version: orchestration-artifact/v1
artifact_type: review-report
task_id: tj-order-state.9
stage_id: tj-order-state
agent_type: correctness_reviewer
subagent_model: inherit_orchestrator
reasoning_effort: role_default
model_reasoning_rationale: required review-fix correctness stream
repo: treejar
branch: codex/tj-order-state-refactor
base_branch: main
base_commit: 5c85a5b46d28320a1790196b48651ad6bc01a41f
worktree: spawned read-only Codex thread
write_zone:
  - none
success_criteria:
  - identify correctness/security/test gaps in order-state refactor
selected_docs:
  - .codex/stages/tj-order-state/summary.md
  - docs/specs/dialogue-state-kernel.md
  - docs/specs/customer-facts-layer.md
selected_skills:
  - code-review
selected_agents:
  - correctness_reviewer
catalog_candidates:
  - none
parallel_group: review-fix
depends_on_streams:
  - none
parallel_decision: parallel
status: returned
delivery_method: not accepted
accepted_by_orchestrator: no
cleanup_status: cleaned
cleanup_notes: read-only spawned thread closed
risk_level: high
docs_impact: behavior
docs_reviewed: n/a
docs_review_notes: review report only
verification:
  - targeted pytest/probes: passed/reproduced gaps
changed_files:
  - none
explicit_defers:
  - none
---

# Findings

1. High must-fix: `OR` was not filtered as an alpha-SKU connector, so
   `I need 2 CH 616 or 4 CH 620` produced bogus `OR-4` with quantity `616`.
   Suggested fix: add connector stopword coverage and regression.
2. High must-fix: fact extraction wrote `order.items` for comparison turns such
   as `Can you compare 2 CH 616 and 4 CH 620?` while engine correctly returned
   no selection. Suggested fix: facts must consume the same selection decision
   gate as engine.
3. Medium high-value improvement: single named-model selections such as
   `I need 2 SKYLAND NOVO 2400` were selected by engine but absent from
   customer facts. Suggested fix: make runtime-backed `order.items` canonical
   for single and multi-line selections.

# Orchestrator Triage

Accepted. Covered by `tj-order-state.9.1` and `tj-order-state.9.3`.

# Summary

This read-only review report records findings from the assigned reviewer lens.
The orchestrator triaged the findings in `review-fix-triage.md`.

# Verification

The reviewer performed read-only inspection and targeted probes as recorded in
the frontmatter. Accepted findings were independently verified by the
orchestrator in the review-fix pass.

# Risks / Follow-ups

Remaining accepted defers are tracked in Beads and summarized in
`review-fix-triage.md`. This read-only report made no file changes.
