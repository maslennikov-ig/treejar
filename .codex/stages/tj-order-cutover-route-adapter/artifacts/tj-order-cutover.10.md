---
schema_version: orchestration-artifact/v1
artifact_type: local-implementation
task_id: tj-order-cutover.10
stage_id: tj-order-cutover-route-adapter
agent_type: n/a
subagent_model: n/a
reasoning_effort: n/a
model_reasoning_rationale: local orchestrator implementation; spawned subagents were not authorized and the route families shared one tightly coupled write zone
repo: treejar
branch: codex/tj-order-route-adapter
base_branch: origin/main
base_commit: 5283e87591589d88a06d5c8255ba82f2102acd6e
worktree: /home/me/code/treejar/.worktrees/tj-order-route-adapter
write_zone:
  - src/llm/engine.py
  - tests/test_llm_engine.py
  - .codex/handoff.md
  - .codex/stages/tj-order-cutover-route-adapter
success_criteria:
  - process_message delegates deterministic order/quote route selection to adapter
  - create_quotation remains callable only through side-effect adapter
  - sales-order quote extraction/resume regressions pass
  - exact-quote SKU repair regressions pass
  - selection confirmation regressions pass
  - quote-detail resume regressions pass
  - pending quantity/reference path remains green
  - #42/#49/#50/#51/#52 current order/quote regressions pass
selected_docs:
  - AGENTS.md
  - .codex/orchestrator.toml
  - .codex/handoff.md
  - .codex/stages/tj-order-cutover-review-fix/summary.md
selected_skills:
  - using-superpowers
  - orchestrator-stage
  - task-router
  - brainstorming
  - using-git-worktrees
  - test-driven-development
  - systematic-debugging
  - orchestration-closeout
selected_agents:
  - none - spawned subagents require explicit authorization and this work was one coupled local stream
catalog_candidates:
  - none - installed workflow skills covered the task
parallel_group: route-adapter-refactor
depends_on_streams:
  - none
parallel_decision: local
status: accepted
delivery_method: manual integration
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: no child worktree was created; active stage worktree is retained until delivery closeout
risk_level: medium
docs_impact: refactor
docs_reviewed: no-change-needed
docs_review_notes: no public behavior, API, operator workflow, deployment, integration, or stable navigation contract changed
verification:
  - structural RED test: failed before adapter extraction
  - targeted order/quote regression set: passed, 13 tests
  - engine/runtime regression set: passed, 339 tests
  - ruff check src/ tests/: passed
  - ruff format --check src/ tests/: passed
  - mypy src/: passed
  - pytest tests/ -q: passed, 1413 passed and 19 skipped after npm ci restored frontend dependencies
  - run_stage_closeout.py --stage tj-order-cutover-route-adapter: passed
changed_files:
  - src/llm/engine.py
  - tests/test_llm_engine.py
  - .codex/handoff.md
  - .codex/stages/tj-order-cutover-route-adapter/summary.md
  - .codex/stages/tj-order-cutover-route-adapter/artifacts/tj-order-cutover.10.md
explicit_defers:
  - none for tj-order-cutover.10 acceptance
---

# Summary

Implemented the P2 route adapter extraction for `tj-order-cutover.10`.
`process_message` now delegates remaining deterministic order/quote routing to
`_order_quote_route_for_turn`; the direct route-family calls are covered by a
structural regression test. `create_quotation` remains directly called only by
`_execute_order_quote_side_effect`.

# Scope / Routing

The stream was local because the acceptance touched one coupled route-selection
region in `src/llm/engine.py`. No external dependency documentation lookup was
needed; this was a repo-local behavior-preserving refactor. Graphify is not
configured.

# Verification

Local verification passed for structural ownership, targeted order/quote
regressions, full engine/runtime tests, and the full repo pytest suite. The
first full pytest attempt exposed missing frontend `node_modules` in the fresh
worktree; `npm ci` restored dependencies and the final full suite passed.

# Delivery / Cleanup

Local implementation accepted by orchestrator and stage closeout passed.
Delivery is pending commit, direct push to `main`, CI/deploy monitoring,
production marker/smoke, live order/quote E2E, and synthetic production data
cleanup.

# Risks / Follow-ups / Explicit Defers

No in-scope defers remain for `tj-order-cutover.10`. The #42 second-occurrence
GitHub evidence comment remains externally visible and was not updated.
