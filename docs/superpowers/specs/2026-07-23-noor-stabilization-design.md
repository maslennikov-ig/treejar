# Noor Production Stabilization — Design Specification

**Date:** 2026-07-23
**Status:** Approved direction for implementation
**Beads epic:** `tj-av22`
**Canonical runtime:** `https://noor.starec.ai`

## 1. Purpose

Bring Noor from “generally operating but carrying known production risks” to a
controlled, observable, and supportable state. The work covers every technical
finding from the 2026-07-23 audit. It does not silently turn business decisions
or third-party approvals into engineering scope.

Success means:

- the public Redis debug exposure is removed;
- a malformed Zoho OAuth response cannot silently lose an accepted inbound
  batch;
- stale production escalations can be classified and reconciled safely;
- health and Docker maintenance report and perform what their contracts claim;
- critical background failures are visible without exposing secrets or PII;
- response latency is measured and reduced without degrading answer quality;
- public `501 Not implemented` contracts are either completed or deliberately
  retired;
- the release is verified locally and, after explicit approval, in production;
- Beads, stage records, handoff, and operational documentation match reality.

## 2. Audit Baseline

The 2026-07-23 audit established the following:

| Finding | Current evidence | Risk | Beads |
|---|---|---:|---|
| Public Redis debug route | `/api/v1/debug/redis` responds without authentication and reads raw queue messages | Critical data exposure | `tj-9c94` |
| Zoho token response is trusted by HTTP status alone | A `200` response without `access_token` caused `KeyError`; the accepted incoming batch was not retried | Message loss / CRM failure | `tj-p9ui` |
| Escalation state drift | 33 pending rows; most are older than 30 days, including conversations whose current state no longer matches the row | Bot can remain paused or managers can see false work | `tj-ymi3` |
| Docker maintenance is not executing | Deployed cron redirection fails when the log directory is absent; reclaimable Docker data is material | Disk exhaustion over time | `tj-092y` |
| Health contract is incomplete | Version is hard-coded as `0.1.0` while package version is `0.4.0`; Redis is checked but the database is not | False-positive health and release ambiguity | `tj-38l5` |
| Failure visibility is weak | OAuth, failed jobs, queue age, stale escalations, and maintenance failures lack one operational contract | Slow detection and recovery | `tj-av22.1` |
| Response latency remains high | Historical observations are roughly 17–42 seconds and need a repeatable current baseline | Poor user experience | `tj-15m` |
| Three public API paths still return `501` | Inventory sync/status and quality report creation are exposed but incomplete | Ambiguous API contract | `tj-av22.2` |
| Local orchestration residue exists | Old worktrees/branches and a stale handoff need exact, non-destructive reconciliation | Operator confusion | `tj-rt42` |

The local code quality baseline was green at the audit point: Ruff, formatting,
Mypy, and the full test suite passed (`1431 passed, 19 skipped`). That is a
starting point, not evidence that production defects are absent.

## 3. Scope Boundaries

### In scope

1. Security boundary for diagnostic endpoints.
2. Shared validation of Zoho OAuth token responses and reliable inbound batch
   outcome handling.
3. A read-only escalation audit and an idempotent, explicitly applied
   reconciliation operation.
4. Database-aware health reporting and version derivation from package
   metadata.
5. Idempotent Docker maintenance installation and post-install verification.
6. Low-cost operational visibility using the existing runtime, logs, Redis,
   database, and current notification channel.
7. Evidence-driven latency work.
8. Resolution of the three known `501` routes.
9. Controlled integration, delivery, verification, documentation, and local
   workspace cleanup.

### External gates / not assumed in this epic

The following remain separate because they require product policy, credentials,
vendor approval, or confirmed field mappings:

- referral launch (`tj-final27.6`);
- WABA template approval (`tj-gh21`);
- catalog issue GH #54 (`tj-2pkk`);
- a new soft/hard escalation policy (`tj-g3f`);
- delivery-source policy (`tj-9q0`);
- Zoho UTM/custom-field mapping (`tj-hye`).

