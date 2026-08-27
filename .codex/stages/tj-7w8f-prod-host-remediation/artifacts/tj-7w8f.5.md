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
milestone_status: deferred_long_term
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
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: code was merged and deployed; dedicated worktree and merged local branch removed by the stage cleanup entrypoint
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
docs_review_notes: updated - production observe state, owner-excluded Polska scope, detached long-term Wazzup hardening, and superseded webhook-PATCH path are aligned without secrets
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
  - production enforcement is a long-term backlog item by owner decision; observe stays non-blocking until a supported WAuth binding is intentionally scheduled
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

The delegated technical premortem verdict was **GO WITH CONDITIONS** for the
application code. It covered permissive defaults, enforcement after a side
effect, weak or serialized secrets, public warning floods, auth bypassing the
IP/channel controls, and unexpected callback/subscription changes. Production
evidence later corrected its provider assumption: webhook PATCH does not support
`crmKey`, so no provider-side crmKey replacement or rotation was proven. The
application controls remain valid for a future supported WAuth binding.

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

The same command after the minimal implementation passed 10/10. During the
delegated local verification phase, the final focused command added the existing
normal webhook, disallowed-IP, refused-channel, and signature cases and passed
14/14; that phase made no provider or production request, database/Redis
operation, real message, or paid call. The later root-owned production outcome
is recorded below.

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

# Production rollout outcome and supported continuation

Root deployed commit `43d6430` through GitHub Actions run `33047773974` after
Ruff, Mypy, 3891 pytest cases, and the semantic retrieval gate passed. The app
was then moved to `observe` with a new `secrets.token_urlsafe(32)` value. The
protected production snapshot, key, request/response bodies, and receipts are
mode `0600`; no credential or callback value was logged or committed.

The original runbook assumption was wrong and is superseded by this result:

- Official `PATCH /v3/webhooks` accepts only `webhooksUri` and
  `subscriptions`. It does not configure `crmKey`.
- Official WAuth stores `crmKey` only during `POST /v3/connect`, together with
  connection-owned `state`, `secret`, and `name` values.
- Two same-key webhook PATCH attempts returned HTTP 200 and preserved the exact
  callback and all four subscription flags, but both provider test POSTs reached
  Noor without a matching Bearer. The unknown `crmKey` field was ignored.
- A bounded synthetic `{"test":true}` POST through the protected current
  `audit.starec.ai` relay with the same Bearer reached Noor and produced one
  privacy-safe `match`. The relay therefore preserves Authorization; it is not
  the missing binding.
- Enforcement was correctly stopped. Production remains in non-blocking
  `observe`; public and local health are HTTP 200, the app has zero restarts and
  zero OOM events, and the main model remains `z-ai/glm-5.3-flash`.

Do not repeat `PATCH /v3/webhooks` with `crmKey` and do not enable `enforce`.
The supported continuation requires proof that this account is connected by
WAuth and the owner-controlled WAuth connection values. If that connection
exists, rotate through the documented reconnect/`POST /v3/connect` path or with
Wazzup support, keeping the app in `observe` until a natural/provider-authorized
event produces `match`. If no WAuth connection exists, obtain from Wazzup a
supported callback-authentication mechanism before changing enforcement.

# Delivery / Cleanup

The implementation branch was reviewed, merged, pushed, and deployed. The root
orchestrator accepted the stage, detached the long-term Wazzup hardening backlog,
and removed the merged local branch and worktree.

# Risks / Follow-ups / Explicit Defers

- Production WAuth ownership and the connection values required by
  `POST /v3/connect` are unknown; webhook PATCH cannot supply them.
- The same long-term Bead owns the separate source-IP control and trustworthy
  proxy/CIDR evidence from `tj-7w8f.4`; `observe` does not authenticate senders.
- The two accepted PATCH calls changed no documented owner field. Their HTTP
  200 responses are not evidence that an unknown `crmKey` field was stored.
- Enforcement remains deliberately deferred until provider-side binding is
  proven by a matching real or provider-authorized event.
