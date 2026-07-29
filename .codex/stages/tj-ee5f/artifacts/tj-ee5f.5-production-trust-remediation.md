---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-ee5f/stage-manifest.json
stream_owner: trust-remediation
orchestration_level: integration
scope_kind: foundation
immediate_consumer: tj-ee5f.1
public_facade: noor-e2e-observe and IndependentExecutionProducer
bounded_acceptance: trusted local compilation from sealed plans, server observations, and one permit-bound judge action
non_goals:
  - no live HTTP, SSH, provider, customer, CRM, quotation, deploy, paid call, or Beads mutation
evidence:
  - runtime_evidence
  - server_observation
  - live_runtime
  - trusted_execution
  - semantic_compiler
task_id: tj-ee5f.5-remediation
epic_id: tj-ee5f
stage_id: tj-ee5f
session_id: tj-ee5f.5-production-trust-correction
milestone: exact runtime authority and provider-bound evidence
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
  - scripts/e2e_acceptance/execution.py
  - scripts/e2e_acceptance/production.py
  - scripts/run_noor_e2e_acceptance.py
  - src/integrations/crm/zoho_crm.py
  - src/llm/engine.py
  - src/llm/order_quote_routes.py
  - src/services/chat.py
  - src/services/e2e_observation_producer.py
  - src/services/outbound_audit.py
  - src/services/runtime_execution_evidence.py
  - tests/test_e2e_acceptance_live_runtime.py
  - tests/test_e2e_acceptance_live_authority.py
  - tests/test_e2e_acceptance_production.py
  - tests/test_e2e_acceptance_trusted_execution.py
  - tests/test_e2e_observation_producer.py
  - tests/test_llm_engine.py
  - tests/test_outbound_audit.py
  - tests/test_runtime_execution_evidence.py
  - tests/test_services_chat_batch.py
  - tests/test_zoho_crm.py
  - .codex/stages/tj-ee5f/artifacts/tj-ee5f.5-production-trust-remediation.md
success_criteria:
  - local, live, and live-with-judge modes accept only their exact adapter sets and runtime transport digest
  - the planned customer input digest is the exact protected question digest used by semantic compilation
  - one derived semantic request permit binds the protected observation and exact dynamic OpenRouter request before network I/O
  - only typed protected semantic response receipts can terminalize paid model actions
  - server evidence fails closed when provider model, token, or cost facts are missing; deterministic static responses carry explicit zero-cost provenance
  - duplicate turn, message, or provider identities are rejected before compilation
  - unknown OpenRouter actions cannot be reconciled through Wazzup facts
  - production transcript, model, timing, token, cost, tool, audit, media, and side-effect facts come from durable server rows and exact provider readbacks
  - Pydantic and deterministic quotation tool calls emit digest-only terminal traces
  - Wazzup pending, sent, unknown, or provider-duplicate states block terminal production evidence
  - CRM contact, CRM deal, sale order, PDF audit, and escalation deltas have exact baseline, expected, and final readback coverage
  - unknown, active, unlisted, or missing side effects block materialization
  - caller-authored execution attempts and evaluation JSON are not accepted by the production collector
  - every paid judge call consumes one exact pre-authorized journal action and settles actual cost
  - judge replay uses the protected receipt and never dispatches a second request
  - active effects are retained only under an exact current pre-authorized retention specification
  - unchanged pre-existing inventory remains visible without becoming a false business delta
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
docs_review_notes: stage artifact records the completed compiler boundary and remaining live acceptance gate
verification:
  - focused RED covered exact runtime adapter modes, input digest drift, fabricated completion, request tampering, incomplete provider usage, duplicate identities, and cross-provider reconciliation
  - affected acceptance, observation, runtime evidence, chat batching, and LLM engine tests: passed 725
  - canonical src Mypy: passed for 165 source files
  - strict Mypy for compiler, journal, transport, and production collector: passed for 4 source files without import suppression
  - affected Ruff check and format: passed
  - artifact validator: passed
  - git diff check: passed
