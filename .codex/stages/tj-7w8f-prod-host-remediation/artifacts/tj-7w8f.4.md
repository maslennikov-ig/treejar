---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-7w8f-prod-host-remediation/stage-manifest.json
stream_owner: prod-wazzup-boundary-worker
orchestration_level: slice_acceptance
scope_kind: product_slice
immediate_consumer: root-orchestrator
public_facade: /api/v1/webhook/wazzup
bounded_acceptance: privacy-safe production channel equality, history, warning timing, and fail-closed proof
non_goals:
  - production-env-db-config-or-service-mutation
  - deploy-or-restart
  - real-message-send-or-paid-provider-call
  - Wazzup-channel-scope-expansion
evidence:
  - none
task_id: tj-7w8f.4
epic_id: tj-7w8f
stage_id: tj-7w8f-prod-host-remediation
session_id: tj-7w8f-prod-wazzup-boundary
milestone: production-wazzup-channel-boundary-diagnosis
milestone_status: n/a
agent_type: custom
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: production authorization boundary required the assigned security auditor with inherited model and reasoning
repo: treejar
branch: codex/prod-wazzup-boundary-validation
base_branch: main
base_commit: 25598101f33f47c9d1117499daeb1f4a02928046
worktree: /home/me/code/treejar/.worktrees/prod-wazzup-boundary
write_zone:
  - .codex/stages/tj-7w8f-prod-host-remediation/artifacts/tj-7w8f.4.md
success_criteria:
  - configured and incoming channel identities are compared without exposing identifiers or customer data
  - expected production channel ownership is proven from current env, running containers, database, and history
  - warnings are classified as drift or correct fail-closed filtering
  - no real message, paid-provider call, production mutation, restart, or deploy occurs
selected_docs:
  - AGENTS.md
  - .codex/orchestrator.toml
  - .codex/handoff.md
  - .codex/stages/tj-7w8f-prod-host-remediation/summary.md
  - Beads tj-7w8f.4 and tj-ppid
selected_skills:
  - orchestrator-stage
  - systematic-debugging
selected_agents:
  - built-in-security-auditor
catalog_candidates:
  - none
parallel_group: wazzup-channel-boundary
depends_on_streams:
  - none
parallel_decision: parallel
status: returned
delivery_method: merge
accepted_by_orchestrator: no
cleanup_status: pending
cleanup_notes: root acceptance and branch cleanup remain with the orchestrator
risk_level: high
verification_tier: delta
risk_tags:
  - security
  - authorization
  - data
  - rollback
affected_surfaces:
  - api
  - backend
  - data
invariants:
  - rollback
  - test-matrix
docs_impact: docs-only
docs_reviewed: no-change-needed
docs_review_notes: no durable product or operator contract changed; this artifact records current stage evidence and one bounded security follow-up
verification:
  - privacy-safe production env container log and DB metadata inspection at release 7e21de2: passed
  - historical Beads tj-ppid identity and owner-decision comparison by hash: passed
  - uv run --extra dev pytest three focused webhook and worker channel-boundary tests -q --tb=short: passed, 3 passed
  - python3 scripts/orchestration/validate_artifact.py artifact: passed
  - git diff --check: passed
changed_files:
  - .codex/stages/tj-7w8f-prod-host-remediation/artifacts/tj-7w8f.4.md
explicit_defers:
  - tj-7w8f root must track and remediate the missing production Wazzup origin allowlist under explicit production-change authority and current official provider ranges
  - channel-specific provider-side webhook routing was not verified and must not be assumed as a safe warning-suppression mechanism
---

# Summary

**Decision: the repeated warnings are correct fail-closed protection, not
`WAZZUP_CHANNEL_ID` drift. No channel/config mutation is the safe fix.**

At the 2026-08-27 06:04:18 UTC snapshot, production release `7e21de2` had one
36-character expected channel value. Its privacy-safe hash tag was identical in
the mode-`0600` current `.env`, the running app container, and the running
worker container. There was no database `system_configs` channel override.
Production DB contained 532 conversations with exactly one stored inbound
channel identity, and that identity matched the current expected value.

The current app container recorded 16 refusals between 05:39:08 and 06:03:48
UTC. Every warning named the same one unexpected identity and the same expected
identity; the two hashes differ. Each refusal was within two seconds of an app
log entry for a webhook receipt containing a message. No missing-channel
configuration event occurred.

The unexpected hash also exactly matches the second channel documented by the
closed `tj-ppid` production investigation. That read-only provider inventory
established that both identifiers belonged to the same Wazzup account. The
owner then explicitly classified the second business-line channel as outside
the test bot's service scope. The current traffic therefore belongs to a known
integration channel but not to the one authorized for Noor processing.

# Scope / Routing

