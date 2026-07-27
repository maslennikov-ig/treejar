---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-15m/stage-manifest.json
stream_owner: latency-stage-owner
orchestration_level: release
scope_kind: product_slice
immediate_consumer: Noor production runtime
public_facade: n/a
bounded_acceptance: six-scenario delivery-aware latency and correctness matrix
non_goals:
  - quotation creation/media, voice, payment, referral, and real-customer traffic
evidence:
  - none
task_id: tj-15m
epic_id: tj-av22
stage_id: tj-15m
session_id: n/a
milestone: cohesive-vertical-slice
milestone_status: accepted
agent_type: worker
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: Root-owned sequential work preserved one production recipient, channel, queue, stop boundary, and exact cleanup owner.
repo: treejar
branch: main
base_branch: main
base_commit: ed28d9294dd12b2c798a4a150a5163fe3b879ce8
worktree: /home/me/code/treejar
write_zone:
  - bounded dialogue fixes, regression tests, production synthetic evidence, Beads, and stage documentation
success_criteria:
  - Six authorized scenarios have delivery, correctness, cleanup, p50, p95, and maximum evidence or an explicit external-model blocker.
selected_docs:
  - docs/superpowers/specs/2026-07-23-noor-stabilization-design.md
  - docs/superpowers/plans/2026-07-23-noor-post-release-validation.md
  - docs/latency-evidence.md
selected_skills:
  - orchestrator-stage
  - task-router
  - systematic-debugging
  - test-driven-development
  - test-pass
  - verification-before-completion
  - orchestration-closeout
selected_agents:
  - none; shared production state and one stop boundary required sequential root ownership
catalog_candidates:
  - none; installed workflows and repository runbooks covered the work
parallel_group: noor-live-synthetic-latency-proof
depends_on_streams:
  - none
parallel_decision: sequential
status: accepted
delivery_method: manual integration
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: No stage-specific worktree or branch was created; protected VPS evidence is intentionally retained with mode 600.
risk_level: high
verification_tier: release
risk_tags:
  - state-transition
  - idempotency
  - data
affected_surfaces:
  - backend
  - data
invariants:
  - state-transition
  - idempotency
  - test-matrix
docs_impact: behavior
docs_reviewed: updated
docs_review_notes: Updated final latency matrix, external-model blocker, source-specific factual checks, cleanup, and handoff.
verification:
  - uv run ruff check src/ tests/: passed
  - uv run ruff format --check src/ tests/: passed
  - uv run mypy src/: passed over 162 source files
  - uv run pytest tests/ -v --tb=short: passed with 1532 passed and 19 skipped
  - GitHub Actions run 30251148113: lint, type-check, tests, and deploy passed
  - production release, channel, six-scenario matrix, outbound audits, exact cleanup, and health readback: passed
changed_files:
  - src/dialogue/catalog_refs.py
  - src/llm/engine.py
  - src/services/customer_language.py
  - tests/test_customer_language.py
  - tests/test_dialog_scenarios.py
  - tests/test_dialogue_catalog_refs.py
  - tests/test_dialogue_runner.py
  - tests/test_llm_engine.py
  - docs/latency-evidence.md
  - .codex/handoff.md
  - .codex/stages/tj-15m
explicit_defers:
  - tj-0j7o: separate model/provider quality and release boundary for the accepted external-model latency blocker
---

# Summary

Completed the authorized six-scenario production matrix, corrected seven
bounded dialogue/media defects found by live evidence, and preserved catalog,
Zoho stock, order/quote, Arabic, escalation, and delivery invariants.

# Scope / Routing

All implementation and live proof stayed inside one shared production
recipient/channel and exact cleanup boundary. The work remained sequential and
root-owned because parallel ownership would have increased duplicate-send and
state-cleanup risk without a material latency or specialist benefit.

# Verification

Local release gates passed with `1532 passed, 19 skipped`; CI/deploy run
`30251148113` passed on exact code release `292d82c`. The six accepted samples
produced `p50 21.599s`, `p95 34.434s`, and maximum `37.775s`. Delivery audits,
source-specific facts, Arabic language, no-quote order behavior, and exact
escalation cleanup passed.

# Delivery / Cleanup

Code releases were committed directly to authorized `main` and delivered by the
canonical pipeline. No task branch or worktree exists. Protected raw production
evidence is intentionally retained on the VPS with mode `600`.

# Risks / Follow-ups / Explicit Defers

The maximum latency meets the `45s` ceiling, but p50/p95 remain above target.
Phase evidence identifies `model_tools` as the remaining external-model
bottleneck. Bead `tj-0j7o` owns that separate model/provider evaluation; no
production switch is authorized by this stage.
