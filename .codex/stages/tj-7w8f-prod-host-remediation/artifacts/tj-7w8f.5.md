---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-7w8f-prod-host-remediation/stage-manifest.json
stream_owner: prod-wazzup-crmkey-worker
orchestration_level: slice_acceptance
scope_kind: product_slice
immediate_consumer: root-orchestrator
public_facade: /api/v1/webhook/wazzup
bounded_acceptance: local staged Bearer crmKey authentication with masked strong secrets and pre-side-effect rejection
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
  - observe mode logs match at INFO and missing or mismatch at DEBUG without blocking the existing handler
  - enforce mode rejects missing malformed or wrong Bearer before persistence queues models CRM or outbound work
  - observe and enforce cannot start with a whitespace or sub-32-byte secret
  - settings representations and JSON serialization mask the crmKey
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
  - review-fix focused TDD RED with 17 collected cases: failed as expected with 10 failed and 7 existing-guard passes
  - review-fix focused TDD GREEN with the same 17 cases: passed with 17 passed
  - final focused affected auth default IP and channel tests: passed with 23 passed
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
compatible default. `observe` performs a constant-time comparison and
continues. A match emits the privacy-safe INFO signal `match`; missing and
mismatch signals are DEBUG-only so public traffic cannot flood warning logs.
`enforce` returns HTTP 401 with a Bearer challenge before JSON parsing, the IP
check, database sessions, Redis, ARQ, models, CRM, or outbound work unless the
secret matches.

`WAZZUP_WEBHOOK_SECRET` is a Pydantic `SecretStr`. Its raw value is absent from
Settings repr and JSON serialization. Both `observe` and `enforce` refuse to
start unless the value has at least 32 UTF-8 bytes and contains no whitespace.

The implementation does not alter the callback route, Wazzup provider
registration, subscription flags, IP-check semantics, or exact channel
equality. `.env.example` now leaves `WAZZUP_ALLOWED_IPS` empty until official
current ranges and a trustworthy proxy chain exist. `WAZZUP_API_KEY` remains
the outbound/account API credential and is never reused as the inbound crmKey.

# Scope / Routing

The request entry point and auth gate are in `src/api/v1/webhook.py`; runtime
configuration and the startup invariant are owned by `src/core/config.py`.
Existing persistence and queue effects remain in the handler after the new
gate. No shared helper, database model, worker, provider client, route, or
channel filter changed.

The revised technical premortem verdict was **GO WITH CONDITIONS**. Retained
failure shapes were a permissive default regression, enforcement after a side
effect, weak or serialized secrets, public warning floods, auth accidentally
bypassing IP/channel controls, and a provider PATCH that silently changes owner
configuration. Tests cover the application risks. Exact callback/subscription
equality is a hard operator precondition. crmKey replacement is explicitly an
irreversible rotation because the prior hidden provider value cannot be read or
restored.

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

Review-fix RED command:

```text
uv run --extra dev pytest tests/test_webhook.py::test_wazzup_webhook_observe_auth_logs_result_without_blocking_or_exposing_secrets tests/test_webhook.py::test_wazzup_webhook_enforce_auth_rejects_before_persistence_or_queue_work tests/test_webhook.py::test_wazzup_webhook_matching_bearer_still_requires_allowed_ip tests/test_webhook.py::test_wazzup_webhook_matching_bearer_still_rejects_wrong_channel tests/test_security.py::test_wazzup_webhook_rollout_auth_requires_strong_secret tests/test_security.py::test_wazzup_webhook_secret_is_masked_in_settings_output tests/test_security.py::test_wazzup_webhook_secret_minimum_uses_utf8_bytes -q --tb=short
```

Result before the review implementation: exit 1, 17 collected, 10 failed and
7 passed. Expected failures proved that missing/mismatch were still WARNING,
weak observe/enforce secrets were accepted, and the raw setting was a plain
string. The seven already-passing cases characterized the existing early 401
and the independent IP/channel layers. The identical target after the minimal
fix passed 17/17.

# Exact production observe / enforce / rollback runbook

All steps below are root/operator-owned and require the existing production
authority. Values stay in the protected operator channel; never place either
credential, the Authorization header, or the saved provider JSON in logs,
shell tracing, a command argument, the artifact, or Git.

## Preconditions, strong key generation, and immutable snapshot

1. Record the current release SHA and public health result. Create a mode-`0600`
   backup of `/opt/noor/.env` outside the replaceable release tree.
2. With the existing Wazzup account API credential, read the current webhook
   registration once into a separate mode-`0600` file. Preserve the exact
   `webhooksUri` and the complete subscription object as owner configuration.
   Record only a SHA-256 digest of that protected file in the operator receipt.
3. Generate one new key with Python `secrets.token_urlsafe(32)` directly into a
   mode-`0600` operator-owned secret file; the generation command must not print
   it. This produces a fresh URL-safe value above the 32-byte application
   minimum. Never reuse the existing nine-character value, `WAZZUP_API_KEY`, or
   any other account credential.