changed_files:
  - scripts/e2e_acceptance/execution.py
  - scripts/e2e_acceptance/live_producer.py
  - scripts/e2e_acceptance/live_transport.py
  - scripts/e2e_acceptance/production.py
  - scripts/run_noor_e2e_acceptance.py
  - src/llm/engine.py
  - src/services/chat.py
  - src/services/e2e_observation_producer.py
  - src/services/runtime_execution_evidence.py
  - tests/test_e2e_acceptance_live_authority.py
  - tests/test_e2e_acceptance_live_runtime.py
  - tests/test_e2e_acceptance_production.py
  - tests/test_e2e_acceptance_trusted_execution.py
  - tests/test_e2e_observation_producer.py
  - tests/test_runtime_execution_evidence.py
  - .codex/stages/tj-ee5f/artifacts/tj-ee5f.5-production-trust-remediation.md
explicit_defers:
  - production execution remains with the root orchestrator after integration and review; it includes deploy/preflight, materializing sealed run authority and evidence specifications, paid/provider canaries, readback, and cleanup
---

# Summary

The application now records bounded versioned evidence for each inbound turn:
assistant identity, received/recorded times, digest-only tool call/return traces,
explicit provider-reported or deterministic-static usage provenance, and
pre/post business inventory. Missing provider model, token, or cost data is a
hard evidence failure. Deterministic quotation creation emits the same typed
trace as Pydantic tool calls. Outbound text, product media, and quote PDF audits
retain their exact inbound source binding across Wazzup callbacks.

The installed `noor-e2e-observe` command reads the production database and
exact Zoho identities to build transcript, duration, token/cost, tool, audit,
media, CRM, sale-order, and escalation facts. It accepts only provider-terminal
Wazzup states and terminal side-effect readbacks. Unknown, active, missing, or
unlisted effects stop evidence materialization.

`IndependentExecutionProducer` no longer reads `evaluation:<execution_id>` or
any caller-shaped attempt JSON. Its sealed semantic compiler checks the exact
protected question digest, deterministic evidence, readbacks, and side effects
before it can derive one request permit for a pre-authorized
`model.classify` action. The permit binds the protected observation and exact
dynamic OpenRouter request before I/O. Only a typed protected response receipt
can complete that action and settle actual cost; generic completion cannot
terminalize model work. Resume replays the receipt without another paid call.

Runtime authority now distinguishes exact local, live, and live-with-judge
adapter sets and binds them to the matching transport digest. Duplicate turn,
message, and provider identities fail closed. Wazzup reconciliation requires
the exact protected outbound request and provider receipt; it cannot infer or
complete an unknown OpenRouter action.

Active test effects are accepted as `retained` only when an unexpired protected
retention specification matches the exact entity and state. Otherwise they
remain cleanup blockers. Unchanged pre-existing inventory is preserved in the
final inventory and is not misreported as a newly created effect. Assertions
that depend on external or reused evidence require exact sealed artifact and
receipt references; the compiler cannot mint them from caller JSON.

# Verification

Focused TDD covered exact adapter modes, question-digest binding, derived
request permits, fabricated completion, request tampering, incomplete provider
usage, duplicate identities, provider-specific reconciliation, receipt replay,
actual cost settlement, and unchanged inventory. The affected acceptance set
passed 725 tests. Canonical source Mypy passed 165 files; strict Mypy passed the
four acceptance compiler/transport/collector modules without suppressing
imports. Ruff and format checks pass. No product system prompt changed and
captured scenario phrases remain fixtures.

# Delivery / Cleanup

Returned as one local commit for orchestrator review and cherry-pick. No push,
deploy, paid model call, provider message, production mutation, or external
cleanup was performed.

# Risks / Follow-ups / Explicit Defers

No production request or paid judge call was made in this stream. The root
orchestrator still needs to integrate and review the commit, deploy under the
repository authority gate, and materialize the live sealed compiler
configuration plus exact journal actions. Any assertion that uses external or
reused evidence needs its protected artifact and receipt published before the
run. Production acceptance and terminal cleanup/readback remain the final
proof; this artifact does not claim them.
