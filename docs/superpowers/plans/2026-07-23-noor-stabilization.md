# Noor Production Stabilization — Implementation Plan

> **Execution contract:** complete Beads epic `tj-av22` using this plan and
> `docs/superpowers/specs/2026-07-23-noor-stabilization-design.md`. Follow
> test-driven development for behavior changes and the repository closeout
> contract before claiming completion.

**Goal:** eliminate the technical risks found in the 2026-07-23 audit and
produce a verified, observable Noor release without guessing business policy.

**Architecture:** staged stabilization. Close P1 security/message-loss paths
first, then operational state and visibility, then evidence-based performance
and API-contract cleanup, and finally one controlled release.

**Primary stack:** Python, FastAPI, SQLAlchemy async, Redis/ARQ, httpx, pytest,
Ruff, Mypy, Docker/cron, existing Telegram notifications.

## Execution Ledger

| Order | Work item | Beads | Depends on | Production approval |
|---:|---|---|---|---|
| 0 | Planning package | `tj-g6m4` | — | No |
| 1 | Remove Redis debug exposure | `tj-9c94` | — | Deploy only |
| 2 | Harden Zoho OAuth and inbound retry | `tj-p9ui` | — | Deploy only |
| 3 | Make health truthful | `tj-38l5` | — | Deploy only |
| 4 | Audit/reconcile escalations | `tj-ymi3` | policy tests | Yes, before apply |
| 5 | Repair Docker maintenance | `tj-092y` | script tests | Yes, before install/apply |
| 6 | Add failure visibility | `tj-av22.1` | OAuth/health contracts understood | Real alert only |
| 7 | Measure and reduce latency | `tj-15m` | stable P1 message path | Live matrix only |
| 8 | Resolve public `501` contracts | `tj-av22.2` | consumer inventory | If compatibility is ambiguous |
| 9 | Reconcile local orchestration residue | `tj-rt42` | exact inventory | Yes, before deletion |
| 10 | Integrate, deploy, verify, close | `tj-av22.3` | all implementation tasks | Yes |

The user explicitly authorized visible spawned subagents on 2026-07-23.
The root orchestrator may delegate coherent workstreams when useful and chooses
the working shape from current evidence. Delegated work still follows the
repository's isolation, artifact, and review contracts.

## Candidate Delegation Map

This is an advisory decomposition map, not a required execution shape.
The orchestrator may combine, split, reorder, defer, or keep any stream local
based on current evidence, shared-file conflicts, context size, and material
benefit.

| Candidate domain | Beads | Likely ownership | Coordination consideration |
|---|---|---|---|
| API security and health | `tj-9c94`, `tj-38l5` | health route/schema, auth/dependency wiring, health tests | These tasks share API files and may be best handled together |
| Zoho and inbound reliability | `tj-p9ui` | OAuth clients, batch processing, worker/chat tests | High-risk cross-module behavior; use a focused agent if isolation helps |
| Operational state | `tj-ymi3`, `tj-092y` | escalation policy/scripts and maintenance scripts/runbook | Production apply remains a separate approval gate |
| Failure visibility | `tj-av22.1` | worker, notifications, summaries, monitoring tests | May overlap Zoho, escalation, health, or latency changes |
| Latency and quality | `tj-15m` | measured message/LLM/RAG path and regression tests | Start from evidence; coordinate any shared `worker`/`chat` edits |
| Public API contracts | `tj-av22.2` | inventory/quality routes, tests, docs | Compatibility ambiguity remains a user decision |
| Repository closeout | `tj-rt42`, `tj-av22.3` | integration, handoff, stage state, approved cleanup/release | Usually benefits from root-level system context |

### Delegation contract

When delegation is chosen, follow `AGENTS.md` and
`.codex/orchestrator.toml`: use visible spawned agents, Beads ownership,
write-heavy worktree isolation, bounded write zones, English prompts, tracked
artifacts, and root review of the actual diff and verification. Prompts should
state outcomes and hard boundaries while leaving implementation choices to the
worker. A completion event is evidence to review, not automatic acceptance.

## Task 0: Finalize the planning package

**Beads:** `tj-g6m4`

**Artifacts:**