The implementation may preserve extension points for these items, but it must
not guess their policy or mark them complete.

## 4. Chosen Approach

Use a staged stabilization program:

1. close exposure and message-loss paths;
2. add safe operational controls and visibility;
3. measure and improve latency;
4. settle incomplete API contracts;
5. integrate, obtain production approval, release, verify, and close.

This is preferred over:

- **P1-only hotfixing:** faster initially, but leaves health, observability,
  maintenance, and contract ambiguity unresolved;
- **full product completion:** mixes technical stabilization with blocked
  business decisions and makes safe acceptance impossible.

## 5. Required System Invariants

### 5.1 Security and privacy

- No unauthenticated route may return raw Redis values, message bodies, phone
  numbers, tokens, credentials, or internal queue keys.
- Diagnostic detail is either removed from the public router or protected by
  the existing internal/admin authentication mechanism.
- Logs and alerts contain stable identifiers and error classes, not OAuth
  payloads, access tokens, message text, or customer PII.
- Error responses use sanitized public messages; full exceptions remain in
  controlled logs.

### 5.2 Inbound message delivery

- An inbound batch accepted for background processing must end in one of three
  explicit outcomes: processed, retryable failure, or terminal quarantined
  failure.
- OAuth payload validation occurs before downstream CRM use.
- A `2xx` token response without a non-empty `access_token` is a typed,
  sanitized integration error, not `KeyError`.
- Retry classification is explicit. Transient network, rate-limit, and token
  service failures are retryable with bounded backoff; invalid configuration is
  terminal and visible.
- Retrying a batch must not duplicate stored inbound messages or outbound
  replies. Existing message identifiers/idempotency keys are reused.

### 5.3 Escalation state

- Conversation state, pending escalation rows, and bot-pause decisions are
  evaluated from one documented state transition policy.
- Audit mode is read-only and the default.
- Apply mode requires an explicit flag, prints exact affected record IDs,
  suppresses real Telegram sends by default, and is idempotent.
- Automatic reconciliation is limited to unambiguous stale combinations.
  Ambiguous or recent records are reported for human review.

### 5.4 Health and maintenance

- `/api/v1/health` reports the actual application version from package/runtime
  metadata.
- Redis and the primary database are required dependencies. Required dependency
  failure returns a non-success health status and HTTP `503`; healthy operation
  returns `200`.
- Dependency messages are sanitized and bounded.
- The maintenance installer creates the log directory before cron can redirect
  output, installs one marked entry idempotently, and verifies the installed
  entry.
- Cleanup remains dry-run by default. Aggressive prune is never scheduled by
  default.

### 5.5 Failure visibility

The existing stack must expose or alert on:

- OAuth refresh failures;
- failed/exhausted background jobs;
- oldest inbound queue item / stalled queue;
- stale pending escalation count;
- maintenance last-run failure or staleness.

Thresholds, destination, owner, and remediation are documented. No new paid
monitoring service is introduced. A real external notification test requires
explicit production approval.

### 5.6 Latency and quality

- Optimization starts with a repeatable stage-by-stage baseline, not
  speculation.
- The measurement records total duration and major phases without message
  content or PII.
- Changes must preserve product-search correctness, quotation/order behavior,
  escalation decisions, language behavior, and existing quality tests.
- After an approved deployment, the bounded synthetic matrix should reach
  `p50 <= 15s`, `p95 <= 25s`, and no response over `45s`. If an external model
  provider makes this impossible, evidence and the exact external blocker must
  be recorded instead of weakening correctness.

### 5.7 Public API contracts

Known `501` routes:

- `POST /api/v1/inventory/sync`;
- `GET /api/v1/inventory/sync/status`;
- `POST /api/v1/quality/reports/`.

For each route, inspect real consumers and documentation, then choose one:

