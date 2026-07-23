---
schema_version: orchestration-artifact/v3
artifact_type: review-report
stage_manifest: .codex/stages/tj-av22/stage-manifest.json
stream_owner: stabilization-reviewer
orchestration_level: integration
scope_kind: product_slice
immediate_consumer: root-orchestrator
public_facade: n/a
bounded_acceptance: independent security reliability privacy and operations review of ee7a250
non_goals:
  - product-code changes
  - live-service calls
  - deployment or production mutation
  - review of later root correction commits
evidence:
  - none
task_id: tj-av22.5
epic_id: tj-av22
stage_id: tj-av22
session_id: tj-av22-stabilization-review
milestone: noor-stabilization-independent-review
milestone_status: replan-required
agent_type: worker
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: independent high-risk security reliability concurrency and production-safety review
repo: treejar
branch: codex/tj-av22-review
base_branch: codex/tj-av22-stabilization
base_commit: ee7a2508306b6332477e7cac678638ca9ec6d3e5
worktree: /home/me/code/treejar/.worktrees/tj-av22-stabilization/.worktrees/tj-av22-review
write_zone:
  - .codex/stages/tj-av22/artifacts/tj-av22.5.md
success_criteria:
  - findings are prioritized with exact evidence impact and practical corrections
  - production-only proof is separated from local defects
  - no product code or external state is changed
selected_docs:
  - AGENTS.md
  - .codex/orchestrator.toml
  - .codex/handoff.md
  - docs/superpowers/specs/2026-07-23-noor-stabilization-design.md
  - docs/superpowers/plans/2026-07-23-noor-stabilization.md
  - docs/operations-runbook.md
selected_skills:
  - code-review
  - verification-before-completion
  - format-commit-message
selected_agents:
  - built-in-worker
catalog_candidates:
  - none
parallel_group: stabilization-review
depends_on_streams:
  - api-health
  - zoho-inbound
  - ops
  - runtime-observability
parallel_decision: parallel
status: returned
delivery_method: merge
accepted_by_orchestrator: yes
cleanup_status: blocked
cleanup_notes: review accepted and integrated; dry-run classifies the isolated worktree and branch as cleanup candidates, but deletion awaits explicit user approval after delivery
risk_level: high
verification_tier: integration
risk_tags:
  - security
  - concurrency
  - retry
  - state-transition
  - idempotency
  - rollback
  - data
  - public-api
affected_surfaces:
  - backend
  - database
  - data
  - api
invariants:
  - state-transition
  - idempotency
  - rollback
  - test-matrix
docs_impact: behavior
docs_reviewed: n/a
docs_review_notes: review-only stream; findings identify code and deployment-contract corrections
verification:
  - focused stabilization pytest matrix - 116 passed: passed
  - full pytest after local frontend dependency bootstrap - 1479 passed and 19 skipped: passed
  - uv run ruff check src/ tests/: passed
  - uv run ruff format --check src/ tests/: passed
  - uv run mypy src/: passed
  - scripts/orchestration/run_process_verification.sh: passed
  - generic inbound failure read-only probe - zero requeue and zero quarantine writes: passed
  - fabricated active-pending reconciliation manifest read-only probe - validator accepted unsafe action: passed
changed_files:
  - .codex/stages/tj-av22/artifacts/tj-av22.5.md
explicit_defers:
  - tj-av22.3 - deployment production readback live OAuth replay escalation apply cron installation Telegram delivery and synthetic E2E remain approval-gated
  - tj-15m.6 - latency implementation and local evidence were not present in the reviewed base
  - tj-rt42 - destructive repository cleanup remains approval-gated
---

# Findings

No P0 finding was identified. Four P1 findings block acceptance of the reviewed
commit. The verdict for `ee7a250` is **NEEDS WORK**.

## P1 — accepted inbound batches can still disappear outside one typed OAuth path

- **Evidence:** `src/services/chat.py:520-525` destructively pops every raw
  message before processing. Only `ZohoOAuthError` is preserved through
  requeue/quarantine at `src/services/chat.py:534-587`; the generic branch at
  `src/services/chat.py:588-590` only re-raises. The concrete concurrent-refresh
  timeout is still an ordinary `RuntimeError` at
  `src/integrations/crm/zoho_crm.py:97-105` and
  `src/integrations/inventory/zoho_inventory.py:267-275`. Missing
  `WAZZUP_CHANNEL_ID` returns successfully after the pop at
  `src/services/chat.py:605-611`. A read-only probe forced a generic processing
  error and observed zero `lpush` and zero quarantine `rpush` calls. Inspection
  of the installed ARQ worker shows ordinary exceptions finish as failed jobs;
  only `Retry`/`RetryJob` are automatically retried.