- `docs/superpowers/specs/2026-07-23-noor-stabilization-design.md`
- `docs/superpowers/plans/2026-07-23-noor-stabilization.md`
- `docs/prompts/2026-07-23-noor-stabilization-orchestrator.md`
- `.codex/handoff.md`
- Beads epic `tj-av22`, children, and dependency edges

**Actions:**

1. Validate that every audit finding maps to one Beads child.
2. Validate that `tj-av22.3` depends on all implementation/cleanup children.
3. Confirm `bd dep cycles` is empty.
4. Remove the mistakenly created commercial-offer artifact.
5. Record the user's spawned-subagent authorization without prescribing the
   execution shape or scheduling-only dependencies.
6. Run prompt validation and process verification.
7. Close `tj-g6m4` only after the artifacts and Beads export are verified.

## Task 1: Remove the public Redis debug exposure

**Beads:** `tj-9c94`

**Files:**

- Modify: `src/api/v1/health.py`
- Inspect/modify if reusing internal auth: `src/api/deps.py`, `src/main.py`
- Test: `tests/test_api_health.py`
- Test or create: `tests/test_api_internal_auth.py`

**TDD steps:**

1. Add a failing test proving an unauthenticated caller cannot read
   `/api/v1/debug/redis` or any raw queue payload.
2. Decide from actual repo consumers whether to delete the route entirely
   (preferred if unused) or move it behind the existing internal/admin auth.
3. Implement the smallest solution. Do not create a new secret scheme solely
   for this endpoint.
4. Add a repository-wide test/search assertion that no public route returns raw
   Redis message values.
5. Run:

   ```bash
   uv run pytest tests/test_api_health.py tests/test_api_internal_auth.py -v --tb=short
   uv run ruff check src/api/v1/health.py tests/test_api_health.py
   ```

**Done when:** unauthenticated access is `404`, `401`, or `403` according to the
chosen contract; no response contains queue data; other health behavior remains
green.

## Task 2: Harden Zoho OAuth and inbound-batch recovery

**Beads:** `tj-p9ui`

**Files:**

- Create: `src/integrations/zoho_oauth.py`
- Modify: `src/integrations/crm/zoho_crm.py`
- Modify: `src/integrations/inventory/zoho_inventory.py`
- Modify as evidence requires: `src/services/chat.py`, `src/worker.py`
- Test: `tests/test_zoho_crm.py`
- Test: `tests/test_zoho_client.py`
- Test: `tests/integrations/test_zoho_inventory.py`
- Test: `tests/test_services_chat_batch.py`
- Test: `tests/test_worker.py`

**TDD steps:**

1. Add red tests for:
   - HTTP `200` JSON without `access_token`;
   - OAuth error JSON delivered with `2xx`;
   - invalid/non-object JSON;
   - token TTL clamping;
   - refresh-lock release on every failure;
   - transient failure retry and exhausted retry visibility;
   - replay of the same inbound batch without duplicate message/reply.
2. Introduce a shared typed OAuth parser/error. Keep secrets and response bodies
   out of exception messages.
3. Use it in CRM and Inventory clients; preserve token locking and cache
   behavior.
4. Trace the accepted-batch lifecycle through `src/services/chat.py` and
   `src/worker.py`. Ensure the job raises the correct retryable exception rather
   than acknowledging a lost batch.
5. Add bounded backoff and a terminal failure record/log/alert. Do not retry
   invalid credentials indefinitely.
6. Run:

   ```bash
   uv run pytest tests/test_zoho_crm.py tests/test_zoho_client.py tests/integrations/test_zoho_inventory.py tests/test_services_chat_batch.py tests/test_worker.py -v --tb=short
   uv run mypy src/integrations src/services/chat.py src/worker.py
   ```

**Done when:** the 2026-07-18 failure shape is a deterministic regression test,
no accepted batch silently disappears, replay is idempotent, and errors are
sanitized.

## Task 3: Make health truthful

**Beads:** `tj-38l5`

**Files:**

- Modify: `src/api/v1/health.py`
- Modify: `src/schemas/health.py`
- Modify: `src/api/deps.py` if a DB dependency is not already exposed
- Test: `tests/test_health.py`
- Test: `tests/test_api_health.py`

**TDD steps:**

1. Add red tests for healthy Redis+DB (`200`), failed Redis (`503`), failed DB
   (`503`), simultaneous failures, sanitized errors, and actual package version.
