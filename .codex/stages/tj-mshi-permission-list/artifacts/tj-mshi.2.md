---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-mshi-permission-list/stage-manifest.json
stream_owner: tj-mshi.2-root-implementation
orchestration_level: slice_acceptance
scope_kind: product_slice
immediate_consumer: tj-mshi.3-positive-permission-wording
public_facade: COMMERCIAL_CAPABILITIES
bounded_acceptance: exact-ratified-registry-coverage
non_goals:
  - positive-rewrite-of-existing-instructions
  - prompt-prohibition-removal
  - deterministic-commitment-check
evidence:
  - none
task_id: tj-mshi.2
epic_id: tj-mshi
stage_id: tj-mshi-permission-list
session_id: tj-mshi-permission-list
milestone: ratified-commercial-capability-registry
milestone_status: accepted
agent_type: n/a
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: root-owned sequential registry contract change
repo: treejar
branch: main
base_branch: main
base_commit: ee34629
worktree: /home/me/code/treejar
write_zone:
  - src/llm/communication_policy.py
  - tests/test_llm_prompts.py
  - .codex
success_criteria:
  - exactly-22-ratified-promises-and-3-redirects
  - every-entry-has-ratified-mode-and-source
  - one-registry-only
selected_docs:
  - docs/superpowers/specs/2026-08-11-what-noor-may-promise-spec.md
  - docs/plans/2026-08-11-permission-list-plan.md
  - docs/plans/2026-08-11-promise-types-for-ratification.md
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
cleanup_notes: root-owned main worktree; no child worktree or branch existed
risk_level: medium
verification_tier: release
risk_tags:
  - none
affected_surfaces:
  - backend
invariants:
  - test-matrix
docs_impact: behavior
docs_reviewed: updated
docs_review_notes: stage summary and handoff record the ratified registry expansion and the declared test update
verification:
  - focused registry test red on the old 8 entries, then green on 25: passed
  - uv run ruff check src/ tests/: passed
  - uv run ruff format --check src/ tests/: passed
  - uv run mypy src/: passed over 173 source files
  - uv run pytest tests/ -v --tb=short: 3559 passed and 19 skipped
  - scripts/orchestration/run_process_verification.sh: passed
changed_files:
  - .codex/goals/tj-mshi/scope-criterion-snapshot.json
  - .codex/handoff.md
  - .codex/orchestrator.toml
  - .codex/stages/tj-ee5f/traceability-manifest.json
  - .codex/stages/tj-mshi-permission-list/stage-manifest.json
  - .codex/stages/tj-mshi-permission-list/summary.md
  - .codex/stages/tj-mshi-permission-list/artifacts/tj-mshi.2.md
  - src/llm/communication_policy.py
  - tests/test_llm_prompts.py
explicit_defers:
  - tj-mshi.3-owns-positive-wording-for-all-existing-instructions
---

# Summary

`COMMERCIAL_CAPABILITIES` now contains exactly the 22 owner-ratified promises
and three permitted redirects. The broad `exceptional_terms` bucket is replaced
by the six separately ratified manager commitments. `not_offered` is a first-
class mode. The owner explicitly authorized expanding the existing exact-set
test from eight entries to 25; this is a declared contract expansion.

# Scope / Routing

Root-owned sequential work on `main`. No second registry, compatibility shim,
deterministic commitment check, or customer-text repair path was added.

# Verification

The exact-set test failed against the old eight-entry registry and passed after
the ratified expansion. Ruff, format, Mypy, the complete Pytest suite, and
process verification passed. The stable `grounding-policy` traceability source
was deliberately re-pinned after its registry content changed.

# Delivery / Cleanup

Accepted directly in the root worktree for one local child commit. No child
worktree or branch existed. No push, deploy, live mutation, or real-user message
occurred.

# Risks / Follow-ups / Explicit Defers

The existing negative instruction wording remains visible until `tj-mshi.3`,
which owns the positive rewrite and rendered-header change.
