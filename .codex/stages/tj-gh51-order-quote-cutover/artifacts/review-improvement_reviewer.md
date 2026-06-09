---
schema_version: orchestration-artifact/v1
artifact_type: delegated-stream
task_id: tj-oq7a
stage_id: tj-gh51-order-quote-cutover
agent_type: improvement_reviewer
subagent_model: inherit_orchestrator
reasoning_effort: role_default
model_reasoning_rationale: high-value improvement review for recurring quote-state regression
repo: treejar
branch: codex/tj-gh51-order-quote-cutover
base_branch: origin/main
base_commit: f41aba6
worktree: /home/me/code/treejar/.worktrees/tj-gh51-order-quote-cutover
write_zone:
  - read-only
success_criteria:
  - identify maintainability and durability improvements for the cutover
selected_docs:
  - AGENTS.md
selected_skills:
  - orchestrator-stage
selected_agents:
  - improvement_reviewer
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
docs_review_notes: specs and stage summary updated for accepted cutover improvements
verification:
  - read-only improvement review completed: passed
changed_files:
  - none (read-only review)
explicit_defers:
  - none
---

# Summary

Read-only improvement review for the GH #51 order/quote frame cutover. The
orchestrator accepted the must-fix and high-value findings in scope. The
original agent report follows.

# Improvement Reviewer Report

Agent/run: `019eab86-f820-7123-b3a1-486a1fef1eb7` (`improvement_reviewer`)
Beads: `tj-oq7a`
Date: 2026-06-09

## Findings

1. Severity: High

Current approach: `_store_quote_frame_metadata()` is a no-op when the new frame
is `None`, so unresolved-only or empty quote writes can leave an older canonical
`order_runtime.quote_frame` alive.

Evidence: `src/llm/engine.py` `_store_quote_frame_metadata()`, plus
unresolved/empty writers in quote selection storage.

Suggested improvement: replace the helper with a single active quote-frame setter
that writes a valid frame or explicitly removes/invalidates
`order_runtime.quote_frame`. Add regression tests for prior quote frame plus
unresolved exact quote and empty selection clearing the frame.

Value: prevents preparing or resuming a quote with stale previous items.

Tradeoff/cost: small metadata behavior change; needs careful rollback tests.

Confidence: High.

Classification: must-fix.

2. Severity: High

Current approach: the spec says `order_runtime.quote_frame` is canonical for
quote details, but `_quote_customer_details_from_metadata()` still reads only
legacy `quote_customer_details`.

Evidence: `docs/specs/dialogue-state-kernel.md` describes canonical
`order_runtime.quote_frame`; `src/llm/engine.py` reader reads only legacy
metadata.

Suggested improvement: introduce one canonical quote-details reader that prefers
`quote_frame.quote_details`, then falls back to legacy metadata. Keep writes
mirrored to legacy for rollback during migration.

Value: makes the new contract real and avoids future "details missing"
regressions when only canonical frame is present.

Tradeoff/cost: moderate touch count because many call sites use the existing
reader.

Confidence: High.

Classification: must-fix.

3. Severity: Medium-High

Current approach: active quote selection variables still prefer legacy
`pending_quote_selection` before synthesizing from the canonical frame.

Evidence: `process_message()` start/resume branches use legacy-first
`pending_quote_selection` expressions.

Suggested improvement: add a single `active_quote_context()` helper that returns
frame-first items, source, unresolved state, and fallback selection. Use it for
route checks, follow-up extraction, and resume.

Value: reduces recurring drift where item reads are frame-first but
source/unresolved decisions are legacy-first.

Tradeoff/cost: moderate refactor, but it replaces duplicated branching with one
contract.

Confidence: High.

Classification: high-value improvement.

4. Severity: Medium

Current approach: `QuoteFrame.status` and `source` are free strings, and invalid
canonical frames are silently ignored.

Evidence: `src/dialogue/order_state.py` `QuoteFrame` model and metadata
validation fallback.

Suggested improvement: use `Literal`/enum-like values for status/source,
generate a stable `frame_id`, and optionally record bounded invalid-frame
diagnostics in metadata or logs.

Value: improves operator/debug usefulness and catches typos before they create
hard-to-reproduce routing behavior.

Tradeoff/cost: low to moderate; may require updating test fixtures.

Confidence: Medium.

Classification: high-value improvement.

5. Severity: Low

Current approach: two bullets in `customer-facts-layer.md` lost list indentation.

Evidence: `docs/specs/customer-facts-layer.md`.

Suggested improvement: restore the same indentation as adjacent bullets.

Value: keeps operator/spec docs readable.

Tradeoff/cost: tiny.

Confidence: High.

Classification: optional/nit.

## Top 3 Recommended Next Improvements

1. Clear or invalidate stale canonical quote frames whenever a quote writer has
   no durable valid lines.
2. Make quote details truly frame-first in the engine reader path.
3. Replace split legacy/frame selection reads with one active quote context
   helper and tests for stale legacy plus canonical frame.

## Orchestrator Decision

- Accepted finding 1 as must-fix in this pass.
- Accepted finding 2 as must-fix in this pass.
- Accepted finding 3 as high-value improvement; implement the frame-first helper
  where it reduces current duplication without broad unrelated refactor.
- Accepted finding 4 as high-value improvement; defer only if full enum/frame-id
  tightening risks widening the patch, otherwise add bounded typing.
- Accepted finding 5 as local docs fix.

# Verification

- Read-only improvement review completed by spawned `improvement_reviewer`: passed.

# Risks / Follow-ups

- Accepted findings were implemented locally except broad enum/frame-id hardening,
  which was bounded to avoid widening the regression fix.
