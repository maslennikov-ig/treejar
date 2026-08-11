---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-n7p4-judged-repairs/stage-manifest.json
stream_owner: tj-n7p4.4-root-implementation
orchestration_level: slice_acceptance
scope_kind: product_slice
immediate_consumer: tj-n7p4.5-measured-round
public_facade: apply_shipped_output_guards
bounded_acceptance: production-parity-and-paid-call-journal
non_goals:
  - frozen-twenty-paid-round
  - root-scoring-and-rewrite-reading
evidence:
  - local-twenty-case-journal-simulations
task_id: tj-n7p4.4
epic_id: tj-n7p4
stage_id: tj-n7p4-judged-repairs
session_id: tj-n7p4-judged-repairs
milestone: acceptance-harness-measures-the-production-reply
milestone_status: accepted
agent_type: n/a
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: root-owned sequential change on the shared protected round journal and response path
repo: treejar
branch: main
base_branch: main
base_commit: a1d9532
worktree: /home/me/code/treejar
write_zone:
  - scripts/corpus_bridge/real_opening_acceptance.py
  - src/llm/repair_judge.py
  - src/llm/message_processor.py
  - tests
  - .codex
success_criteria:
  - triggered-harness-reply-matches-production-finalizer
  - preflight-authorizes-fixed-repair-model
  - repair-call-journaled-before-dispatch
  - no-trigger-means-no-repair-call
  - protected-rewrite-pack-is-separate-from-blind-scoring-pack
selected_docs:
  - docs/superpowers/specs/2026-08-11-nothing-is-deleted-without-a-judge-spec.md
  - docs/plans/2026-08-11-orchestrator-prompt.md
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
  - tj-n7p4.6
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
  - data
affected_surfaces:
  - backend
invariants:
  - no-unpaid-or-unjournaled-repair-call
  - no-trigger-no-repair-call
  - protected-corpus-stays-outside-git
docs_impact: behavior
docs_reviewed: updated
docs_review_notes: stage summary and handoff record production parity authority journaling and protected reading separation
verification:
  - focused TDD red: missing repair authority and async harness contract failed collection
  - focused green: 46 harness split and repair tests passed
  - direct triggered parity: harness content and repair counts equal the production finalizer
  - local triggered round: 20 generation calls and exactly one repair call journaled
  - local no-trigger round: 20 generation calls and zero repair calls journaled
  - affected response-path regression: 879 tests passed
  - user-authorized stale-test update: three synchronous harness assertions and one old patch-point assertion now exercise the async production path
  - uv run ruff check src/ tests/ scripts/corpus_bridge/real_opening_acceptance.py: passed
  - uv run ruff format --check src/ tests/ scripts/corpus_bridge/real_opening_acceptance.py: passed over 374 files
  - uv run mypy src/: passed over 174 source files
  - uv run pytest tests/ -v --tb=short: 3594 passed and 19 skipped
  - scripts/orchestration/run_process_verification.sh: passed
changed_files:
  - .codex/handoff.md
  - .codex/stages/tj-ee5f/traceability-manifest.json
  - .codex/stages/tj-n7p4-judged-repairs/stage-manifest.json
  - .codex/stages/tj-n7p4-judged-repairs/summary.md
  - .codex/stages/tj-n7p4-judged-repairs/artifacts/tj-n7p4.4.md
  - scripts/corpus_bridge/real_opening_acceptance.py
  - src/llm/message_processor.py
  - src/llm/repair_judge.py
  - tests/test_corpus_bridge_real_opening_acceptance.py
  - tests/test_llm_grounding_classification_split.py
explicit_defers:
  - tj-n7p4.5-owns-the-authorized-paid-round-root-scoring-and-rewrite-reading
---

# Summary

The acceptance harness now resolves the reply through the same rendered flags,
PII-safe second-vendor review, reclassification and fallback notice as
production. Preflight and the protected journal explicitly cover the extra
repair calls, while no flag makes no repair call.

# Scope / Routing

The root implemented this sequentially because the frozen generator, repair
provider, per-model cap, resumable journal and reading packs form one protected
measurement boundary. The scoring reader remains root-only by default and is
still separate from the repair judge.

# Verification

The new contract first failed on missing async and authority symbols. After
implementation, a direct test matched the harness reply and counts to the
production finalizer. Two local 20-case rounds proved exactly one repair call
for one trigger and zero for no triggers, with the call recorded before
dispatch. The protected rewrite pack is separate from the blind scoring pack.
Ruff, format, Mypy, all repository tests and process verification passed.

# Delivery / Cleanup

Accepted directly in the root worktree for one local child commit. No child
branch or worktree exists. No corpus was read and no paid call, push, deploy,
live mutation, model configuration change or real-user message occurred.

# Risks / Follow-ups / Explicit Defers

`.5` owns the authorized live measured round, root blind scoring, aggregate
trigger/fallback/cost report and root reading of every protected rewrite.
