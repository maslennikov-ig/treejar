---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-rt7w-verification-fixes/stage-manifest.json
stream_owner: tj-rt7w.12-root-implementation
orchestration_level: slice_acceptance
scope_kind: product_slice
immediate_consumer: tj-rt7w-real-split
public_facade: n/a
bounded_acceptance: one-module-owns-currency
non_goals:
  - process-message-impl-split
  - deterministic-route-retirement
evidence:
  - none
task_id: tj-rt7w.12
epic_id: tj-rt7w
stage_id: tj-rt7w-verification-fixes
session_id: tj-rt7w-verification-fixes
milestone: overcomplication-verification-fixes
milestone_status: accepted
agent_type: n/a
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: root-owned sequential work; repo contract disallows inline subagents
repo: treejar
branch: main
base_branch: main
base_commit: dce7442
worktree: /home/me/code/treejar
write_zone:
  - src
  - tests
  - scripts
  - docs
  - .codex
success_criteria:
  - patterns-byte-identical
  - no-currency-regex-outside-money
  - no-existing-test-edited
selected_docs:
  - docs/superpowers/specs/2026-08-11-what-grew-too-big-and-how-we-cut-it-back-spec.md
selected_skills:
  - orchestrator-stage
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
cleanup_notes: root-owned main worktree; no dedicated worktree or branch existed
risk_level: medium
verification_tier: release
risk_tags:
  - none
affected_surfaces:
  - backend
invariants:
  - test-matrix
docs_impact: none
docs_reviewed: updated
docs_review_notes: money.py documents why four vocabularies remain distinct
verification:
  - uv run ruff check src/ tests/ scripts/: passed
  - uv run ruff format --check src/ tests/ scripts/: passed
  - uv run mypy src/: passed over 173 source files
  - uv run pytest tests/ -q --tb=line: 3554 passed and 19 skipped
  - scripts/orchestration/run_process_verification.sh: passed
changed_files:
  - src/llm/money.py
  - src/llm/engine.py
  - src/llm/response_adapter.py
  - tests/test_llm_money.py
explicit_defers:
  - tj-rt7w.10-the-genuine-split-remains-open
  - tj-rt7w.7-remains-open-and-blocked-on-tj-rt7w.10
---

# Summary

`tj-rt7w.3` left two currency patterns behind: the SKU suffix in
`engine.py`, the only one that knows `د.إ`, and the price signal in
`response_adapter.py`. Both move, spelled exactly as they were. The four
vocabularies still differ on purpose; living in four files was the defect.

# Scope / Routing

Pure move. Widening any vocabulary would be a behaviour change and is not done here.

# Verification

Compiled patterns and flags compared byte-for-byte before and after. A new
AST test rejects `re.compile` with a currency literal anywhere in
`src/llm/` but `money.py`; a line-wise draft missed the two-line pattern it
was written for. One exception is named: a units list that knows `usd`.

Ruff, format, Mypy, the complete Pytest suite and process verification passed.
No existing test was edited.

# Delivery / Cleanup

Accepted in the root worktree as commit `8a80c1f` on `main`. No paid model
call, push, PR, deployment, production mutation, or real-user message occurred.

# Risks / Follow-ups / Explicit Defers

`tj-rt7w.10` is open with its plan in the Bead notes. `tj-rt7w.7` is blocked on
it. `tj-rt7w.14` records the missing semantic half of R2.
