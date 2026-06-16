---
schema_version: orchestration-artifact/v1
artifact_type: local-implementation
task_id: tj-order-cutover.5
stage_id: tj-order-adapter-hardening
agent_type: n/a
subagent_model: n/a
reasoning_effort: n/a
model_reasoning_rationale: local execution because user did not authorize spawned subagents for this follow-up
repo: treejar
branch: codex/tj-order-sideeffect-adapter
base_branch: origin/main
base_commit: 350822e86db838678551deca98234d6b925144f3
worktree: /home/me/code/treejar/.worktrees/tj-order-sideeffect-adapter
write_zone:
  - src/llm/engine.py
  - tests/test_llm_engine.py
  - .codex/handoff.md
  - .codex/stages/tj-order-cutover/summary.md
  - .codex/stages/tj-order-adapter-hardening
success_criteria:
  - deterministic order quote create_quotation calls route through one side effect adapter
  - structural regression prevents process_message direct create_quotation calls
  - local and CI gates pass
selected_docs:
  - AGENTS.md
  - .codex/orchestrator.toml
  - .codex/handoff.md
selected_skills:
  - orchestrator-stage
  - test-driven-development
  - verification-before-completion
selected_agents:
  - none
catalog_candidates:
  - none
parallel_group: local
depends_on_streams:
  - none
parallel_decision: local
status: merged
delivery_method: merge
accepted_by_orchestrator: yes
cleanup_status: blocked
cleanup_notes: current worktree retained until docs closeout commit is pushed
risk_level: medium
docs_impact: refactor
docs_reviewed: no-change-needed
docs_review_notes: internal refactor only with no customer behavior or API contract changes
verification:
  - RED structural test failed before implementation
  - targeted order quote tests passed 6 selected
  - engine runtime tests passed 327
  - ruff check passed
  - ruff format check passed
  - mypy passed
  - full pytest passed 1396 passed 19 skipped
  - CI run 27602099718 passed changes lint test type-check deploy
  - production verify_api passed 8 of 8
changed_files:
  - src/llm/engine.py
  - tests/test_llm_engine.py
  - .codex/handoff.md
  - .codex/stages/tj-order-cutover/summary.md
  - .codex/stages/tj-order-adapter-hardening/summary.md
  - .codex/stages/tj-order-adapter-hardening/artifacts/tj-order-cutover.5.md
explicit_defers:
  - tj-order-cutover.10 tracks remaining route selection extraction from process_message
---

# Summary

Delivered the order quote side-effect adapter cut for `tj-order-cutover.5`.
`process_message` no longer calls `create_quotation` directly for deterministic
order quote routes; those calls now go through `_execute_order_quote_side_effect`.

# Scope / Routing

The work stayed local in a dedicated worktree because the user authorized
push/deploy but did not authorize spawned subagents. No external docs were needed;
the behavior is repo-internal. Graphify is not configured.

# Verification

RED was observed with
`tests/test_llm_engine.py::test_order_quote_create_quotation_calls_are_adapter_owned`.
After implementation, targeted order quote tests, engine/runtime tests, ruff,
format, mypy, full pytest, GitHub Actions, deploy, and production API smoke all
passed.

# Delivery / Cleanup

Commit `8bce80194cd3640d30a8a5c25e66cc85c3eeadff` was pushed to `origin/main`
and deployed by GitHub Actions run `27602099718`, deploy job `81605605844`.
The worktree remains active until this docs closeout commit is pushed.

# Risks / Follow-ups / Explicit Defers

`tj-order-cutover.10` tracks the remaining behavior-preserving extraction of
order quote route selection from `process_message`.
