---
schema_version: orchestration-artifact/v1
artifact_type: delegated-stream
task_id: tj-oq7a
stage_id: tj-gh51-order-quote-cutover
agent_type: qa_expert
subagent_model: inherit_orchestrator
reasoning_effort: role_default
model_reasoning_rationale: QA coverage review for recurring order/quote regression
repo: treejar
branch: codex/tj-gh51-order-quote-cutover
base_branch: origin/main
base_commit: f41aba6
worktree: /home/me/code/treejar/.worktrees/tj-gh51-order-quote-cutover
write_zone:
  - read-only
success_criteria:
  - review acceptance coverage and release confidence gaps
selected_docs:
  - AGENTS.md
selected_skills:
  - orchestrator-stage
selected_agents:
  - qa_expert
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
docs_review_notes: stage verification and specs updated after accepted QA findings
verification:
  - read-only QA review completed: passed
changed_files:
  - none (read-only review)
explicit_defers:
  - none
---

# Summary

Read-only QA review for the GH #51 order/quote frame cutover. The orchestrator
accepted the must-fix and high-value coverage findings. The original agent
report follows.

# QA Expert Review Report

Agent/run: `019eab90-87db-7440-9cf0-6aa4ecd2a060` (`qa_expert`)
Beads: `tj-oq7a`
Date: 2026-06-09

## Findings

1. Severity: High

Classification: must-fix.

Evidence: current tests check `quoted` frame inactive without stale legacy
`pending_quote_selection`; GH #51 recovery asserts frame lines after quote
creation but not `status == "quoted"`. Runtime can still build pending selection
from legacy first, and active quote items can fall back to legacy selection when
canonical frame is not active.

Suggested fix: add a focused test with canonical
`order_runtime.quote_frame.status="quoted"` plus stale `pending_quote_selection`;
send compact quote details after assistant quote-details prompt; assert
`create_quotation` is not called and stale SKU is not used. Also assert
`quote_frame["status"] == "quoted"` in the GH #51 recovery success test.

Value: closes the exact quoted-vs-active/stale-legacy recurrence surface.

Tradeoff: small test setup increase; no live dependency.

Confidence: high.

2. Severity: Medium

Classification: high-value improvement.

Evidence: spec requires quote-line SKU/quantity `source_refs`; implementation
populates them, but existing test only checks slot names.

Suggested fix: extend expected-answer frame test for `quote_details` to assert
`source_refs` includes each quote line SKU and quantity.

Value: protects compact-details routing when quote-details frames move further
into enforce mode.

Tradeoff: minor assertion coupling to frame metadata shape.

Confidence: medium.

## Validated Coverage

- Normal path: canonical frame write/read, multi-item bullet-summary recovery,
  compact details to quotation, stale legacy precedence when canonical active.
- Failure path: no quote-details frame from assistant prose alone, unresolved
  exact quote clears stale frame, fast extractor drops `order.item`.
- Integration edge: mocked `process_message` paths cover assistant summary
  recovery, multiple items, and quote creation without live Zoho/Wazzup.

## Residual Verification

Local gates still need rerun after latest fixes: `uv run mypy src/`, full ruff,
full pytest, and stage closeout. Live/prod E2E was not run by design.

## Orchestrator Decision

- Accepted finding 1 as must-fix test coverage.
- Accepted finding 2 as high-value test improvement in this pass.

# Verification

- Read-only QA review completed by spawned `qa_expert`: passed.

# Risks / Follow-ups

- Live/prod E2E remains explicitly blocked unless the user approves it for this
  stage.
