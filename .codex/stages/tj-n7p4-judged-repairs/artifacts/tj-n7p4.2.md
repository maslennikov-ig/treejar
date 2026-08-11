---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-n7p4-judged-repairs/stage-manifest.json
stream_owner: tj-n7p4.2-root-implementation
orchestration_level: slice_acceptance
scope_kind: product_slice
immediate_consumer: tj-n7p4.3-repair-judge
public_facade: render_reply
bounded_acceptance: six-guard-declaration-matrix
non_goals:
  - repair-judge-provider-call
  - customer-visible-behavior-change
  - paid-model-call
evidence:
  - protected-60-output-replay-under-git-common-dir
task_id: tj-n7p4.2
epic_id: tj-n7p4
stage_id: tj-n7p4-judged-repairs
session_id: tj-n7p4-judged-repairs
milestone: every-guard-declares-its-customer-text-effect
milestone_status: accepted
agent_type: n/a
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: root-owned sequential change on the shared reply and replay boundary
repo: treejar
branch: main
base_branch: main
base_commit: 7248844
worktree: /home/me/code/treejar
write_zone:
  - src/llm/response_policy.py
  - src/llm/opening_guard.py
  - tests/test_llm_response_guard_declarations.py
  - .codex
success_criteria:
  - exactly-six-explained-guard-declarations
  - replacing-guards-enforce-coverage
  - removing-guards-return-original-text-and-a-flag
  - protected-60-output-replay-unchanged
  - no-existing-test-edited
selected_docs:
  - docs/superpowers/specs/2026-08-11-nothing-is-deleted-without-a-judge-spec.md
  - docs/plans/2026-08-11-orchestrator-prompt.md
selected_skills:
  - orchestrator-stage
  - superpowers-test-driven-development
  - superpowers-systematic-debugging
  - superpowers-verification-before-completion
selected_agents:
  - none
catalog_candidates:
  - none
parallel_group: n/a
depends_on_streams:
  - tj-n7p4.1
parallel_decision: sequential
status: accepted
delivery_method: manual integration
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: root-owned main worktree; no child worktree or branch exists
risk_level: high
verification_tier: release
risk_tags:
  - authorization
affected_surfaces:
  - backend
invariants:
  - customer-visible-output-unchanged
  - removing-guard-cannot-edit
  - replacement-coverage-is-executable
  - protected-corpus-stays-outside-git
docs_impact: api-contract
docs_reviewed: updated
docs_review_notes: stage summary and handoff record the six declarations, compatibility bridge, and exact replay proof
verification:
  - focused red: new test module failed to import RESPONSE_GUARD_DECLARATIONS before implementation
  - focused green: 8 declaration-contract tests passed
  - focused guard regression: 194 tests passed before the final naming refinement and 32 passed after it
  - protected full-chain replay: 60 raw and 60 rendered digests matched, zero coverage failures, baseline aggregate digest 1b0b2963480c08e466a8d44133e763a2ede3fa423d5dc4b0f2f327f383411052
  - source review: closed-question, opening, and deferred-commitment replace or add covered meaning; selling-turn and grounding-output can delete without equivalent text
  - existing tests: none edited
  - uv run ruff check src/ tests/: passed
  - uv run ruff format --check src/ tests/: passed over 371 files
  - uv run mypy src/: passed over 173 source files
  - uv run pytest tests/ -v --tb=short: 3573 passed and 19 skipped
  - scripts/orchestration/run_process_verification.sh: passed
changed_files:
  - .codex/handoff.md
  - .codex/stages/tj-ee5f/traceability-manifest.json
  - .codex/stages/tj-n7p4-judged-repairs/stage-manifest.json
  - .codex/stages/tj-n7p4-judged-repairs/summary.md
  - .codex/stages/tj-n7p4-judged-repairs/artifacts/tj-n7p4.2.md
  - src/llm/opening_guard.py
  - src/llm/response_policy.py
  - tests/test_llm_response_guard_declarations.py
explicit_defers:
  - none
---

# Summary

All six customer-text guards now have one executable declaration. Replacing
guards may change text only when their coverage proof passes. Removing guards
return the original reply and raise a `ReplyGuardFlag`; a deliberately named
legacy candidate bridge preserves `.2` output until `.3` replaces it with the
repair judge.

# Scope / Routing

Root-owned sequential implementation on `main`. Source reading corrected the
initial classification of `closed_question`: it replaces a standalone known
slot question with a localized acknowledgement and next action, so it is
replacing rather than removing. No paid call or external documentation was
needed.

# Verification

The new test was red on the missing declaration registry, then all eight
contract tests passed. A first protected replay exposed an over-strict opening
coverage proof that confused legal header movement with lost content; the proof
was moved next to the opening guard and now checks the exact non-header body.
The final replay matched all 60 stored raw and rendered digests, with zero
coverage failures and one expected `grounding_output` flag.

Ruff, format, Mypy, the complete 3,592-case Pytest collection, and process
verification passed. No existing test was edited.

# Delivery / Cleanup

The change is integrated directly in the root worktree for one local child
commit. Protected reply text stayed under `.git`; no paid call, push, deploy,
live mutation, model configuration change, or real-user message occurred.

# Risks / Follow-ups / Explicit Defers

There is no defer in this child. The legacy bridge is not debt left open: it is
the explicit behavior-preserving boundary that `.3` removes when the repair
judge starts consuming flags.
