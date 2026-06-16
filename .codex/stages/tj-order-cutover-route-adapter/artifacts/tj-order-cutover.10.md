---
schema_version: orchestration-artifact/v1
artifact_type: local-implementation
task_id: tj-order-cutover.10
stage_id: tj-order-cutover-route-adapter
agent_type: n/a
subagent_model: n/a
reasoning_effort: n/a
model_reasoning_rationale: local orchestrator implementation; spawned subagents were not authorized and the route families shared one tightly coupled write zone
repo: treejar
branch: codex/tj-order-route-adapter
base_branch: origin/main
base_commit: 5283e87591589d88a06d5c8255ba82f2102acd6e
worktree: /home/me/code/treejar/.worktrees/tj-order-route-adapter
write_zone:
  - src/llm/engine.py
  - tests/test_llm_engine.py
  - .codex/handoff.md
  - .codex/stages/tj-order-cutover-route-adapter
success_criteria:
  - process_message delegates deterministic order/quote route selection to adapter
  - create_quotation remains callable only through side-effect adapter
  - sales-order quote extraction/resume regressions pass
  - exact-quote SKU repair regressions pass
  - selection confirmation regressions pass
  - bare ordinal selection after numbered SKU options remains in selection-confirmation
  - bare ordinal selection after name-gate preserves the option prompt quantity
  - quote-detail resume regressions pass
  - pending quantity/reference path remains green
  - dialogue-kernel product-selection quantity prompts persist the canonical pending quantity frame
  - short affirmative follow-up after a single stock/price option resumes quote context
  - #42/#49/#50/#51/#52 current order/quote regressions pass
selected_docs:
  - AGENTS.md
  - .codex/orchestrator.toml
  - .codex/handoff.md
  - .codex/stages/tj-order-cutover-review-fix/summary.md
selected_skills:
  - using-superpowers
  - orchestrator-stage
  - task-router
  - brainstorming
  - using-git-worktrees
  - test-driven-development
  - systematic-debugging
  - orchestration-closeout
selected_agents:
  - none - spawned subagents require explicit authorization and this work was one coupled local stream
catalog_candidates:
  - none - installed workflow skills covered the task
parallel_group: route-adapter-refactor
depends_on_streams:
  - none
parallel_decision: local
status: accepted
delivery_method: manual integration
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: no child worktree was created; active stage worktree is retained until delivery closeout
risk_level: medium
docs_impact: refactor
docs_reviewed: no-change-needed
docs_review_notes: no public behavior, API, operator workflow, deployment, integration, or stable navigation contract changed
verification:
  - structural RED test: failed before adapter extraction
  - bare ordinal RED test: failed with verified-policy-clarify before context-gated parser fix
  - bare ordinal quantity RED test: failed with quantity 1 before option-prompt quantity fallback
  - dialogue-kernel quantity-frame RED test: failed with missing order_runtime frame before kernel quantity prompt frame storage
  - single stock-option quote-resume RED tests: failed with no quote candidate and proposal-clarify fallback before stock option parsing/storage
  - bare ordinal targeted set: passed, 4 tests
  - dialogue-kernel pending quantity targeted set: passed, 9 tests
  - single stock-option quote-resume targeted set: passed, 2 tests
  - single stock-option blocker set: passed, 4 tests
  - targeted order/quote regression set: passed, 13 tests
  - engine/runtime regression set: passed, 339 tests
  - ruff check src/ tests/: passed
  - ruff format --check src/ tests/: passed
  - mypy src/: passed
  - pytest tests/ -q: passed, 1418 passed and 19 skipped after single stock-option quote-resume fix
  - run_stage_closeout.py --stage tj-order-cutover-route-adapter: passed after adapter extraction, bare ordinal fix, quantity preservation fix, dialogue-kernel quantity-frame fix, and single stock-option quote-resume fix
changed_files:
  - src/llm/engine.py
  - tests/test_llm_engine.py
  - .codex/handoff.md
  - .codex/stages/tj-order-cutover-route-adapter/summary.md
  - .codex/stages/tj-order-cutover-route-adapter/artifacts/tj-order-cutover.10.md
explicit_defers:
  - none for tj-order-cutover.10 acceptance
