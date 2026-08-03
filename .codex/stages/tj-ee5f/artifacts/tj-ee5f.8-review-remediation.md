---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-ee5f/stage-manifest.json
stream_owner: dialogue-review-remediation
orchestration_level: integration
scope_kind: product_slice
immediate_consumer: tj-ee5f parent remediation stream
public_facade: Noor dialogue and quotation-consent behavior
bounded_acceptance: focused R-01 R-02 and R-05 dialogue regressions
non_goals:
  - catalog materialization, evaluator, model battle, deployment, or production readback
  - Beads, handoff, stage summary, specification, or plan changes
evidence:
  - none
task_id: tj-ee5f.8
epic_id: tj-ee5f
stage_id: tj-ee5f
session_id: tj-ee5f-r08-review-remediation
milestone: deterministic dialogue review remediation
milestone_status: accepted
agent_type: worker
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: inherited for a bounded typed-state remediation stream
repo: treejar
branch: codex/tj-ee5f-r08-review-remediation
base_branch: codex/tj-ee5f-quality-model-battle
base_commit: d58e321
worktree: /home/me/code/treejar/.worktrees/tj-ee5f-r08-review-remediation
write_zone:
  - src/core/config.py
  - src/dialogue/order_state.py
  - src/dialogue/reducer.py
  - src/dialogue/runner.py
  - src/dialogue/state.py
  - src/llm/engine.py
  - tests/test_dialogue_config.py
  - tests/test_dialogue_runner.py
  - tests/test_dialogue_state.py
  - tests/test_llm_engine.py
  - .codex/stages/tj-ee5f/artifacts/tj-ee5f.8-review-remediation.md
success_criteria:
  - typed dialogue reconciliation is the default runtime mode
  - quote refusal and defer remain distinct and refusal never becomes on-hold wording
  - canonical quote workflow wins over stale dialogue-kernel state
  - quote details are collected only after typed granted consent
  - trusted legacy grant context is canonicalized before quotation side effects
selected_docs:
  - AGENTS.md
  - .codex/orchestrator.toml
  - .codex/handoff.md
  - docs/superpowers/specs/2026-08-03-noor-e2e-remediation-and-model-comparison-spec.md
selected_skills:
  - orchestrator-stage
  - test-driven-development
  - systematic-debugging
  - verification-before-completion
selected_agents:
  - worker
catalog_candidates:
  - none
parallel_group: quality-model-remediation
depends_on_streams:
  - none
parallel_decision: parallel
status: accepted
delivery_method: cherry-pick
accepted_by_orchestrator: yes
cleanup_status: pending
cleanup_notes: parent must review and integrate the commit before cleanup
risk_level: high
verification_tier: integration
risk_tags:
  - user-flow
  - state
  - backwards-compatibility
affected_surfaces:
  - backend
  - user-flow
invariants:
  - idempotency
  - test-matrix
  - backwards-compatibility
docs_impact: internal
docs_reviewed: updated
docs_review_notes: this artifact records only behavior covered by focused tests
verification:
  - RED default runtime tests failed with legacy mode and missing state reconciliation
  - RED canonical precedence test failed because stale kernel grant won
  - RED refusal and defer tests failed in post-quotation and ambiguous later wording
  - RED typed detail guard and trusted legacy migration tests failed before implementation
  - uv run --extra dev pytest tests/test_dialogue_config.py tests/test_dialogue_order_state.py tests/test_dialogue_state.py tests/test_dialogue_runner.py tests/test_dialogue_replay_fixtures.py tests/test_llm_engine.py -q --tb=short: 803 passed
  - targeted Ruff check and format check: passed
  - targeted Mypy for six source files: passed
  - git diff --check: passed
changed_files:
  - src/core/config.py
  - src/dialogue/order_state.py
  - src/dialogue/reducer.py
  - src/dialogue/runner.py
  - src/dialogue/state.py
  - src/llm/engine.py
  - tests/test_dialogue_config.py
  - tests/test_dialogue_runner.py
  - tests/test_dialogue_state.py
  - tests/test_llm_engine.py
  - .codex/stages/tj-ee5f/artifacts/tj-ee5f.8-review-remediation.md
explicit_defers:
  - catalog materialization and provenance remain outside this stream
  - evaluator and isolated model battle remain with tj-ee5f.12 and tj-ee5f.13
  - integration full release gates deployment and production acceptance remain with the parent stage
---

# Summary

Typed dialogue reconciliation is now the default local runtime mode. Empty
enforcement configuration still lets the legacy response generator answer, but
the typed state is reconciled and persisted on the same production path.

Explicit quote refusal now records `declined` and returns to consultation even
after a quotation was already sent; the historical `created` lifecycle remains
truthful. Phrases that explicitly postpone a quote record `deferred` instead.
Customer-facing context and sales-opportunity responses no longer translate a
refusal into “on hold” wording or write a new legacy `quotation_hold` marker.

The canonical `order_runtime.quote_workflow` overrides stale kernel state.
Assistant requests for customer, email, phone, or delivery details are removed
unless typed consent is `granted`; the current message text and an active quote
frame no longer bypass that gate. A trusted legacy exact-quote or
sales-order-quote grant is canonicalized before quotation adapters run, while
missing or malformed canonical state fails closed.

# Customer-visible behavior

- “I do not want the quotation” no longer produces or preserves “on hold”
  wording. It states that no quotation was created unless one already existed.
- “Not yet / later / for now” remains a defer rather than becoming a refusal.
- A model response cannot ask for quote-only address or contact details before
  the typed workflow records explicit consent.
- An affirmative reply to an existing saved quote selection resumes at the
  missing customer detail instead of asking for products again, and first
  writes the canonical grant.

# Verification

The focused TDD cycles reproduced the legacy-default path, stale canonical
precedence, post-quotation refusal, defer classification, pre-consent detail
collection, and trusted legacy migration failures before implementation.

The final bounded integration command passed all 803 selected dialogue,
replay, and engine tests. No provider, model, paid, deployment, or production
call was made.

# Risks / Follow-ups

This stream does not establish that the full stage or release suite passes, and
does not claim catalog, evaluator, battle, deployment, or production
remediation. The parent must integrate the commit, reconcile Beads and stage
documents, list this new artifact in the owning stage manifest, and run its
risk-selected acceptance and closeout gates.
