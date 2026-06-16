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
  - src/llm/fact_extractor.py
  - src/services/chat.py
  - tests/test_dialogue_order_runtime.py
  - tests/test_fact_extractor.py
  - tests/test_llm_engine.py
  - tests/test_services_chat_batch.py
  - .codex/handoff.md
  - .codex/stages/tj-order-cutover-review-fix
success_criteria:
  - accepted must-fix leaks are fixed test-first
  - accepted hardening follow-ups are implemented or explicitly bounded
  - send failures cannot make inbound batches fail after reply generation
  - customer-label names are extracted deterministically
  - target order runtime, LLM, chat batch, and fact extraction tests pass
  - deploy, production smoke, and approved synthetic E2E pass
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
cleanup_notes: current active orchestrator worktree and branch are retained for final closeout bookkeeping; no separate child worktree remains
risk_level: medium
docs_impact: behavior,dependency
docs_reviewed: no-change-needed
docs_review_notes: existing stable docs already cover runtime ownership and webhook processing; handoff/stage docs were updated with delivery evidence
verification:
  - local full gates after final runtime fix: ruff check, ruff format check, mypy, pytest tests/ -q -> 1412 passed, 19 skipped
  - GitHub Actions run 27614021694: changes, lint, test, type-check, deploy passed
  - production smoke after deploy: health OK, verify_api 8 passed / 0 failed
  - live synthetic E2E matrix 0616112830: passed
  - strict all-details synthetic quote run: passed
changed_files:
  - frontend/admin/package-lock.json
  - src/dialogue/order_state.py
  - src/dialogue/order_runtime.py
  - src/llm/engine.py
  - src/llm/fact_extractor.py
  - src/services/chat.py
  - tests/test_dialogue_order_runtime.py
  - tests/test_fact_extractor.py
  - tests/test_llm_engine.py
  - tests/test_services_chat_batch.py
  - .codex/handoff.md
  - .codex/stages/tj-order-cutover-review-fix
explicit_defers:
  - tj-order-cutover.10 full route-selection extraction remains a P2 architecture follow-up
  - GitHub #42 second-occurrence evidence comment remains externally visible and separately unauthorized
---

# Summary

Implemented and delivered the accepted order/quote review fixes, follow-up
hardening, and two production regressions found during delivery retest:

- canonical quote-frame presence blocks invalid-frame legacy fallback;
- non-answerable typed quantity frames suppress stale legacy quantity metadata;
- `legacy_migration_read` records legacy metadata consumption;
- unresolved-only exact quote repair has canonical typed runtime ownership;
- pending quantity/reference route selection is delegated to
  `_pending_reference_route_for_turn`;
- quote frames get deterministic IDs and quote side effects write bounded
  non-PII diagnostics;
- frontend admin lockfile resolves the Vite/esbuild audit findings;
- Wazzup outbound send failures no longer fail the inbound batch after the bot
  reply is generated;
- deterministic fact extraction recognizes `Customer:` labels as names.

# Verification

Fresh local gates passed after the final runtime fix: ruff check, ruff format
check, mypy, and `pytest tests/ -q` with `1412 passed, 19 skipped`. GitHub
Actions run `27614021694` passed changes/lint/test/type-check/deploy.
Production health, `verify_api.py`, the approved live E2E matrix, and the
strict all-details first-turn synthetic quote run passed after deploy.

# Delivery / Cleanup

Delivery to `main` completed. Production marker readback showed
`.release-sha=16a2dfe8de30b79a81cb53f73279c629eaa70499`. Synthetic production
test data was removed from PostgreSQL and Redis after the E2E run; exact target
conversation count was zero after cleanup. The current active orchestrator
worktree is retained only for final closeout bookkeeping.

# Risks / Follow-ups

`tj-order-cutover.10` remains open for the broader behavior-preserving
extraction of sales-order, exact-quote SKU repair, selection-confirmation, and
quote-detail-resume route families from `process_message`. The delivered branch
only includes the lower-risk pending quantity/reference extraction slice.