- **Impact:** database, parsing, provider, lock-contention, or configuration
  failures can leave an accepted webhook payload in neither the live queue nor
  quarantine. The job result records failure, but its arguments contain only
  `chat_id`, so the raw customer payload cannot be replayed. This violates the
  required processed/retryable/terminal outcome invariant and preserves the
  original message-loss class.
- **Correction:** introduce one common batch lease/outcome boundary around all
  failures. Keep raw messages in a processing list or durable batch envelope
  until commit; classify retryable exceptions into bounded `Retry`; quarantine
  terminal and exhausted failures; make missing required configuration a
  visible terminal outcome. Convert refresh-lock exhaustion to a typed
  retryable OAuth error. Add regressions for DB failure, lock timeout, invalid
  configuration, and terminal quarantine-write failure.

## P1 — the refresh lock can be released by a worker that no longer owns it

- **Evidence:** CRM acquires the lock with the shared literal value `"1"` at
  `src/integrations/crm/zoho_crm.py:89-95` and unconditionally deletes it at
  `src/integrations/crm/zoho_crm.py:137-139`. Inventory repeats the pattern at
  `src/integrations/inventory/zoho_inventory.py:258-265` and
  `src/integrations/inventory/zoho_inventory.py:307-309`. The lease is 20
  seconds, while only the HTTP request is bounded to 15 seconds; token-cache
  writes, scheduling delay, and cleanup are outside that bound.
- **Impact:** if the original lease expires and another worker acquires the same
  key, the old owner can delete the new owner's lock. Multiple token refreshes
  can then overlap, defeating the concurrency guarantee and creating another
  path to transient authentication failure.
- **Correction:** store a unique owner token and release through atomic
  compare-and-delete (Lua or an equivalent proven lock primitive). Either renew
  the lease while refreshing or bound the complete critical section. Add a
  regression where owner A expires, owner B acquires, and owner A is unable to
  delete B's lease.

## P1 — exact-ID apply accepts actions the audit classifier would never emit

- **Evidence:** `scripts/escalation_guard.py:179-223` validates the self-digest,
  UUID shape, pending-to-resolved transition, and unchanged conversation fields,
  but does not require an action to correspond to `records` or to
  `classify_pending_escalation`. `scripts/escalation_guard.py:284-308` checks
  only those supplied expected/target states before mutation. A read-only probe
  built an empty-record manifest containing a fabricated
  active/pending-human-owned action, recomputed the self-digest, and
  `_validated_actions` accepted it.
- **Impact:** an edited or independently constructed manifest can resolve a
  valid human-owned pending escalation while satisfying every apply guard.
  Transactionality and exact IDs limit blast radius but do not enforce the
  central rule that only unambiguous stale combinations are automatically
  reconciled.
- **Correction:** after locking each database pair, run the canonical
  classifier again using the current row, conversation, configured threshold,
  and current time; refuse every action whose result is not
  `EscalationAction.RESOLVE`. Also validate manifest record/action consistency.
  Add a test proving a recomputed active/pending action is rejected before any
  mutation.

## P1 — the stage privacy invariant is not true for inbound runtime logs

- **Evidence:** `src/api/v1/webhook.py:171-182` logs manager/client names,
  `chatId`, and the first 100 characters of message text.
  `src/services/chat.py:599-600` and multiple nearby lifecycle logs emit the raw
  `chat_id`; `src/services/chat.py:724-727` logs up to 200 characters of voice
  transcription. These calls predate the stabilization diff, but remain on the
  exact inbound path the approved specification declares privacy-safe.
- **Impact:** customer identifiers and message/transcription content are copied
  into long-lived application logs. Anyone with log access receives materially
  more customer data than the new monitoring contract promises, and forwarding
  logs during an incident can disclose PII.
- **Correction:** use a non-reversible bounded operational correlation ID
  (existing `batch_id` where available), role/type/count metadata, and error
  classes only. Remove message/transcription snippets and raw phone/chat IDs
  from ordinary logs, then add capture-based privacy tests across webhook,
  text-batch, and voice paths.

## P2 — the canonical worker cannot see the host maintenance heartbeat

- **Evidence:** `src/core/config.py:100-106` defaults the heartbeat to
  `/opt/noor/logs/maintenance/docker-maintenance.status`, which the host cron
  writes. The runtime image works under `/app` (`Dockerfile:37-77`), and the
  `worker` service has no bind or named volume in `docker-compose.yml:24-34`.
  The collector test at `tests/test_runtime_monitoring.py:127-193` injects a
  temporary file and therefore does not exercise deployment topology.
