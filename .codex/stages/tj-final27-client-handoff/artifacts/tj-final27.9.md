---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-final27-client-handoff/stage-manifest.json
stream_owner: tj-final27-client-handoff-root
orchestration_level: release
scope_kind: product_slice
immediate_consumer: client final-acceptance decision
public_facade: Noor opening reply and final client handoff pack
bounded_acceptance: remaining client-handoff code, measurement, controlled E2E, and delivery
non_goals:
  - no rubric, applicability-map, model, prompt, or retrieval-evidence change
  - no protected replay re-baseline
  - no second reader or tj-jlx4 work
evidence:
  - none
task_id: tj-final27.9
epic_id: tj-final27
stage_id: tj-final27-client-handoff
session_id: tj-final27
milestone: client-handoff-code-measurement-e2e-delivery
milestone_status: replan-required
agent_type: n/a
subagent_model: n/a
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: root owns implementation, blind reading, acceptance, and delivery
repo: treejar
branch: main
base_branch: main
base_commit: 40357200c052d14c84c2c282cc6625457ae2122b
worktree: /home/me/code/treejar
write_zone:
  - src/llm
  - scripts/corpus_bridge
  - tests
  - docs/client
  - .codex
success_criteria:
  - pinned English anchor is exactly AED 139 / AED 58 and preflight is 19 priced / 1 withheld
  - low-stock quoted rows are disclosed and realistic openings carry a verified row with at most one question
  - referral exclusion is explicit and final pack states measurement reach plainly
  - blind openings-20 round is paired per rule against tj-399z without a second reader
  - protected raw replay and release gates stay fixed
  - controlled E2E leaves no pending synthetic conversations and production health reports the delivered SHA
selected_docs:
  - AGENTS.md
  - .codex/orchestrator.toml
  - .codex/handoff.md
  - docs/root-reading-convention.md
  - docs/plans/2026-04-27-final-delivery-completion.md
selected_skills:
  - orchestrator-stage
  - technical-premortem
  - systematic-debugging
  - test-driven-development
  - orchestration-closeout
selected_agents:
  - none
catalog_candidates:
  - none
parallel_group: n/a
depends_on_streams:
  - none
parallel_decision: local
status: blocked
delivery_method: manual integration
accepted_by_orchestrator: no
cleanup_status: not_applicable
cleanup_notes: root used the authorized main worktree; no delegated workspace exists
risk_level: high
verification_tier: release
risk_tags:
  - state-transition
  - user-flow
  - rollback
affected_surfaces:
  - backend
  - user-flow
invariants:
  - state-transition
  - rollback
  - test-matrix
docs_impact: behavior
docs_reviewed: updated
docs_review_notes: handoff, client pack, reading convention, and stage evidence record behavior and measurement
verification:
  - pinned catalog anchor AED 139 / AED 58 and preflight 19 / 1: passed
  - focused anchor guard and harness tests 119 passed: passed
  - repeated R04 and R02 deterministic verified rows: passed
  - blind root reading and pairing against tj-399z: passed with one critical language defect recorded
  - protected raw replay current 1b425bd1 versus frozen 1fc87c04 with seven expected differences: passed
  - uv run ruff check src/ tests/: passed
  - uv run ruff format --check src/ tests/: passed
  - uv run mypy src/: passed
  - uv run pytest tests/ -v --tb=short: passed 3821 passed 20 skipped
  - scripts/orchestration/run_process_verification.sh: passed
  - run_stage_closeout corpus bridge acceptance: passed 71 passed 1 skipped
  - post-deploy controlled E2E and release SHA readback: pending
changed_files:
  - .beads/issues.jsonl
  - .codex/goals/tj-final27/scope-criterion-snapshot.json
  - .codex/handoff.md
  - .codex/orchestrator.toml
  - .codex/stages/tj-ee5f/traceability-manifest.json
  - .codex/stages/tj-final27-client-handoff/stage-manifest.json
  - .codex/stages/tj-final27-client-handoff/summary.md
  - .codex/stages/tj-final27-client-handoff/artifacts/tj-final27.9.md
  - docs/client/final-acceptance-pack-2026-04-29.md
  - docs/root-reading-convention.md
  - scripts/corpus_bridge/real_opening_acceptance.py
  - src/llm/catalog_planning.py
  - src/llm/deterministic_routes.py
  - src/llm/engine.py
  - src/llm/message_processor.py
  - src/llm/opening_guard.py
  - src/llm/order_quote_routes.py
  - src/llm/response_policy.py
  - src/llm/sales_turn_guard.py
  - tests/test_corpus_bridge_real_opening_acceptance.py
  - tests/test_llm_catalog_anchor_line.py
  - tests/test_llm_company_activity_cooldown.py
  - tests/test_llm_engine.py
  - tests/test_llm_response_guard_declarations.py
  - tests/test_llm_response_policy_guards.py
  - tests/test_opening_guard.py
explicit_defers:
  - tj-08ve requires a deterministic language guard and fresh measured-round authority
---

# Summary

The requested anchor, low-stock disclosure, realistic-opening route, referral
exclusion, final pack, blind measured round and local release gates are complete.
The stage is not accepted because the round found one new critical language
failure on dialog 293, tracked as P1 `tj-08ve`.

# Scope / Routing

Root-owned sequential delivery in the main worktree. No delegation, no second
reader, and no external documentation boundary. The anchor family, non-furniture
withholding and Arabic separator rules are unchanged.

# Verification

The pinned line is `Chairs from AED 139, desks and workstations from AED 58.`;
preflight is 19 priced / 1 withheld. Full pytest is 3821 passed, 20 skipped,
zero failed. Raw replay is unchanged. The measured-round detail, paid cost and
defect movement are recorded in the handoff and client pack.

# Delivery / Cleanup

Production delivery and post-deploy readback are pending. No delegated branch or
worktree exists to clean.

# Risks / Follow-ups / Explicit Defers

`tj-08ve` blocks formal acceptance. The authorized 20 generation calls are
exhausted, so its confirming paired round needs fresh owner authority. No
protected message or reply body is included in tracked evidence.