4. Build the desired provider payload from the protected registration snapshot
   and that one new key. The only semantic delta may be replacing `crmKey`;
   `webhooksUri`, every subscription key, and every subscription value must
   compare equal before sending. Abort on any other delta or concurrent drift.
5. Put the same new key in the protected `/opt/noor/.env` as
   `WAZZUP_WEBHOOK_SECRET`; keep file mode `0600`. Transfer it from the protected
   file without stdout, shell tracing, command arguments, logs, or clipboard
   history. Keep the protected source until production acceptance.

The provider PATCH is an explicit irreversible credential rotation. The old
hidden crmKey cannot be read back and must not be described as restorable.

## Observe

1. Deploy this release with `WAZZUP_WEBHOOK_AUTH_MODE=observe`, then recreate
   only the `app` service so the webhook process reads the new environment.
   Verify the app is running, the configured mode readback is exactly
   `observe`, and public health is green without printing the secret.
2. PATCH the provider once with the preflighted payload. This necessarily
   triggers Wazzup's registration test POST. Do not change the callback URL or
   any subscription flag.
3. In the bounded app-log window, accept only the privacy-safe INFO signal
   `Wazzup webhook auth: match` for that test POST. The log line contains no
   header, credential, URL, payload, channel, chat, or customer identifier.
   Missing/mismatch are DEBUG-only; absence of the bounded `match` proof means
   do not enforce and follow recovery below.
4. Read the provider registration once after PATCH and compare the returned
   callback and complete subscription object to the protected snapshot. Abort
   and recover on any difference. A missing returned crmKey is not evidence
   of failure because the provider read contract may omit secrets; the test POST
   `match` is the activation proof.

## Enforce

1. Change only `WAZZUP_WEBHOOK_AUTH_MODE` from `observe` to `enforce` in the
   protected env and recreate only `app`. Startup must fail closed if the secret
   contains whitespace or is shorter than 32 UTF-8 bytes; do not bypass this
   validator.
2. Verify sanitized mode readback equals `enforce` and public health remains
   green. A bounded synthetic `{"test":true}` request with missing, malformed,
   or wrong Bearer must return 401; the matching protected Bearer must return
   200. Do not use a customer message payload.
3. Confirm those rejected requests produced no JSON parse, database, Redis,
   ARQ, LLM, CRM, or outbound activity. At default INFO, only a successful
   `match` is logged; missing/mismatch remain DEBUG. Preserve the production
   `WAZZUP_ALLOWED_IPS` and `WAZZUP_CHANNEL_ID` values unchanged.

## Recovery and application rollback

Recovery triggers are absence of the provider test `match`, any callback or
subscription delta, app startup failure, unexpected provider 401, public-health
degradation, or restart instability.

1. If already enforcing, first set `WAZZUP_WEBHOOK_AUTH_MODE=observe` while
   retaining the same new `WAZZUP_WEBHOOK_SECRET`, then recreate only `app`.
   Observe accepts the provider test regardless of match while preserving the
   bounded `match` proof when configuration is correct.
2. Repeat the exact desired provider PATCH with the **same new strong crmKey**,
   exact owner callback, and exact complete subscription object. Never omit the
   key, generate a second key, or claim to restore the old hidden value. Confirm
   callback and every subscription field equal the protected snapshot; use the
   repeated test POST `match` as key-binding proof.
3. If the current release is healthy in observe mode, leave the provider on the
   new strong key and keep the app in observe until the cause is fixed. Public
   health and sanitized restart/status counts must return to baseline.
4. If the release itself is implicated, restore the recorded predecessor
   release through the existing Noor deployment rollback process **without
   rotating the provider again**. The predecessor ignores the Authorization
   header, so it remains compatible with the provider's new key. Preserve the
   new key in the protected operator store and production env for roll-forward;
   do not blindly restore a pre-rotation env that would lose it.
5. Recheck release identity, public health, process restarts, callback equality,
   complete subscription equality, and privacy-safe webhook status counts.
   Retain protected snapshots and the new key until root acceptance.

# Delivery / Cleanup

The branch is prepared for root review and merge. The root owns stage
acceptance, production rollout, completion-inbox handling, and eventual
worktree/branch cleanup. This worker performed no external delivery action.

# Risks / Follow-ups / Explicit Defers

- Production account binding is not proven locally; only the root-owned
  provider test POST in observe mode can prove the configured crmKey matches.
- The separate source-IP control still depends on trustworthy proxy/CIDR
  evidence from `tj-7w8f.4`; this change neither weakens nor claims to repair it.
- The provider PATCH has no proven compare-and-swap or atomic rollback. It is an
  irreversible key rotation: recovery repeats the exact desired registration
  with the same new strong key; it never removes or restores a hidden old key.
- Final production health, observe evidence, enforce rejection proof, provider
  state readback, and rollback readiness remain root-owned acceptance work.
