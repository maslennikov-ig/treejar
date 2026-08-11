---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-t6ug-selling-turn-declarations/stage-manifest.json
stream_owner: tj-t6ug-root-implementation
orchestration_level: slice_acceptance
scope_kind: product_slice
immediate_consumer: production-reply-path
public_facade: render_reply
bounded_acceptance: one-declaration-per-selling-turn-guard
non_goals:
  - repair-judge-provider-call
  - paid-model-call
  - new-measured-round
evidence:
  - protected-60-output-replay-before-and-after
task_id: tj-t6ug
epic_id: tj-t6ug
stage_id: tj-t6ug-selling-turn-declarations
session_id: tj-t6ug-selling-turn-declarations
milestone: the-fold-is-deterministic-again-and-proves-what-it-took
milestone_status: accepted
agent_type: n/a
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: root-owned single-file change on the shared reply boundary
repo: treejar
branch: main
base_branch: main
base_commit: 1754544
worktree: /home/me/code/treejar
write_zone:
  - src/llm/response_policy.py
  - src/llm/sales_turn_guard.py
  - scripts/corpus_bridge/replay_policy_chain.py
  - tests/test_llm_response_guard_declarations.py
  - tests/test_llm_response_policy_guards.py
  - tests/test_sales_turn_guard.py
  - tests/test_corpus_bridge_replay_policy_chain.py
  - .codex
success_criteria:
  - one-declaration-per-guard
  - additive-guard-applies-without-a-flag
  - measured-fold-applies-deterministically
  - reduction-proof-is-executable
  - protected-replay-identical-before-and-after
selected_docs:
  - docs/superpowers/specs/2026-08-11-nothing-is-deleted-without-a-judge-spec.md
selected_skills:
  - orchestrator-stage
  - superpowers-test-driven-development
  - superpowers-verification-before-completion
selected_agents:
  - none
catalog_candidates:
  - none
parallel_group: n/a
depends_on_streams:
  - tj-n7p4.2
parallel_decision: sequential
status: accepted
delivery_method: manual integration
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: temporary read-only worktree at 1754544 removed after the before-and-after replay
risk_level: high
verification_tier: release
risk_tags:
  - authorization
affected_surfaces:
  - backend
invariants:
  - only-asks-are-dropped
  - reduction-proof-failure-raises-a-flag
  - additive-guard-spends-no-judge-call
  - protected-corpus-stays-outside-git
docs_impact: api-contract
docs_reviewed: updated
docs_review_notes: stage summary and handoff record the third guard mode, the reduction proof, and the replay entry point
verification:
  - focused red: the declaration test failed on question_form missing from RESPONSE_GUARD_DECLARATIONS
  - focused green: 11 declaration, 4 policy-guard, 34 sales-turn-guard, and 4 replay-script tests passed
  - behaviour reproduction: five non-first-turn shapes read by hand before and after the change
  - protected replay at 1754544 and at the fix: identical aggregate digests 68c926ed (fixture convention) and 1fc87c04 (raw)
  - uv run ruff check src/ tests/ scripts/: passed
  - uv run ruff format --check src/ tests/ scripts/: passed
  - uv run mypy src/: passed over 174 source files
  - uv run pytest tests/ -v --tb=short: 3604 passed and 19 skipped
  - scripts/orchestration/run_process_verification.sh: passed
changed_files:
  - .codex/handoff.md
  - .codex/stages/tj-t6ug-selling-turn-declarations/stage-manifest.json
  - .codex/stages/tj-t6ug-selling-turn-declarations/summary.md
  - .codex/stages/tj-t6ug-selling-turn-declarations/artifacts/tj-t6ug.md
  - scripts/corpus_bridge/replay_policy_chain.py
  - src/llm/response_policy.py
  - src/llm/sales_turn_guard.py
  - tests/test_corpus_bridge_replay_policy_chain.py
  - tests/test_llm_response_guard_declarations.py
  - tests/test_llm_response_policy_guards.py
  - tests/test_sales_turn_guard.py
explicit_defers:
  - none
---

# Summary

The three selling-turn guards are declared one at a time. `question_form` and
`name_chase` are `REDUCING` and prove at runtime that they took only the
reply's own asks; `company_question` is `REPLACING` and additive. A reply that
asks three questions is folded to one again, deterministically and free, and
an appended question no longer spends a second-vendor call.

# Scope / Routing

Root-owned. Found by auditing `tj-n7p4` rather than by a failing test, because
no test covered the selling turn through `render_reply` — which is the same
gap that let the bundle's mode ship. That coverage now exists.

# Verification

The fold and the addition were reproduced on the base commit first, so the
defect is recorded rather than asserted. The protected 60-output replay was
run at `1754544` in a temporary worktree and at the fix, and both conventions
give identical aggregate digests, so nothing stored changed. The one
`grounding_output` flag on dialog 789 appears in both and belongs to
`tj-n7p4.3`.

# Delivery / Cleanup

One local commit on `main`. The temporary worktree is removed. Protected reply
text stayed under the git common dir; the tracked side carries digests,
dialog identifiers and counts only. No paid call, push, deploy, live
mutation, model configuration change, or real-user message occurred.

# Risks / Follow-ups / Explicit Defers

No defer. The two reducing guards remain unmeasured on live multi-turn
traffic, which is a property of a first-turn frozen set and was equally true
before this change; the fix restores behaviour measured on 2026-08-09 rather
than introducing new behaviour.
