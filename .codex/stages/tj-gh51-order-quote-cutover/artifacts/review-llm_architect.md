---
schema_version: orchestration-artifact/v1
artifact_type: delegated-stream
task_id: tj-oq7a
stage_id: tj-gh51-order-quote-cutover
agent_type: llm_architect
subagent_model: inherit_orchestrator
reasoning_effort: role_default
model_reasoning_rationale: LLM/tool-flow architecture review for quote-state cutover
repo: treejar
branch: codex/tj-gh51-order-quote-cutover
base_branch: origin/main
base_commit: f41aba6
worktree: /home/me/code/treejar/.worktrees/tj-gh51-order-quote-cutover
write_zone:
  - read-only
success_criteria:
  - review prompt/tool workflow boundaries and quote resume risks
selected_docs:
  - AGENTS.md
selected_skills:
  - orchestrator-stage
selected_agents:
  - llm_architect
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
docs_review_notes: durable quote-frame behavior documented after review
verification:
  - read-only llm architecture review completed: passed
changed_files:
  - none (read-only review)
explicit_defers:
  - none
---

# LLM Architect Review Report

Agent/run: `019eab86-fc65-71a3-824f-91ccc489ef11` (`llm_architect`)
Beads: `tj-oq7a`
Date: 2026-06-09

## Summary

Current flow: customer turn -> facts/DialogueState -> order runtime/legacy
guards -> quote metadata (`pending_quote_selection` plus
`order_runtime.quote_frame`) -> quote-details resume -> `create_quotation`.
The riskiest boundary is converting durable quote state back into a pending quote
selection before `create_quotation`, where canonical frame, legacy metadata, and
assistant-prose repair can mix.

Recommended architecture change: introduce one helper-level active quote frame
context that returns pending/quoted/repair state from the canonical frame first,
using legacy `pending_quote_selection` strictly as migration fallback when the
frame is absent.

## Findings

1. High / must-fix: `quoted` quote frame is still considered pending and can
   repeat `create_quotation`.

Evidence: `_clear_pending_quote_selection()` marks frame `status="quoted"` after
successful quotation, but `_pending_quote_selection_from_quote_frame()` accepts
any valid frame without status check. Resume path can then call
`create_quotation` again.

Suggested fix: synthetic pending selection from frame should return only for
`collecting_details` or `repair_required`. `quoted` should route to
post-quotation state, not quote-resume.

Value: prevents duplicate Zoho/PDF/WhatsApp side effects.

Tradeoff: intentional resend needs a separate explicit flow.

Confidence: high.

Classification: must-fix.

2. High / must-fix: stale legacy unresolved markers can override a complete
canonical quote frame.

Evidence: active items are frame-first, but unresolved checks still consider
legacy selection. Complete `order_runtime.quote_frame` plus stale
`pending_quote_selection.unresolved_items` can still trigger
`quote-resume-missing-items`.

Suggested fix: when a valid canonical frame exists, unresolved status must be
determined only from frame status/missing fields. Legacy unresolved should be
used only when frame is absent.

Value: directly closes the GH #51-class regression where items exist but the bot
asks for items/quantities again.

Tradeoff: legacy unresolved is ignored when it conflicts with canonical frame,
which is correct if the frame is the owner.

Confidence: high.

Classification: must-fix.

3. Medium / high-value improvement: state-resume path still has legacy-only and
history-dependent gaps.

Evidence: neutral detail-capture early return checks only
`_pending_quote_selection_from_metadata(conv) is None`, not canonical frame
presence. Sales-order unresolved resume also reads only legacy selection. Tests
for compact quote details still seed mostly legacy `pending_quote_selection`.

Suggested fix: route all quote resume checks through one canonical active-frame
helper; add canonical-only tests for compact details, sales-order follow-up, and
history-compacted resume.

Value: makes context loss/resume measurable instead of relying on last assistant
prose.

Tradeoff: small test expansion and tighter lifecycle semantics.

Confidence: medium-high.

Classification: high-value improvement.

## Eval Plan

Add regression cases for:

- canonical frame only plus compact details -> `create_quotation`;
- canonical frame plus stale legacy unresolved -> frame wins;
- quoted frame plus quote request -> no duplicate quotation;
- no frame plus noisy/partial assistant prose repair -> fail closed or explicit
  repair source.

Track `quote_frame.source/status` at quotation attempts and alert on unexpected
`assistant_prose_repair` rate.

## Residual Risks

Assistant-prose repair is still allowed when no durable frame exists. That is
acceptable as recovery, but it needs live traffic validation because unit tests
cannot prove the model will not drift into prose-owned quote summaries.

## Orchestrator Decision

- Accepted findings 1 and 2 as must-fix in this pass.
- Accepted finding 3 as high-value improvement; add helper/tests for current
  touched paths, avoid unrelated broad refactor if it risks the patch.

# Verification

- Read-only LLM architecture review completed by spawned `llm_architect`: passed.

# Risks / Follow-ups

- Accepted findings were implemented locally and verified in the stage gates.