- **Impact:** in the canonical Compose deployment the monitor cannot observe a
  successful host cron run. It will remain `maintenance_heartbeat_missing` (or
  read an unrelated container-local path), producing permanent false alarms
  and no real missed-run detection.
- **Correction:** mount the host maintenance directory read-only into the
  worker at an explicit container path and configure that path, or publish the
  heartbeat through an existing shared store. Add a Compose/deployment contract
  test linking cron output and worker input.

## P2 — quarantined customer payloads have no retention boundary

- **Evidence:** terminal raw messages are appended at
  `src/services/chat.py:558-575`. No expiry, bounded length, deletion workflow,
  or retention setting exists for
  `wazzup:inbound:quarantine:<batch_id>`. `docs/operations-runbook.md:169-174`
  correctly labels the values restricted customer content but does not define
  retention or disposal.
- **Impact:** every terminal batch can retain customer messages and identifiers
  indefinitely in Redis, increasing privacy exposure and memory usage.
- **Correction:** set an explicit configurable TTL atomically with quarantine
  creation, document owner/replay/delete handling, and test expiry plus
  idempotent repeated quarantine writes.

## P2 — optional Telegram delivery can consume cooldown without delivering

- **Evidence:** `src/services/runtime_monitoring.py:425-432` claims the Redis
  cooldown before calling the notification wrapper.
  `src/services/notifications.py:618-632` swallows send exceptions and returns
  no success result; an unconfigured client also silently returns `None` at
  `src/integrations/notifications/telegram.py:41-59`.
- **Impact:** with Telegram delivery enabled but missing/broken configuration,
  a signal is marked claimed for 30 minutes even though no notification was
  sent. Structured logs remain, but the optional alert channel can fail
  silently at the exact moment it is needed.
- **Correction:** make delivery return an explicit outcome, validate destination
  configuration before enabling, and release/shorten the claim after failed
  delivery while retaining race-safe deduplication. Test no-op, exception, and
  success paths.

# Summary

The public raw-Redis route is removed, health now checks Redis and the database
with sanitized `503` semantics, OAuth responses have a shared sanitized parser,
public `501` stubs are retired, and the maintenance/escalation tooling is
substantially safer than the baseline. The focused and full local suites pass.

Those positive changes do not make the reviewed commit releasable: message
preservation is incomplete, lock ownership is unsafe, escalation apply does not
enforce its classifier, and the declared log-privacy boundary is still false.
The maintenance heartbeat and two secondary observability/privacy contracts
also need correction.

# Scope / Routing

This was a surgical review of 63 files (`+5022/-287`) between
`main@89f9a560` and `codex/tj-av22-stabilization@ee7a250`, emphasizing the
high-risk paths named in the assignment. Git history was inspected for the
changed files and for removed safety behavior. No external documentation was
decisive; repository contracts and the installed ARQ implementation were
sufficient. No product code, production service, paid API, or external message
was touched.

The prompt's strict write boundary prevented creating separate Beads findings.
The root orchestrator should track accepted corrections in the existing stage
before closing `tj-av22.5` or the stabilization epic.

# Verification

- Focused stabilization matrix: `116 passed`.
- Full repository suite after installing the worktree's locked frontend
  dependencies: `1479 passed, 19 skipped`.
- The first full-suite attempt had seven environment-only failures because this
  new worktree lacked `frontend/admin/node_modules`/`esbuild`; `npm ci` restored
  the locked dependencies and both the affected 11-test file and full rerun
  passed.
- Ruff check: passed.
- Ruff format check: passed (`297 files already formatted`).
- Mypy: passed (`160 source files`).
- Orchestration process verification: passed.
- `git diff --check`: passed.
- Read-only generic-failure probe reproduced zero requeue/quarantine writes.
- Read-only fabricated-manifest probe reproduced classifier-invalid action
  acceptance.

# Delivery / Cleanup

This artifact is returned on `codex/tj-av22-review` for root triage. It does not
accept or merge the implementation. The isolated worktree remains intact as
requested.

# Risks / Follow-ups / Explicit Defers

Even after local defects are corrected, release claims require the explicit
approval-gated evidence owned by `tj-av22.3`: deployed SHA/version readback,
production debug-route absence, Redis+DB health, real token refresh and bounded
affected-batch recovery, the 33-row escalation dry-run/manager disposition,
cron installation and heartbeat readback, optional Telegram delivery, and
bounded WhatsApp/synthetic E2E.

Latency work (`tj-15m.6`) was still running and was not in this review base, so
neither the local before/after profile nor the approved live target matrix is
claimed. Repository cleanup (`tj-rt42`) also remains an explicit destructive
approval gate.
