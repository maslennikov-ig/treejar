---
schema_version: orchestration-artifact/v1
artifact_type: delegated-stream
task_id: tj-oq7a
stage_id: tj-gh51-order-quote-cutover
agent_type: correctness_reviewer
subagent_model: inherit_orchestrator
reasoning_effort: role_default
model_reasoning_rationale: high-risk regression review for quote/order state correctness
repo: treejar
branch: codex/tj-gh51-order-quote-cutover
base_branch: origin/main
base_commit: f41aba6
worktree: /home/me/code/treejar/.worktrees/tj-gh51-order-quote-cutover
write_zone:
  - read-only
success_criteria:
  - identify must-fix correctness regressions and missing tests
selected_docs:
  - AGENTS.md
selected_skills:
  - orchestrator-stage
selected_agents:
  - correctness_reviewer
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
docs_review_notes: dialogue-state and customer-facts specs updated for accepted fixes
verification:
  - read-only correctness review completed: passed
changed_files:
  - none (read-only review)
explicit_defers:
  - none
---

# Summary

Read-only correctness review for the GH #51 order/quote frame cutover. The
orchestrator accepted the must-fix findings and implemented them locally. The
original agent report follows.

# Correctness Reviewer Report

Agent/run: `019eab86-f467-77a3-a951-ddccc5c49faf` (`correctness_reviewer`)
Beads: `tj-oq7a`
Date: 2026-06-09

## Findings

1. Severity: High

Classification: must-fix.

Evidence: `_clear_pending_quote_selection()` clears `pending_quote_selection` but
keeps canonical `quote_frame` and changes status to `quoted`. Active readers
still treat any valid-line frame as pending, and `process_message()` can recreate
a pending selection from that frame. `DialogueState` also imports selected items
from the quoted frame and can set `active_flow="quote_details"`.

Impact: after a quotation is created, the old canonical frame can be resurrected
as an active quote selection. A later customer detail/proceed message can
generate a duplicate quote for already-quoted items.

Suggested fix: introduce an active-frame predicate. Only `collecting_details` and
`repair_required` are resumable. Use it in frame-to-pending conversion, active
item reads, expected-frame capture, and `DialogueState`. Treat `quoted` as
post-quotation state or archive/remove the frame on clear.

Value: prevents completed quote frames from becoming live quote input again.

Tradeoff: if analytics need quoted frames, keep them stored but make active
readers status-aware.

Confidence: high.

2. Severity: High

Classification: must-fix.

Evidence: `_store_quote_frame_metadata()` is a no-op for `None` frames. Writers
such as `_store_pending_exact_quote()` can write a new legacy unresolved
selection but leave any old canonical frame intact when there are no resolved
durable lines. `_store_pending_quote_selection()` only pops legacy metadata in
the empty-resolution branch. Since active quote items prefer canonical frame
items, stale old items can win over the current unresolved selection.

Impact: a new unresolved quote flow can accidentally carry previous quote lines
into the next quotation once the customer clarifies the new item. This is a
wrong-quote risk.

Suggested fix: when starting/storing quote state that has no durable resolved
lines, clear or explicitly replace `order_runtime.quote_frame` instead of
leaving the previous one. Avoid preferring a canonical frame over a current
legacy selection unless the frame is active and belongs to the same quote context.

Value: prevents stale quote lines from leaking across quote attempts.

Tradeoff: clearing the frame may remove some rollback context; archiving under a
non-active status/key would keep audit data without making it routable.

Confidence: high.

## Missing Tests

- Add regression coverage for "quote created, canonical frame remains with
  `status=\"quoted\"`, next message must not call `create_quotation()` with old
  items."
- Add coverage for "old canonical frame exists, new unresolved exact/sales quote
  is stored with no durable lines, follow-up must not merge old items."
- Existing tests mostly assert `pending_quote_selection` is removed, but do not
  assert canonical frame lifecycle/active-status behavior.

## Orchestrator Decision

- Accepted both findings as must-fix.
- Will add RED tests before production changes, then fix active-frame lifecycle
  and stale-frame clearing.

# Verification

- Read-only correctness review completed by spawned `correctness_reviewer`: passed.

# Risks / Follow-ups

- Accepted findings were implemented locally and verified in the stage gates.