2. Resolve the version from installed/package metadata with one deterministic
   fallback suitable for tests.
3. Execute a minimal database liveness query using normal dependency injection.
4. Return `503` whenever a required dependency is unavailable. Preserve a
   structured response body for diagnosis.
5. Run:

   ```bash
   uv run pytest tests/test_health.py tests/test_api_health.py -v --tb=short
   ```

**Done when:** the endpoint cannot report HTTP success while the primary DB or
Redis is unavailable and the version matches the deployed package.

## Task 4: Audit and reconcile pending escalations

**Beads:** `tj-ymi3`

**Files:**

- Modify: `src/services/escalation_state.py`
- Modify/reuse: `scripts/escalation_guard.py`
- Create only if needed: `scripts/reconcile_pending_escalations.py`
- Test: `tests/test_escalation_state.py`
- Test: `tests/test_scripts_escalation_guard.py`
- Test: `tests/test_api_escalation.py`
- Document: operational runbook under `docs/`

**TDD steps:**

1. Encode the observed combinations as fixtures: active/pending, active/none,
   closed/resolved, and manual takeover, with old/recent variants.
2. Add red tests for classification, no-op repeat runs, exact-ID apply,
   transaction rollback, and suppression of real external alerts.
3. Implement read-only JSON/text audit output. Default to no writes.
4. Implement apply mode only for unambiguous transitions; require both an apply
   flag and an archived manifest/exact ID set.
5. Run the local/test database dry-run.
6. Prepare the production dry-run command and stop for explicit approval.
7. After approval, archive the dry-run, apply exactly that manifest, read back
   counts/state, and verify a second apply is a no-op.

**Done when:** every one of the 33 audited rows has a documented disposition,
but no production row is changed without approval.

## Task 5: Repair Docker maintenance

**Beads:** `tj-092y`

**Files:**

- Modify: `scripts/docker-maintenance.sh`
- Modify: `scripts/install-docker-maintenance-cron.sh`
- Test: `tests/test_scripts_docker_maintenance.py`
- Document: deployment/operations runbook

**TDD steps:**

1. Add red shell-behavior tests for absent log directories, duplicate
   installation, paths containing spaces, failed health verification, and
   conservative default flags.
2. Ensure directory creation happens before cron redirection can fail and the
   installer emits exactly one marked entry.
3. Add readback verification for the installed crontab and a non-destructive
   dry-run command.
4. Do not schedule `--aggressive`; do not delete volumes or running resources.
5. Stop for approval before installing the cron or applying cleanup on the VPS.
6. After approval, install, read back, run once conservatively, record before/
   after disk and Docker usage, and confirm health.

**Done when:** a first run succeeds with logs present, repeated installation is
idempotent, and canonical health remains green.

## Task 6: Add failure visibility

**Beads:** `tj-av22.1`

**Files (expected; adjust from evidence):**

- Modify: `src/worker.py`
- Modify/reuse: `src/integrations/notifications/escalation.py`
- Modify/reuse: `src/services/daily_summary.py`
- Test: `tests/test_worker.py`
- Test: `tests/test_telegram_notifications.py`
- Add/update: operations runbook

**TDD steps:**

1. Define safe event records for OAuth failure, exhausted ARQ job, queue
   staleness, escalation staleness, and maintenance staleness.
2. Add tests for thresholds, cooldown/deduplication, recovery, and redaction.
3. Reuse structured logging and the existing notification channel. Do not add a
   paid monitoring dependency.
4. Document owner, threshold, detection source, and remediation command for
   every signal.
5. Keep real Telegram delivery suppressed in tests and local verification.
6. Stop for approval before one real production alert test.

**Done when:** each critical failure has deterministic detection evidence and a
runbook, without secrets or PII.

## Task 7: Measure and reduce end-to-end latency

**Beads:** `tj-15m`

**Files:** select only after profiling; likely `src/services/chat.py`,
`src/llm/engine.py`, context/RAG modules, `src/worker.py`, and their existing
tests.

**Steps:**

1. Reopen the task's historical evidence and establish a current repeatable
   matrix covering simple FAQ, product search, multi-product comparison,
   quotation/order path, Arabic, and escalation.
2. Add phase timings for queue wait, context, model, tools/RAG, and outbound
   delivery. Never log message content or phone numbers.