The reviewed boundary is `src/api/v1/webhook.py:262-281`, where
`settings.wazzup_channel_id` is required and equality is checked before a
message can reach Redis or ARQ. The worker repeats the same filter at
`src/services/chat.py:1062-1080`. `src/core/config.py:70-74` maps the expected
value from `WAZZUP_CHANNEL_ID`; `docker-compose.yml` injects `.env` into both
app and worker. No source, test, production configuration, database row,
service, provider account, or webhook route was changed.

Evidence was deliberately reduced to equality, short one-way hash tags,
counts, timestamps, lengths, file modes, and release/container metadata. No
raw channel, phone, chat, message, payload, or secret value is present here.

# Findings

## Correct control — no mutation (confirmed, preventive)

- **Attack/failure path:** a message bearing a channel identity outside the
  single configured scope reaches the webhook.
- **Observed behavior:** the app emits the warning and returns without writing
  to Redis or scheduling ARQ; the worker independently rejects missing or
  mismatched channels before DB/provider work.
- **Impact avoided:** an intentionally excluded business-line message cannot
  enter Noor's customer conversation, LLM, CRM, or outbound response path.
- **Prerequisite for acceptance:** exact equality with the configured channel.
- **Classification:** correct control; no fix. Confidence: high.

Changing `WAZZUP_CHANNEL_ID`, adding the second channel, or weakening equality
from warning traffic would widen customer-data and outbound-message authority
against the recorded owner decision. If product intent changes, that is a new
owner decision and a separately approved rollout, not incident remediation.

There is no evidence-backed in-repository suppression that preserves signal.
Provider-side channel-specific webhook routing was not verified in this pass,
so it must not be recommended as an available control. Keep the warning until
provider capabilities and intended channel ownership are confirmed.

## High — production origin allowlist is disabled (confirmed, must-fix follow-up)

- **Evidence:** production `WAZZUP_ALLOWED_IPS` is empty. In
  `src/api/v1/webhook.py:27-39`, an empty value causes the endpoint to accept
  every request origin. The route is the public Noor Wazzup webhook.
- **Attack path:** an external caller who obtains or guesses the expected
  channel identifier can submit a syntactically valid inbound payload. The
  channel equality guard does not authenticate the HTTP sender.
- **Impact:** unauthorized queue/LLM work and an outbound response to an
  attacker-controlled chat are possible; this can consume provider budget and
  pollute conversation/CRM data. The current warning traffic is not evidence
  that this happened.
- **Prerequisites:** public route access plus the expected channel identifier
  and a valid payload shape. Confidence: high for the missing preventive
  control and code path; unknown for exploitation.
- **Smallest mitigation:** after current official Wazzup source ranges are
  independently verified, set the production allowlist to only those ranges,
  validate origin parsing through the actual proxy chain, and restart only the
  app under explicit production authority. Keep channel equality as the second
  preventive layer. Until approved, do not expose the expected identifier and
  monitor refusal/403 counts. This pass did not perform containment because
  config edits and restarts were explicitly prohibited.

# Verification

Normal path, failure path, and the worker edge passed locally:

- an expected-channel webhook enqueues one batch;
- an unexpected-channel webhook returns success to stop provider retries but
  performs no Redis push and no ARQ enqueue;
- a worker batch with no configured expected channel terminates and quarantines
  before opening a DB session.

The first test command omitted the optional `dev` extra; `uv` therefore had no
`pytest` executable and returned `Permission denied` before collection. The
root cause was confirmed from `pyproject.toml` and the empty environment. The
same exact three-test set with `--extra dev` passed: 3 tests in 1.23 seconds.
This was an environment-launch failure, not a test failure.

Production validation was read-only. It covered current `.env`, running
container environments and creation timestamps, app/worker logs, release SHA,
and aggregate DB metadata. It did not call Wazzup, send a message, invoke a paid
provider, mutate DB/Redis/config, restart services, or deploy.

# Delivery / Cleanup

This branch contains only this artifact. The root orchestrator owns validation,
acceptance, merge, any Beads update, and cleanup. No production delivery action
is part of this stream.

# Risks / Follow-ups / Explicit Defers

1. Do not change channel configuration for `tj-7w8f.4`; the warnings prove the
   existing scope guard is active.
2. Track the missing production origin allowlist as a must-fix authorization
   follow-up. Runtime/proxy verification and the config/restart need explicit
   production authority.
3. If warning volume becomes operationally noisy, first verify whether Wazzup
   supports channel-scoped webhook delivery and whether the owner still wants
   the second channel excluded. Do not suppress or reroute based on an
   unverified assumption.
4. Static and read-only review cannot prove the HTTP sender was Wazzup while
   the origin allowlist is empty. It proves only that the received identifier
   equals the previously known excluded integration channel.
