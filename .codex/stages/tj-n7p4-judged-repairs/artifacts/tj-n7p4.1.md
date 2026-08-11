---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-n7p4-judged-repairs/stage-manifest.json
stream_owner: tj-n7p4.1-root-implementation
orchestration_level: slice_acceptance
scope_kind: product_slice
immediate_consumer: tj-n7p4.2-guard-declarations
public_facade: render_reply
bounded_acceptance: pure-classification-named-repair-split
non_goals:
  - model-judge-call
  - guard-declaration-change
  - customer-visible-behavior-change
evidence:
  - protected-60-output-replay-under-git-common-dir
task_id: tj-n7p4.1
epic_id: tj-n7p4
stage_id: tj-n7p4-judged-repairs
session_id: tj-n7p4-judged-repairs
milestone: classifier-no-longer-selects-repair
milestone_status: accepted
agent_type: n/a
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: root-owned sequential change on the single reply path
repo: treejar
branch: main
base_branch: main
base_commit: bfb8dcb
worktree: /home/me/code/treejar
write_zone:
  - src/llm/grounding_output.py
  - src/llm/response_policy.py
  - scripts/corpus_bridge/real_opening_acceptance.py
  - tests/test_llm_grounding_classification_split.py
  - .codex
success_criteria:
  - pure-classifier-called-by-production-and-harness
  - one-named-deterministic-repair-function
  - legacy-enforcement-name-is-an-alias
  - protected-60-output-replay-unchanged
  - unrelated-guard-sources-byte-identical
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
  - none
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
  - classifier-is-pure
  - customer-visible-output-unchanged
  - protected-corpus-stays-outside-git
docs_impact: structural
docs_reviewed: updated
docs_review_notes: stage summary and handoff record the explicit classification-to-repair boundary and replay proof
verification:
  - focused red: new test module failed to import repair_grounding_output before implementation
  - focused green: 133 passed across split, grounding-output, and acceptance-harness tests
  - protected full-chain replay: 60 checked, 0 raw or rendered mismatches, baseline aggregate digest 1b0b2963480c08e466a8d44133e763a2ede3fa423d5dc4b0f2f327f383411052
  - unrelated guard source hashes: closed-question bf6b7335..., opening 09e8d90f..., sales-turn 979eba1b... unchanged from base
  - uv run ruff check src/ tests/: passed
  - uv run ruff format --check src/ tests/: passed over 370 files
  - uv run mypy src/: passed over 173 source files
  - uv run pytest tests/ -v --tb=short: 3565 passed and 19 skipped
  - scripts/orchestration/run_process_verification.sh: passed
changed_files:
  - .codex/handoff.md
  - .codex/stages/tj-ee5f/traceability-manifest.json
  - .codex/stages/tj-n7p4-judged-repairs/stage-manifest.json
  - .codex/stages/tj-n7p4-judged-repairs/summary.md
  - .codex/stages/tj-n7p4-judged-repairs/artifacts/tj-n7p4.1.md
  - scripts/corpus_bridge/real_opening_acceptance.py
  - src/llm/grounding_output.py
  - src/llm/response_policy.py
  - tests/test_llm_grounding_classification_split.py
explicit_defers:
  - none
---

# Summary

`classify_grounding_output` is now the explicit pure decision used by both
production and the acceptance harness. Both pass its flags to the one named
`repair_grounding_output` function. `enforce_grounding_output` remains the same
function object as a compatibility alias, so existing consumers keep their
behavior without a second repair implementation.

# Scope / Routing

Root-owned sequential implementation on `main`. This child only separates
classification from repair; it does not add a model call, change a guard's
declaration, or change customer-visible behavior. The new test file was added
without editing any existing test.

# Verification

The focused test was red before `repair_grounding_output` existed, then all 133
focused tests passed. The root initially reconstructed one replay state with
an empty evidence set instead of `None`; the mismatch disappeared when the
stored semantics were restored exactly. The exact full-chain replay then
matched all 60 raw and rendered digests with aggregate `1b0b2963…`.

Ruff, format, Mypy, the complete Pytest suite, artifact validation, stage
sizing, traceability checks, and process verification passed.

# Delivery / Cleanup

The change is integrated directly in the root worktree for one local child
commit. Protected reply text stayed under `.git`; no paid call, push, deploy,
live mutation, model configuration change, or real-user message occurred.

# Risks / Follow-ups / Explicit Defers

There is no defer in this child. `.2` owns the six guard declarations; `.3`
owns the model judge. The old enforcement name is intentionally an identity
alias, not a second path.
