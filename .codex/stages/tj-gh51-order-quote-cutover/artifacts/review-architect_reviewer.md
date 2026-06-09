---
schema_version: orchestration-artifact/v1
artifact_type: delegated-stream
task_id: tj-oq7a
stage_id: tj-gh51-order-quote-cutover
agent_type: architect_reviewer
subagent_model: inherit_orchestrator
reasoning_effort: role_default
model_reasoning_rationale: architecture review for canonical quote-frame ownership
repo: treejar
branch: codex/tj-gh51-order-quote-cutover
base_branch: origin/main
base_commit: f41aba6
worktree: /home/me/code/treejar/.worktrees/tj-gh51-order-quote-cutover
write_zone:
  - read-only
success_criteria:
  - review boundaries, coupling, and lifecycle consistency
selected_docs:
  - AGENTS.md
selected_skills:
  - orchestrator-stage
selected_agents:
  - architect_reviewer
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
docs_review_notes: accepted architecture findings documented in specs and stage summary
verification:
  - read-only architecture review completed: passed
changed_files:
  - none (read-only review)
explicit_defers:
  - none
---

# Summary

Read-only architecture review for the GH #51 order/quote frame cutover. The
orchestrator accepted both findings and implemented them locally. The original
agent report follows.

# Architect Reviewer Report

Agent/run: `019eab90-8f62-7421-9600-b5b90f87dd6d` (`architect_reviewer`)
Beads: `tj-oq7a`
Date: 2026-06-09

## Findings

1. Severity: High

Classification: must-fix.

Evidence: `process_message()` computes frame-aware quote context, but the early
neutral detail-capture guard checks only legacy `pending_quote_selection`. The
canonical frame resume path is lower, so a canonical-only frame plus customer
details and compacted/non-matching recent history can return `detail-capture`
before quote resume.

Suggested fix: replace that guard with an active quote context check, or
introduce one active quote helper and use it for early guards and resume.

Value: makes `QuoteFrame` a real owner even when `pending_quote_selection` is
absent and recent assistant prose is unavailable.

Tradeoff: neutral detail updates during an active quote frame will be treated as
quote-detail progress, which matches the new ownership model.

Confidence: medium-high.

2. Severity: Medium-High

Classification: high-value improvement.

Evidence: `_clear_pending_quote_selection()` marks canonical frames
`status="quoted"`, and `create_quotation()` records proposal follow-up metadata.
But `DialogueState.from_conversation()` derives post-quote state only from legacy
`last_quote_status` or `pending_quote_selection.source == "quotation_sent"`.

Suggested fix: teach `DialogueState.from_conversation()` to map
`quote_frame.status == "quoted"` and/or proposal follow-up pending metadata into
`slots.quote_sent`, `post_quotation_status`, and
`active_flow="post_quotation_hold"`.

Value: keeps active vs quoted lifecycle coherent for future kernel enforcement
and avoids split-brain metadata.

Tradeoff: small coupling to quote/proposal metadata shape; keep it as local
parser helper.

Confidence: high.

## Orchestrator Decision

- Accepted finding 1 as must-fix.
- Accepted finding 2 as high-value improvement; implement quote-frame status
  mapping in `DialogueState` with focused coverage.

# Verification

- Read-only architecture review completed by spawned `architect_reviewer`: passed.

# Risks / Follow-ups

- Accepted findings were implemented locally and verified in the stage gates.