3. Record baseline `p50`, `p95`, maximum, quality/correctness result, provider,
   and sample size.
4. Pick only bottlenecks supported by evidence. For each behavior change, write
   a failing performance/contract test first where deterministic.
5. Apply safe parallelism/caching/bounds one change at a time and remeasure.
6. Run product-search, media, quotation/order, language, escalation, and full
   regression suites.
7. Stop for approval before a live synthetic matrix.

**Done when:** approved live evidence reaches the design targets, or a named
external-provider blocker is documented with local improvements and no quality
regression.

## Task 8: Resolve incomplete `501` API contracts

**Beads:** `tj-av22.2`

**Files:**

- Inspect/modify: `src/api/v1/inventory.py`
- Inspect/modify: `src/api/v1/quality.py`
- Test: `tests/test_api_inventory.py`
- Test: `tests/test_api_quality.py`
- Inspect: frontend and external API documentation/consumers

**Steps:**

1. Inventory all consumers of the three routes and their documented auth/
   response contracts.
2. Record one decision per route: implement now or remove/deprecate.
3. If behavior is clearly defined by existing services, add red API contract
   tests and connect it with authorization, idempotency, and bounded status
   reporting.
4. If there is no consumer/defined behavior, remove or explicitly deprecate the
   route and update OpenAPI/docs/tests.
5. If compatibility is materially ambiguous, stop with the evidence and one
   concrete decision request rather than guessing.

**Done when:** no unexplained public `501` remains and existing order/quotation/
quality flows stay green.

## Task 9: Reconcile local orchestration residue

**Beads:** `tj-rt42`

1. Use the `cleanup-audit` skill and produce an exact inventory of worktrees,
   local/remote branches, dirty files, completion-inbox state, and caches.
2. Classify each item as keep, archive, safe remove, or needs user decision.
3. Preserve every unknown or dirty user artifact.
4. Ask for approval before deleting worktrees/branches or any material cache.
5. After approval, use the repository cleanup entrypoint where applicable and
   verify `git worktree list`, branches, and handoff truth.

**Done when:** the workspace state is explainable and current, with no
unapproved destructive cleanup.

## Task 10: Integrate, release, verify, and close

**Beads:** `tj-av22.3`

1. Confirm all blocking children are closed or explicitly blocked by a named
   external decision. Do not close the epic around unresolved technical P1s.
2. Run focused tests for each workstream, then canonical full gates:

   ```bash
   uv run ruff check src/ tests/
   uv run ruff format --check src/ tests/
   uv run mypy src/
   env DYLD_FALLBACK_LIBRARY_PATH="${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}" uv run pytest tests/ -v --tb=short
   scripts/orchestration/run_process_verification.sh
   ```

3. Review diff for secrets, PII, debug routes, accidental product-policy
   changes, and unrelated user files.
4. Update durable docs and report
   `docs-reviewed: updated` with exact paths. Graphify is not configured, so
   report `graph-reviewed: no-change-needed` with that reason.
5. Prepare a release/rollback checklist and stop for explicit deployment
   approval.
6. After approval, deliver through the established main-only flow, read back
   deployed SHA/version, and run:
   - public debug route auth/absence check;
   - Redis+DB health check;
   - OAuth/inbound worker smoke without exposing data;
   - maintenance status;
   - escalation post-state readback;
   - bounded synthetic E2E with cleanup;
   - latency matrix.
7. Update Beads, `.codex/handoff.md`, and
   `.codex/stages/tj-av22/summary.md`.
8. Run:

   ```bash
   scripts/orchestration/check_stage_ready.py tj-av22
   scripts/orchestration/run_stage_closeout.py --stage tj-av22
   ```

9. Perform only approved cleanup and verify the final workspace/delivery state.

## Stop Conditions

Stop and ask the user when:

- production/staging mutation or deployment is next;
- a real WhatsApp/Telegram message would be sent;
- escalation rows or other production data would be changed;
- credentials/scopes/vendor configuration must change;
- compatibility for a public API route is materially ambiguous;
- dirty/unknown worktrees or branches would be deleted;
- a P1 cannot be fixed without an external owner or secret.

Do not stop for reversible local implementation, tests, documentation, or Beads
updates when the requirement is already specified here.
