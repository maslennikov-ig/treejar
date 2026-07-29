---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-ee5f/stage-manifest.json
stream_owner: trust-remediation
orchestration_level: integration
scope_kind: foundation
immediate_consumer: tj-ee5f.1
public_facade: noor-e2e-observe and IndependentExecutionProducer
bounded_acceptance: server-owned observations only; semantic publication fails closed without a trusted compiler
non_goals:
  - no live HTTP, SSH, provider, customer, CRM, quotation, deploy, paid call, or Beads mutation
evidence:
  - runtime_evidence
  - server_observation
  - live_runtime
task_id: tj-ee5f.5-remediation
epic_id: tj-ee5f
stage_id: tj-ee5f
session_id: tj-ee5f.5-server-observation
milestone: canonical server observation and fail-closed production collection
milestone_status: accepted
agent_type: worker
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: production evidence integrity and external side effects require strict fail-closed contracts
repo: treejar
branch: codex/tj-ee5f-5-runtime-plan-compat
base_branch: codex/tj-ee5f-remediation
base_commit: 475dcb02bb75aa2028f061dc6cd31bfd50e63ceb
worktree: /home/me/code/treejar/.worktrees/tj-ee5f-5-runtime-plan-compat
write_zone:
  - pyproject.toml
  - scripts/e2e_acceptance/live_producer.py
  - scripts/e2e_acceptance/live_transport.py
  - src/integrations/crm/zoho_crm.py
  - src/llm/engine.py
  - src/llm/order_quote_routes.py
  - src/services/chat.py
  - src/services/e2e_observation_producer.py
  - src/services/outbound_audit.py
  - src/services/runtime_execution_evidence.py
  - tests/test_e2e_acceptance_live_runtime.py
  - tests/test_e2e_observation_producer.py
  - tests/test_llm_engine.py
  - tests/test_outbound_audit.py
  - tests/test_runtime_execution_evidence.py
  - tests/test_services_chat_batch.py
  - tests/test_zoho_crm.py
  - .codex/stages/tj-ee5f/artifacts/tj-ee5f.5-production-trust-remediation.md
success_criteria:
  - production transcript, model, timing, token, cost, tool, audit, media, and side-effect facts come from durable server rows and exact provider readbacks
  - Pydantic and deterministic quotation tool calls emit digest-only terminal traces
  - Wazzup pending, sent, unknown, or provider-duplicate states block terminal production evidence
  - CRM contact, CRM deal, sale order, PDF audit, and escalation deltas have exact baseline, expected, and final readback coverage
  - unknown, active, unlisted, or missing side effects block materialization
  - caller-authored execution attempts and evaluation JSON are not accepted by the production collector
  - SSH permits only the exact installed noor-e2e-observe command shape
selected_docs:
  - AGENTS.md
  - .codex/orchestrator.toml
  - .codex/handoff.md
  - docs/superpowers/plans/2026-07-29-noor-e2e-remediation-and-closeout.md
selected_skills:
  - orchestrator-stage
  - superpowers:systematic-debugging
  - superpowers:test-driven-development
  - superpowers:using-git-worktrees
  - superpowers:verification-before-completion
selected_agents:
  - none
catalog_candidates:
  - none
parallel_group: tj-ee5f-runtime-observation
depends_on_streams:
  - tj-ee5f.5-runtime-plan-compat
parallel_decision: local
status: returned
delivery_method: cherry-pick
accepted_by_orchestrator: no
cleanup_status: pending
cleanup_notes: isolated worktree and branch remain for orchestrator integration
risk_level: high
verification_tier: integration
risk_tags:
  - authorization
  - security
  - retry
  - state-transition
  - idempotency
  - data
affected_surfaces:
  - backend
  - data
invariants:
  - state-transition
  - idempotency
  - rollback
  - test-matrix
docs_impact: behavior
docs_reviewed: updated
docs_review_notes: stage artifact records the remaining trusted semantic compiler boundary
verification:
  - focused RED: 5 expected failures for missing source binding, business delta coverage, terminal readback, and caller-independent collection
  - focused observation and transport GREEN: passed 42
  - impacted chat, LLM, quotation, outbound audit, observation, live runtime, and exact CRM readback tests: passed 583
  - focused Mypy for eight changed source modules: passed
  - focused Ruff check and format: passed
  - artifact validator: passed
  - git diff check: passed
changed_files:
  - pyproject.toml
  - scripts/e2e_acceptance/live_producer.py
  - scripts/e2e_acceptance/live_transport.py
  - src/integrations/crm/zoho_crm.py
  - src/llm/engine.py
  - src/llm/order_quote_routes.py
  - src/services/chat.py
  - src/services/e2e_observation_producer.py
  - src/services/outbound_audit.py
  - src/services/runtime_execution_evidence.py
  - tests/test_e2e_acceptance_live_runtime.py
  - tests/test_e2e_observation_producer.py
  - tests/test_llm_engine.py
  - tests/test_outbound_audit.py
  - tests/test_runtime_execution_evidence.py
  - tests/test_services_chat_batch.py
  - tests/test_zoho_crm.py
  - .codex/stages/tj-ee5f/artifacts/tj-ee5f.5-production-trust-remediation.md
explicit_defers:
  - a permit-bound semantic compiler is still required to construct ScenarioAttemptV2 from sealed planned turns, server observations, and one bounded judge receipt
  - evaluators.py cannot fill that boundary because it only combines caller-provided mappings and has no production call site
  - pre-authorized retention of still-active test entities needs the semantic compiler to bind protected retention authority; without it the server producer requires cleanup to a terminal provider state
  - production invocation remains with the root orchestrator after integration, review, deploy authority, and fresh preflight
---

# Summary

The application now records bounded versioned evidence for each inbound turn:
assistant identity, received/recorded times, digest-only tool call/return traces,
and pre/post business inventory. Deterministic quotation creation emits the
same typed trace as Pydantic tool calls. Outbound text, product media, and quote
PDF audits retain their exact inbound source binding across Wazzup callbacks.

The installed `noor-e2e-observe` command reads the production database and
exact Zoho identities to build transcript, duration, token/cost, tool, audit,
media, CRM, sale-order, and escalation facts. It accepts only provider-terminal
Wazzup states and terminal side-effect readbacks. Unknown, active, missing, or
unlisted effects stop evidence materialization.

`IndependentExecutionProducer` no longer reads `evaluation:<execution_id>` or
any caller-shaped attempt JSON. It stores the exact server observation and then
fails closed until a separate trusted semantic compiler is present.

# Verification

The focused RED reproduced five missing-trust failures before implementation.
The focused observation/transport set then passed 42 tests. The affected
integration set passed 583 tests across chat batching, LLM routes, quotations,
outbound audit, server observation, runtime evidence, live runtime, and exact
CRM readback.
Focused Ruff and Mypy checks pass. No product system prompt changed.

# Delivery / Cleanup

Returned as one local commit for orchestrator review and cherry-pick. No push,
deploy, paid model call, provider message, production mutation, or external
cleanup was performed.

# Risks / Follow-ups / Explicit Defers

The repository still has no implementation of the allowlisted
`production-policy-classifier`. `scripts/e2e_acceptance/evaluators.py` only
combines already supplied deterministic and judge mappings and is unused by
production code, so treating it as a compiler would reintroduce caller trust.
The remaining component must build `ScenarioAttemptV2` from sealed planned
turns plus the stored server observation and a permit-bound, one-call bounded
judge receipt. It must also bind any explicit retention to the protected
retention authority. Until then publication is fail-closed; cleaned terminal
provider facts remain collectable and immutable.
