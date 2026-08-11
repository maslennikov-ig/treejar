---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-rt7w-overcomplication/stage-manifest.json
stream_owner: tj-rt7w.5-root-implementation
orchestration_level: slice_acceptance
scope_kind: product_slice
immediate_consumer: message-orchestration-stage
public_facade: src.llm.response_policy.render_reply
bounded_acceptance: single-render-exit-proof
non_goals:
  - process-message-split
  - deterministic-route-retirement
evidence:
  - none
task_id: tj-rt7w.5
epic_id: tj-rt7w
stage_id: tj-rt7w-overcomplication
session_id: tj-rt7w-overcomplication
milestone: one-response-policy-exit
milestone_status: accepted
agent_type: n/a
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: root-owned sequential behavior change
repo: treejar
branch: main
base_branch: main
base_commit: 7c6427b
worktree: /home/me/code/treejar
write_zone:
  - src
  - tests
  - .codex
success_criteria:
  - one-render-reply-policy-for-every-exit
  - provenance-does-not-select-policy
  - new-exit-bypass-test
  - every-stored-output-change-read-and-explained
selected_docs:
  - docs/superpowers/specs/2026-08-11-what-grew-too-big-and-how-we-cut-it-back-spec.md
selected_skills:
  - orchestrator-stage
  - superpowers-test-driven-development
  - superpowers-systematic-debugging
selected_agents:
  - none
catalog_candidates:
  - none
parallel_group: n/a
depends_on_streams:
  - tj-rt7w.4
parallel_decision: sequential
status: accepted
delivery_method: manual integration
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: root-owned main worktree; no dedicated worktree or branch existed
risk_level: high
verification_tier: release
risk_tags:
  - behavior-change
affected_surfaces:
  - backend
invariants:
  - test-matrix
  - customer-reply-grounding
docs_impact: behavior
docs_reviewed: updated
docs_review_notes: stage summary names both stored-output changes and their causes
verification:
  - focused single-exit and provenance tests: 6 passed
  - focused engine tests: 819 passed
  - protected replay: 20 checked; the existing full chain changed 0 outputs
  - protected replay: each formerly short chain changed only dialog_id 789 and 819
  - root read the complete old and new replies for dialog_id 789 and 819
  - dialog_id 789 changed only because grounding removed an unsupported service offer
  - dialog_id 819 changed only because full-chain convergence added the owner-approved deferred commitment; grounding stayed unchanged
  - uv run ruff check src/ tests/: passed
  - uv run ruff format --check src/ tests/: passed over 363 files
  - uv run mypy src/: passed over 170 source files
  - uv run pytest tests/ -q --tb=short: 3546 passed and 19 skipped
  - scripts/orchestration/run_process_verification.sh: passed
changed_files:
  - .codex/stages/tj-rt7w-overcomplication/artifacts/tj-rt7w.5.md
  - .codex/stages/tj-rt7w-overcomplication/stage-manifest.json
  - .codex/stages/tj-rt7w-overcomplication/summary.md
  - src/llm/engine.py
  - src/llm/order_quote_routes.py
  - src/llm/response_policy.py
  - tests/test_llm_reply_exit.py
  - tests/test_llm_reply_rendering.py
explicit_defers:
  - process-message-split-belongs-to-tj-rt7w.6
  - tj-rt7w.7-remains-open-and-unstarted
---

# Summary

`render_reply()` now applies the same closed-question, premature quote-detail,
opening, selling-turn, deferred-commitment, grounding, and disclosure policy to
every reply. Provenance is returned as metadata and never selects policy steps.
All transport responses are built from a `RenderedReply`; an AST regression
test rejects a direct `LLMResponse` exit inside `process_message`.

# Scope / Routing

Root-owned sequential work on `main`. Verified catalog and inventory facts are
now carried explicitly into rendering so the newly universal grounding step
does not mistake verified deterministic facts for unsupported ones. The
no-evidence quantity prompt no longer promises a future inventory check.

# Verification

The existing full chain reproduced all twenty protected raw outputs exactly.
Each of the three previously short chains changed only `dialog_id=789` and
`dialog_id=819`. Root read both complete before/after replies. The first lost
the unsupported customer-owned-furniture service offer at grounding. The second
gained the owner-approved commitment to resolve a stated assembly deferral;
grounding itself left that reply unchanged. No other stored output moved.

# Delivery / Cleanup

Accepted directly in the root worktree for one local behavior-change commit.
No paid model call, push, deployment, production mutation, or real-user message
occurred.

# Risks / Follow-ups / Explicit Defers

The one local state adapter remains inside `process_message` until the settled
split in `tj-rt7w.6`. `tj-rt7w.7` remains open and unstarted.
