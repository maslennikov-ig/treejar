---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-tjgx-opening-quality/stage-manifest.json
stream_owner: tj-tjgx-root-implementation
orchestration_level: slice_acceptance
scope_kind: product_slice
immediate_consumer: Treejar first-turn reply generation
public_facade: existing message-processing and response-policy path
bounded_acceptance: four measured opening defects from tj-399z
non_goals:
  - no rubric, applicability-map, model, price-anchor or retrieval change
  - no paid measured round or second reader
  - no deploy or production mutation
evidence:
  - none
task_id: tj-tjgx
epic_id: n/a
stage_id: tj-tjgx-opening-quality
session_id: tj-tjgx
milestone: four-measured-opening-defects
milestone_status: accepted
agent_type: n/a
subagent_model: n/a
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: root owns the product contract, implementation and acceptance
repo: treejar
branch: codex/opening-quality-tj399z
base_branch: main
base_commit: 1c2035633aaad846aca7f027ba0c2ca17519f15e
worktree: /home/me/code/treejar
write_zone:
  - src/dialogue
  - src/llm
  - tests
  - .codex/orchestrator.toml
  - .codex/goals/tj-tjgx
  - .codex/handoff.md
  - .codex/stages/tj-tjgx-opening-quality
  - .codex/stages/tj-ee5f/traceability-manifest.json
success_criteria:
  - discovery is work-led, not product-led
  - the canonical offer is stated once
  - all stated needs are acknowledged or left explicitly unconfirmed
  - at most one equivalent name question remains
  - replay and repository gates pass without re-baselining
selected_docs:
  - AGENTS.md
  - .codex/orchestrator.toml
  - .codex/handoff.md
  - docs/root-reading-convention.md
selected_skills:
  - orchestrator-stage
  - systematic-debugging
  - test-driven-development
selected_agents:
  - none
catalog_candidates:
  - none
parallel_group: n/a
depends_on_streams:
  - none
parallel_decision: local
status: accepted
delivery_method: merge
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: no delegated worktree existed; the task branch is removed after fast-forward delivery
risk_level: medium
verification_tier: release
risk_tags:
  - user-flow
affected_surfaces:
  - backend
  - user-flow
invariants:
  - test-matrix
docs_impact: behavior
docs_reviewed: updated
docs_review_notes: The handoff records the accepted response contract and unchanged production boundary.
verification:
  - focused TDD: four intended failures, then 85 passed
  - related response-policy slice: 1015 passed
  - protected replay: current 1b425bd1 against frozen 1fc87c04 with the same 7 expected differences
  - uv run ruff check src/ tests/: passed
  - uv run ruff format --check src/ tests/: passed
  - uv run mypy src/: passed
  - uv run pytest tests/ -v --tb=short: passed (3803 passed, 20 skipped)
  - scripts/orchestration/run_process_verification.sh: passed
  - run_stage_closeout release_commands: passed
changed_files:
  - .codex/goals/tj-tjgx/scope-criterion-snapshot.json
  - .codex/orchestrator.toml
  - .codex/handoff.md
  - .codex/stages/tj-ee5f/traceability-manifest.json
  - .codex/stages/tj-tjgx-opening-quality/stage-manifest.json
  - .codex/stages/tj-tjgx-opening-quality/summary.md
  - .codex/stages/tj-tjgx-opening-quality/artifacts/tj-tjgx.md
  - src/dialogue/claim_contract.py
  - src/llm/closed_question_guard.py
  - tests/test_closed_question_guard.py
  - tests/test_dialogue_consultative_opening.py
  - tests/test_llm_response_guard_declarations.py
explicit_defers:
  - none
---

# Summary

The four opening defects measured in `tj-399z` are fixed and accepted.

# Scope / Routing

Root-owned local product fix. No delegation, paid call, second reader, deploy or
production mutation.

# Verification

Focused TDD captured all four shapes. Release gates passed with 3803 tests and
20 skips, and the protected replay retained its current digest and exact seven
expected differences.

# Delivery / Cleanup

Accepted by the root orchestrator. Fast-forward delivery to `main` follows this
record; no deploy or production mutation is included.

# Risks / Follow-ups / Explicit Defers

The code contract is proved locally. A future measured round would be product
evidence, not a condition of this implementation closeout.
