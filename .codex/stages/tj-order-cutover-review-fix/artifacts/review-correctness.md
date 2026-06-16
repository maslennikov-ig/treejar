---
schema_version: orchestration-artifact/v1
artifact_type: delegated-stream
task_id: tj-s1qi
stage_id: tj-order-cutover-review-fix
agent_type: correctness_reviewer
subagent_model: role_default
reasoning_effort: role_default
model_reasoning_rationale: review is cross-module order/quote correctness risk
repo: treejar
branch: codex/tj-order-cutover-review-fix
base_branch: origin/main
base_commit: b03227e86db838678551deca98234d6b925144f3
worktree: /home/me/code/treejar/.worktrees/tj-order-cutover-review-fix
write_zone:
  - read-only
success_criteria:
  - identify material regressions and verification gaps for order/quote cutover
selected_docs:
  - AGENTS.md
  - .codex/orchestrator.toml
  - .codex/handoff.md
  - .codex/stages/tj-order-cutover/summary.md
  - .codex/stages/tj-order-adapter-hardening/summary.md
selected_skills:
  - code-review
selected_agents:
  - correctness_reviewer
catalog_candidates:
  - none
parallel_group: correctness-review
depends_on_streams:
  - none
parallel_decision: parallel
status: accepted
delivery_method: manual integration
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: read-only spawned agent; no branch or worktree cleanup needed
risk_level: medium
docs_impact: n/a
docs_reviewed: n/a
docs_review_notes: read-only review
verification:
  - local orchestrator independently reproduced and fixed must-fix quantity leak
changed_files:
  - none
explicit_defers:
  - none
---

# Summary

The correctness reviewer returned Conditional Pass. It found one must-fix:
legacy `pending_product_reference_quantity` could revive an expired typed
quantity frame when recent assistant history still looked like a quantity
prompt. It also found that `legacy_migration_read` existed but was never set.

# Accepted Findings

- Accepted and fixed: expired/non-answerable typed quantity frame now suppresses
  and clears legacy pending product-reference quantity metadata for that turn.
- Accepted and fixed: `legacy_migration_read` now records legacy metadata reads
  during runtime load.

# Verification

The spawned reviewer could not run pytest in its sandbox, but the orchestrator
reproduced the quantity leak with a RED process test, fixed it, and verified the
target suite: 330 passed.

# Risks / Follow-ups

No untracked correctness follow-up remains from this stream. The accepted trace
observability improvement was fixed locally.
