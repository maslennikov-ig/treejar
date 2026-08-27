---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-7w8f-prod-host-remediation/stage-manifest.json
stream_owner: prod-wazzup-crmkey-worker
orchestration_level: slice_acceptance
scope_kind: product_slice
immediate_consumer: root-orchestrator
public_facade: /api/v1/webhook/wazzup
bounded_acceptance: local staged Bearer crmKey authentication with fail-closed enforce startup and pre-side-effect rejection
non_goals:
  - production-or-provider-mutation
  - callback-url-or-subscription-change
  - Wazzup-IP-or-channel-scope-change
  - database-redis-message-or-paid-provider-call
evidence:
  - none
task_id: tj-7w8f.5
epic_id: tj-7w8f
stage_id: tj-7w8f-prod-host-remediation
session_id: tj-7w8f-prod-wazzup-crmkey
milestone: staged-wazzup-crmkey-authentication
milestone_status: in_progress
agent_type: backend_developer
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: assigned production authentication implementation retained the orchestrator model and reasoning
repo: treejar
branch: codex/prod-wazzup-crmkey-auth
base_branch: main
base_commit: 248a0e69d41ea5932accf73f34b98dce079a369f
worktree: /home/me/code/treejar/.worktrees/prod-wazzup-crmkey
write_zone:
  - src/core/config.py
  - src/api/v1/webhook.py
  - tests/test_webhook.py
  - tests/test_security.py
  - .env.example
  - .codex/stages/tj-7w8f-prod-host-remediation/artifacts/tj-7w8f.5.md
success_criteria:
  - disabled mode preserves the existing unauthenticated default
  - observe mode logs only missing mismatch or match and never blocks the existing handler
  - enforce mode rejects missing malformed or wrong Bearer before persistence queues models CRM or outbound work
  - enforce mode cannot start with a missing or empty secret
  - IP allowlisting and channel equality remain separate unchanged controls
selected_docs:
  - AGENTS.md
  - .codex/orchestrator.toml
  - .codex/handoff.md
  - .codex/stages/tj-7w8f-prod-host-remediation/stage-manifest.json
  - .codex/stages/tj-7w8f-prod-host-remediation/artifacts/tj-7w8f.4.md
  - Beads tj-7w8f.5
selected_skills:
  - superpowers:test-driven-development
  - technical-premortem
selected_agents:
  - backend_developer
catalog_candidates:
  - none
parallel_group: wazzup-crmkey-authentication
depends_on_streams:
  - tj-7w8f.4
parallel_decision: sequential
status: returned
delivery_method: merge
accepted_by_orchestrator: no
cleanup_status: pending
cleanup_notes: root owns acceptance merge production rollout and branch cleanup
risk_level: high
verification_tier: delta
risk_tags:
  - security
  - authorization
  - rollback
  - public-api
affected_surfaces:
  - api
  - backend
invariants:
  - rollback
  - test-matrix
docs_impact: ops-deploy
docs_reviewed: updated
docs_review_notes: .env.example and this artifact document the staged mode and production sequence without secret values
verification:
  - focused TDD RED with 10 collected cases: failed as expected with 9 failed and 1 permissive-path pass
  - focused TDD GREEN with the same 10 cases: passed with 10 passed
  - focused affected auth default IP and channel tests: passed with 14 passed
  - python3 scripts/orchestration/validate_artifact.py artifact: passed
  - git diff --check: passed
changed_files:
  - src/core/config.py
  - src/api/v1/webhook.py
  - tests/test_webhook.py
  - tests/test_security.py
  - .env.example
  - .codex/stages/tj-7w8f-prod-host-remediation/artifacts/tj-7w8f.5.md
explicit_defers:
  - root-owned production deploy provider PATCH observe proof enforce switch public health acceptance and rollback drill were not performed in this no-production stream
---

# Summary

Added a staged inbound Wazzup Bearer boundary. `disabled` is the backward-
compatible default. `observe` performs a constant-time comparison, emits one
privacy-safe result (`missing`, `mismatch`, or `match`), and continues.
`enforce` returns HTTP 401 with a Bearer challenge before JSON parsing, the IP
check, database sessions, Redis, ARQ, models, CRM, or outbound work unless the
secret matches. Settings validation refuses `enforce` when
`WAZZUP_WEBHOOK_SECRET` is empty or whitespace.

The implementation does not alter the callback route, Wazzup provider
registration, subscription flags, `WAZZUP_ALLOWED_IPS`, or exact channel
equality. `WAZZUP_API_KEY` remains the outbound/account API credential and is
not reused as the inbound crmKey.

# Scope / Routing

The request entry point and auth gate are in `src/api/v1/webhook.py`; runtime
configuration and the startup invariant are owned by `src/core/config.py`.
Existing persistence and queue effects remain in the handler after the new
gate. No shared helper, database model, worker, provider client, route, or
channel filter changed.

The technical premortem verdict was **GO WITH CONDITIONS**. Retained failure
shapes were a permissive default regression, enforcement after a side effect,
startup with no secret, secret-bearing logs, and a provider PATCH that silently
changes owner configuration. The tests and implementation cover the first four;
the production runbook below makes exact callback/subscription preservation a
hard precondition for the fifth.

# Verification

TDD RED command (before production code):