1. implement the documented contract with authorization and tests; or
2. remove/deprecate the route with compatibility evidence and updated docs.

An unexplained public `501` is not an acceptable final state.

## 6. Component Design

### OAuth and batch reliability

Introduce a small shared Zoho OAuth parser/error type used by CRM and Inventory
clients. It validates JSON shape, error fields, token type, and expiration
without logging secrets. The inbound worker/service boundary converts typed
integration failures into the queue's retry/terminal semantics and preserves
idempotency.

Expected touchpoints:

- `src/integrations/zoho_oauth.py` (new shared contract);
- `src/integrations/crm/zoho_crm.py`;
- `src/integrations/inventory/zoho_inventory.py`;
- `src/services/chat.py`;
- `src/worker.py`;
- Zoho, worker, and batch tests.

### Escalation reconciliation

Extend the existing `src/services/escalation_state.py` policy and
`scripts/escalation_guard.py` safety mechanism. Add a dedicated reconciliation
entrypoint only if the existing script cannot express exact audit/apply
semantics cleanly. Output must be machine-readable enough to archive before
apply.

### Health, maintenance, and visibility

The health handler receives database and Redis dependencies through normal
FastAPI dependency injection. Package version resolution lives outside the
handler and has a deterministic fallback. Maintenance installation validates
directory, executable, crontab, and log behavior. Runtime visibility should
reuse structured logs and existing Telegram notification infrastructure, with
deduplication/cooldowns and safe test suppression.

### Latency

Instrument the existing message pipeline around queue wait, context assembly,
LLM/model calls, tools/RAG, and outbound delivery. Use those measurements to
choose changes. Acceptable techniques include safe parallelism for independent
I/O, bounded caching, smaller non-overlapping context, and bounded tool loops.
Provider/model changes require quality evidence and configuration-level
rollback.

## 7. Rollout and Rollback

1. Land each concern with focused regression tests.
2. Run all local canonical quality gates.
3. Prepare release notes, exact production commands, and rollback SHA.
4. Ask for explicit approval before deployment or any production data mutation.
5. Deploy through the repository's established delivery path.
6. Read back the release SHA/version and run health/auth smoke tests.
7. Run bounded synthetic E2E only with approved test destinations; leave no
   synthetic pending escalation.
8. Apply escalation reconciliation separately, from an archived dry-run
   manifest, after explicit approval.
9. Roll back immediately on message duplication/loss, auth regression, health
   failure, or material answer-quality regression.

## 8. Acceptance Matrix

| Outcome | Evidence required | Beads |
|---|---|---|
| Debug exposure closed | unauthenticated regression plus authenticated/404 contract | `tj-9c94` |
| Zoho/batch failure safe | malformed-`200`, retry, exhaustion, and idempotency tests | `tj-p9ui` |
| Escalations reconciled | archived dry-run, approved apply, post-readback counts | `tj-ymi3` |
| Maintenance operational | script tests, installed-cron readback, first-run evidence | `tj-092y` |
| Health truthful | Redis/DB/version and HTTP `200`/`503` tests | `tj-38l5` |
| Failures visible | deterministic alert/metric tests and runbook | `tj-av22.1` |
| Latency improved safely | before/after phase metrics and regression suite | `tj-15m` |
| `501` ambiguity removed | per-route implement/retire decision and contract tests | `tj-av22.2` |
| Workspace truth restored | exact cleanup inventory and current handoff | `tj-rt42` |
| Release closed | full gates, approved prod evidence, stage closeout | `tj-av22.3` |

## 9. Approval Gates

The orchestrator must stop and ask before:

- deployment or any production/staging mutation;
- applying escalation reconciliation;
- sending a real Telegram/WhatsApp test;
- deleting worktrees, branches, remote refs, caches, or production data;
- changing credentials, scopes, vendor settings, or WABA templates;
- deciding a materially ambiguous public API compatibility policy.

Everything else that is reversible and local should proceed without waiting.
