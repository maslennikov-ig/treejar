---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-mshi-permission-list/stage-manifest.json
stream_owner: tj-mshi.3-root-implementation
orchestration_level: slice_acceptance
scope_kind: product_slice
immediate_consumer: tj-mshi.4-prompt-prohibition-removal
public_facade: COMMERCIAL_CAPABILITIES
bounded_acceptance: positive-commercial-permission-contract
non_goals:
  - prompt-prohibition-removal-outside-registry
  - deterministic-commitment-check
  - customer-text-repair-path
evidence:
  - none
task_id: tj-mshi.3
epic_id: tj-mshi
stage_id: tj-mshi-permission-list
session_id: tj-mshi-permission-list
milestone: positive-commercial-permission-wording
milestone_status: accepted
agent_type: n/a
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: root-owned sequential prompt-contract change
repo: treejar
branch: main
base_branch: main
base_commit: d64cec5
worktree: /home/me/code/treejar
write_zone:
  - src/llm/communication_policy.py
  - tests/test_llm_prompts.py
  - tests/test_dialogue_consultative_opening.py
  - .codex
success_criteria:
  - all-25-instructions-state-positive-permissions
  - ratified-conditions-remain-explicit
  - rendered-header-says-what-noor-may-promise
selected_docs:
  - docs/superpowers/specs/2026-08-11-what-noor-may-promise-spec.md
  - docs/plans/2026-08-11-permission-list-plan.md
  - docs/plans/2026-08-11-promise-types-for-ratification.md
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
  - tj-mshi.2-root-implementation
parallel_decision: sequential
status: accepted
delivery_method: manual integration
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: root-owned main worktree; no child worktree or branch existed
risk_level: medium
verification_tier: release
risk_tags:
  - prompt-contract-change
affected_surfaces:
  - backend
invariants:
  - positive-permission-registry
  - ratified-condition-preservation
docs_impact: behavior
docs_reviewed: updated
docs_review_notes: stage summary and handoff record the positive permission contract and owner-authorized assertion replacement
verification:
  - focused positive-permission tests failed on showroom_visit project_samples discount and the old header, then passed: 3 passed
  - uv run ruff check src/ tests/: passed
  - uv run ruff format --check src/ tests/: passed over 369 files
  - uv run mypy src/: passed over 173 source files
  - uv run pytest tests/ -v --tb=short: 3560 passed and 19 skipped
  - scripts/orchestration/run_process_verification.sh: passed
changed_files:
  - .codex/handoff.md
  - .codex/stages/tj-ee5f/traceability-manifest.json
  - .codex/stages/tj-mshi-permission-list/stage-manifest.json
  - .codex/stages/tj-mshi-permission-list/summary.md
  - .codex/stages/tj-mshi-permission-list/artifacts/tj-mshi.3.md
  - src/llm/communication_policy.py
  - tests/test_dialogue_consultative_opening.py
  - tests/test_llm_prompts.py
explicit_defers:
  - tj-mshi.4-owns-removal-of-duplicate-prompt-prohibitions
---

# Summary

All 25 commercial capability instructions now read as actions Noor may take
under the ratified condition. The three remaining negative entries were turned
around without weakening their conditions, and the rendered block is headed
`[WHAT NOOR MAY PROMISE]`.

# Scope / Routing

Root-owned sequential work on `main`. This child changed only the capability
wording and rendered header. It added no duplicate promise rule, deterministic
check, or customer-text repair path.

# Verification

The focused tests first failed on `showroom_visit`, `project_samples`,
`discount`, and the old header, then passed after the positive rewrite. The
owner-authorized discount assertion replacement now holds the
`manager_required` mode and prior-approval condition. Ruff, format, Mypy, the
complete Pytest suite, and process verification passed. The stable
`grounding-policy` traceability source was deliberately re-pinned.

# Delivery / Cleanup

Accepted directly in the root worktree for one local child commit. No child
worktree or branch existed. No paid call, push, deploy, live mutation, or
real-user message occurred.

# Risks / Follow-ups / Explicit Defers

The duplicate future-check and customer-owned-furniture prompt prohibitions
remain until `tj-mshi.4`, their declared removal boundary.