---

# Summary

Implemented the P2 route adapter extraction for `tj-order-cutover.10`.
`process_message` now delegates remaining deterministic order/quote routing to
`_order_quote_route_for_turn`; the direct route-family calls are covered by a
structural regression test. `create_quotation` remains directly called only by
`_execute_order_quote_side_effect`.

First production E2E on `ab865b3` found one selection-confirmation regression:
bare `2` after numbered SKU options fell through to `verified-policy-clarify`.
The follow-up fix accepts a bare ordinal only when the last assistant message
contains numbered SKU options, preserving quantity clarification behavior.

Second production E2E on `32baf76` found the follow-up quantity gap: after
name-gate, bare `2` selected option 2 but defaulted quantity to 1 because the
previous user turn was just the customer's name. The final local fix preserves
the quantity from the last option prompt, such as "for your 2 chairs".

Third production E2E on `8fb39cb` found a pending quantity/reference gap when
the initial quantity prompt came from `dialogue-kernel|product_selection`.
Production conversation `b228ac0e-ecbd-4d12-9a1f-671286733bba` stored no
`order_runtime.pending_question_frame`, so the follow-up `2` fell through to
`verified-policy-clarify`. The final local fix stores a canonical order-runtime
quantity frame before returning the kernel product-selection quantity prompt.

Fourth production E2E on `4d68f78` found a short follow-up gap after a single
stock/price option. Production conversation
`c6d21cfe-6492-46d4-928b-ca33ee0d9fc4` returned
`z-ai/glm-5|stock-price-options`, but `Yes prepare the quotation` fell through
to `z-ai/glm-5|proposal-clarify` because no pending quote selection was stored
from the assistant's single-option stock/price prose. The final local fix parses
that single-option offer and stores pending quote context only when the assistant
explicitly offers to prepare/send a quote.

# Scope / Routing

The stream was local because the acceptance touched one coupled route-selection
region in `src/llm/engine.py`. No external dependency documentation lookup was
needed; this was a repo-local behavior-preserving refactor. Graphify is not
configured.

# Verification

Local verification passed for structural ownership, targeted order/quote
regressions, bare ordinal selection confirmation, dialogue-kernel pending
quantity frame storage, full engine/runtime tests, and the full repo pytest
suite. The first full pytest attempt exposed missing
frontend `node_modules` in the fresh worktree; `npm ci` restored dependencies and
the final post-dialogue-kernel-quantity-frame-fix full suite passed.

# Delivery / Cleanup

Local implementation accepted by orchestrator and stage closeout passed.
Initial delivery reached production, but live E2E found the bare ordinal gap.
Second delivery reached production, but live E2E found the quantity-preservation
gap. Third delivery reached production, but live E2E found the dialogue-kernel
pending quantity frame gap. Fourth delivery reached production, but live E2E
found the single stock-option short follow-up gap. Fifth delivery commit
`ec8dd61` reached production via CI run `27622142673`; production marker matched
`ec8dd612dfb0a44eb41104bd198a5936f91c847d`, health and `verify_api.py` passed,
and the final live order/quote E2E matrix passed.

Final live E2E run `20260616134948` covered:

- name-gate resume, selected option `2`, and preserved quantity 2;
- exact-quote SKU repair followed by quote-detail resume, quotation `Fr3415`;
- SKU variant all-details quote, quotation `Fr3416`;
- all-details first turn, quotation `Fr3417`;
- dialogue-kernel pending quantity/reference resume, `CH 140 black` quantity 2;
- short follow-up after long stock/price context, route `quote-resume`,
  quotation `Fr3418`.

Scoped production cleanup completed after E2E. PostgreSQL deleted 22 synthetic
conversations, 92 messages, 46 outbound audits, 119 customer facts, 22 order
memories, 22 customer profiles, and 1 escalation for phones matching
`%tj-route-adapter%` or `+70016416123436`; Redis deleted 37 scoped keys. A
post-cleanup check returned 0 matching conversations, profiles, joined messages,
and Redis keys.

# Risks / Follow-ups / Explicit Defers

No in-scope defers remain for `tj-order-cutover.10`. The #42 second-occurrence
GitHub evidence comment remains externally visible and was not updated.