```text
uv run --extra dev pytest tests/test_webhook.py::test_wazzup_webhook_observe_auth_logs_result_without_blocking_or_exposing_secrets tests/test_webhook.py::test_wazzup_webhook_enforce_auth_rejects_before_persistence_or_queue_work tests/test_webhook.py::test_wazzup_webhook_enforce_auth_accepts_matching_bearer tests/test_security.py::test_wazzup_webhook_auth_defaults_to_disabled tests/test_security.py::test_wazzup_webhook_auth_enforce_requires_non_empty_secret -q --tb=short
```

Result: exit 1, 10 collected, 9 failed and 1 passed. Expected failures were no
auth result logs, enforce returning the former HTTP 200, missing Settings fields,
and no startup refusal. The matching-Bearer case passed only because the old
handler was fully permissive; it became meaningful together with the failing
negative branches.

The same command after the minimal implementation passed 10/10. The final
focused command added the existing normal webhook, disallowed-IP, refused-
channel, and signature cases and passed 14/14. No full suite, provider request,
production request, database/Redis operation, real message, or paid call ran.

# Exact production observe / enforce / rollback runbook

All steps below are root/operator-owned and require the existing production
authority. Values stay in the protected operator channel; never place either
credential, the Authorization header, or the saved provider JSON in logs,
shell tracing, a command argument, the artifact, or Git.

## Preconditions and immutable snapshot

1. Record the current release SHA and public health result. Create a mode-`0600`
   backup of `/opt/noor/.env` outside the replaceable release tree.
2. With the existing Wazzup account API credential, read the current webhook
   registration once into a separate mode-`0600` file. Preserve the exact
   `webhooksUri` and the complete subscription object as owner configuration.
   Record only a SHA-256 digest of that protected file in the operator receipt.
3. Build the proposed provider payload from that protected snapshot. The only
   semantic delta may be adding/replacing `crmKey`; `webhooksUri`, every
   subscription key, and every subscription value must compare equal before
   sending. Abort on any other delta or concurrent drift.
4. Put the same crmKey in the protected `/opt/noor/.env` as
   `WAZZUP_WEBHOOK_SECRET`; keep file mode `0600`. Do not reuse
   `WAZZUP_API_KEY` and do not print either value.

## Observe

1. Deploy this release with `WAZZUP_WEBHOOK_AUTH_MODE=observe`, then recreate
   only the `app` service so the webhook process reads the new environment.
   Verify the app is running, the configured mode readback is exactly
   `observe`, and public health is green without printing the secret.
2. PATCH the provider once with the preflighted payload. This necessarily
   triggers Wazzup's registration test POST. Do not change the callback URL or
   any subscription flag.
3. In the bounded app-log window, accept only the privacy-safe signal
   `Wazzup webhook auth: match` for that test POST. The log line contains no
   header, credential, URL, payload, channel, chat, or customer identifier.
   `missing` or `mismatch` means do not enforce; follow rollback below.
4. Read the provider registration once after PATCH and compare the returned
   callback and complete subscription object to the protected snapshot. Abort
   and roll back on any difference. A missing returned crmKey is not evidence
   of failure because the provider read contract may omit secrets; the test POST
   `match` is the activation proof.

## Enforce

1. Change only `WAZZUP_WEBHOOK_AUTH_MODE` from `observe` to `enforce` in the
   protected env and recreate only `app`. Startup must fail closed if the secret
   is absent or empty; do not bypass this validator.
2. Verify sanitized mode readback equals `enforce` and public health remains
   green. A bounded synthetic `{"test":true}` request with missing, malformed,
   or wrong Bearer must return 401; the matching protected Bearer must return
   200. Do not use a customer message payload.
3. Confirm those rejected requests produced no database, Redis, ARQ, LLM, CRM,
   or outbound activity and that logs contain only `missing`, `mismatch`, or
   `match`. Preserve `WAZZUP_ALLOWED_IPS` and `WAZZUP_CHANNEL_ID` unchanged.

## Rollback

Rollback triggers are provider test `missing`/`mismatch`, any callback or
subscription delta, app startup failure, unexpected 401 for the provider,
public-health degradation, or restart instability.

1. If already enforcing, first restore `WAZZUP_WEBHOOK_AUTH_MODE=observe` and
   recreate only `app`; this lets the provider's compensating test POST reach
   the old handler regardless of Bearer state.
2. PATCH the exact protected pre-change provider registration, omitting the new
   crmKey exactly as in the owner snapshot. Confirm callback and all subscription
   fields equal the snapshot. This is compensating rollback, not a claim of
   provider atomicity.
3. Restore the mode-`0600` pre-change `/opt/noor/.env`, recreate only `app`, and
   verify auth mode is the prior value, public health is green, and webhook
   status counts have returned to baseline without inspecting payloads.
4. If the release itself is implicated, use the existing Noor deployment
   rollback archive/process to restore the recorded predecessor release and
   recheck release identity, app health, process restarts, and sanitized webhook
   status counts. Retain the protected snapshots until root acceptance.

# Delivery / Cleanup

The branch is prepared for root review and merge. The root owns stage
acceptance, production rollout, completion-inbox handling, and eventual
worktree/branch cleanup. This worker performed no external delivery action.

# Risks / Follow-ups / Explicit Defers

- Production account binding is not proven locally; only the root-owned
  provider test POST in observe mode can prove the configured crmKey matches.
- The separate source-IP control still depends on trustworthy proxy/CIDR
  evidence from `tj-7w8f.4`; this change neither weakens nor claims to repair it.
- The provider PATCH has no proven compare-and-swap or atomic rollback. Exact
  before/after equality checks and the compensating PATCH are mandatory.
- Final production health, observe evidence, enforce rejection proof, provider
  state readback, and rollback readiness remain root-owned acceptance work.
