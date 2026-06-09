---
schema_version: orchestration-artifact/v1
artifact_type: delegated-stream
task_id: tj-oq7a
stage_id: tj-gh51-order-quote-cutover
agent_type: docs_reviewer
subagent_model: inherit_orchestrator
reasoning_effort: role_default
model_reasoning_rationale: docs freshness review for behavior-changing quote-frame cutover
repo: treejar
branch: codex/tj-gh51-order-quote-cutover
base_branch: origin/main
base_commit: f41aba6
worktree: /home/me/code/treejar/.worktrees/tj-gh51-order-quote-cutover
write_zone:
  - read-only
success_criteria:
  - identify stale durable docs and stage handoff gaps
selected_docs:
  - AGENTS.md
selected_skills:
  - orchestrator-stage
selected_agents:
  - docs_reviewer
catalog_candidates:
  - none
parallel_group: review
depends_on_streams:
  - none
parallel_decision: parallel
status: accepted
delivery_method: manual integration
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: read-only spawned agent report preserved and agent closed
risk_level: medium
docs_impact: behavior
docs_reviewed: updated
docs_review_notes: accepted docs findings applied to specs, handoff, and stage summary
verification:
  - read-only docs review completed: passed
changed_files:
  - none (read-only review)
explicit_defers:
  - none
---

# Summary

Read-only docs freshness review for the GH #51 order/quote frame cutover. The
orchestrator accepted the required docs updates and applied them locally. The
original agent report follows.

# Docs Reviewer Report

Agent/run: `019eab90-8bb6-7723-85ee-9f236b1e605e` (`docs_reviewer`)
Beads: `tj-oq7a`
Date: 2026-06-09

Documentation impact classification: behavior.

## Findings

1. Severity: High

Classification: must-fix.

Evidence: `docs/specs/dialogue-state-kernel.md` says quotation detail collection
is allowed while a `quote_frame` with valid lines exists. The implemented
contract is stricter: active frames are only `collecting_details` or
`repair_required`; `quoted` frames are explicitly non-resumable and tests assert
that.

Suggested fix: update the `order_runtime.quote_frame` section and
expected-answer rule to define status semantics:

- `collecting_details` and `repair_required` are active/resumable;
- `quoted` is retained as post-quotation state but must not synthesize pending
  selection, import selected items, or create `quote_details` expected-answer
  frames.

Also update older issue wording from preserving `pending_quote_selection` to
preserving canonical `quote_frame` with legacy migration fallback.

Value: prevents future operators/reviewers from treating any valid quoted frame
as resumable quote input, exactly the duplicate/wrong-quote class fixed here.

Tradeoff: slightly longer spec section, still compact and durable.

Confidence: high.

2. Severity: Medium

Classification: must-fix.

Evidence: stage summary still lists review streams as pending, but review
artifacts for code mapper, correctness, improvement, docs, and LLM architecture
are present or in progress, and accepted fixes are reflected in code/tests.

Suggested fix: update stage summary to record accepted review fixes and leave
only full verification/closeout pending.

Value: keeps stage handoff truth usable for closeout and prevents duplicate
review work.

Tradeoff: small summary update.

Confidence: high.

## Orchestrator Decision

- Accepted both findings as must-fix docs/stage updates.

# Verification

- Read-only docs review completed by spawned `docs_reviewer`: passed.

# Risks / Follow-ups

- Docs updates were applied locally and are covered by stage closeout.
