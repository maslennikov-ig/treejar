---
schema_version: orchestration-artifact/v1
artifact_type: local-implementation
task_id: tj-s1qi
stage_id: tj-order-cutover-review-fix
agent_type: n/a
subagent_model: n/a
reasoning_effort: n/a
model_reasoning_rationale: local orchestrator accepted findings and implemented fixes
repo: treejar
branch: codex/tj-order-cutover-review-fix
base_branch: origin/main
base_commit: b03227e86db838678551deca98234d6b925144f3
worktree: /home/me/code/treejar/.worktrees/tj-order-cutover-review-fix
write_zone:
  - frontend/admin/package-lock.json
  - src/dialogue/order_state.py
  - src/dialogue/order_runtime.py
  - src/llm/engine.py
  - tests/test_dialogue_order_runtime.py
  - tests/test_llm_engine.py
  - .codex/handoff.md
  - .codex/stages/tj-order-cutover-review-fix
success_criteria:
  - accepted must-fix leaks are fixed test-first
  - accepted hardening follow-ups are implemented or explicitly bounded
  - target order runtime and llm engine tests pass
  - docs-reviewed and graph-reviewed decisions recorded
selected_docs:
  - AGENTS.md
  - .codex/orchestrator.toml
  - .codex/handoff.md
  - .codex/stages/tj-order-cutover/summary.md
  - .codex/stages/tj-order-adapter-hardening/summary.md
selected_skills:
  - orchestrator-stage
  - task-router
  - code-review
  - test-driven-development
  - systematic-debugging
  - verification-before-completion
  - orchestration-closeout
selected_agents:
  - correctness_reviewer
  - improvement_reviewer
  - architect_reviewer
catalog_candidates:
  - none
parallel_group: local-fix
depends_on_streams:
  - correctness-review
  - improvement-review
  - architecture-review
parallel_decision: local
status: accepted
delivery_method: manual integration
accepted_by_orchestrator: yes
cleanup_status: blocked
cleanup_notes: local feature branch/worktree retained until approved delivery, deploy, and live E2E complete
risk_level: medium
docs_impact: behavior,dependency
docs_reviewed: no-change-needed
docs_review_notes: existing docs already state typed runtime ownership; package-lock update does not change supported Node policy
verification:
  - target pytest: 330 passed
  - ruff check: passed
  - ruff format check: passed
  - mypy: passed
  - hardening target pytest: 332 passed
  - frontend admin npm audit: 0 vulnerabilities
  - frontend admin lint/build: passed
changed_files:
  - frontend/admin/package-lock.json
  - src/dialogue/order_state.py
  - src/dialogue/order_runtime.py
  - src/llm/engine.py
  - tests/test_dialogue_order_runtime.py
  - tests/test_llm_engine.py
  - .codex/handoff.md
  - .codex/stages/tj-order-cutover-review-fix
explicit_defers:
  - tj-order-cutover.10 full route-selection extraction remains a P2 architecture follow-up
  - production delivery and live E2E are pending in the current approved delivery phase
---

# Summary

Implemented three accepted review fixes locally:

- canonical quote-frame presence now blocks invalid-frame legacy fallback;
- non-answerable typed quantity frames suppress stale legacy quantity metadata;
- `legacy_migration_read` is now set when runtime load consumes legacy metadata.

Follow-up hardening was added in the same branch after delivery approval:

- unresolved-only exact quote repair now has canonical typed frame ownership;
- the pending quantity/reference slice of route selection is delegated to
  `_pending_reference_route_for_turn`;
- quote frames get deterministic IDs and quote side effects write bounded
  non-PII diagnostics;
- frontend admin lockfile now resolves Vite/esbuild audit findings.

# Verification

Fresh target tests and local code gates passed after implementation and
formatting. Follow-up hardening target tests, ruff, mypy, npm audit, admin
lint, and admin build passed. Full stage closeout and external delivery remain
to be run after this artifact update.

# Delivery / Cleanup

The baseline review-fix commit was created locally. No push, deploy, production
mutation, or live WhatsApp E2E has been run after the follow-up hardening yet.
The worktree and local branch are retained until delivery completes.

# Risks / Follow-ups

`tj-order-cutover.10` remains open for the full behavior-preserving extraction
of sales-order, exact-quote, selection-confirmation, and quote-detail-resume
route families from `process_message`. External delivery/live E2E is the
remaining phase for the current bug hardening branch.
