# Wazzup callback guard delivery

Task: `tj-vqcc`. External-writer follow-up: `tj-zc6k`.
Owner explicitly authorized production deployment, activation and immediate
bot-response verification on 2026-10-13. All timestamps below are UTC;
Moscow is UTC+3.

## Delivered behavior

`WAZZUP_WEBHOOK_GUARD_ENABLED=true` is effective in the new app and worker.
Startup and minute reconciliation enforce the approved callback
`https://noor.starec.ai/api/v1/webhook/wazzup`, retaining subscription flags.
Two identical reads precede a repair; a Redis ownership lease prevents overlap,
and provider readback determines success. Administrator alerts are bounded.
The sender/allowlist remains the approved test channel ending 0665, restore
mode stays enabled, and the other account channel remains excluded.

This recovers routing after a change. It does not revoke the unknown writer's
access or replay messages that reached the displaced audit receiver. The
provider does not expose a conditional-write contract, so the final read/PATCH
race remains. Identify and stop the external writer under `tj-zc6k`.

## Source and release checks

- Source implementation: `b360c2ed39e36ba4f95f81b58d48547a77cd5daf`.
- Delivered release: `d2de7b3f47260cbb88114fc42f8cb6c85e27832d`, which also
  repins the mutable current-handoff traceability digest.
- [Canonical CI run 38425819094](https://github.com/maslennikov-ig/treejar/actions/runs/38425819094)
  completed successfully: Ruff, Mypy (194 source files), 4470 passed / 27
  gated skips, separate pgvector integration 1 passed, and VPS deployment.
- Local focused acceptance already passed 89 guard, worker, deployment and
  outbound-safety tests; 54 manifest/repin tests passed after the metadata fix.
- Initial run 38424935724 correctly blocked deployment on four handoff digest
  failures. The official repin helper fixed mutable pins; frozen evidence was
  retained. No checks were bypassed.
- Delivery used the clean dedicated task worktree and fast-forward main push.
  Dirty primary checkout, unrelated worktrees and shared services were preserved.

## Runtime evidence

The canonical `--app-only` helper automatically preserves an existing verified
restore-mode worker: it builds both images, probes the candidate safety
fingerprint and recreates app/worker with the normal drain allowance. Its
candidate probe passed. New containers started at 16:03:53–54; deployment
reported success at 16:04:15. Host source, app health and worker image report
the exact release above. Database, Redis and nginx were retained.

Worker startup at 16:04:10 registered `reconcile_wazzup_webhook`; the startup
run finished at 16:04:11 with `status=ok`. The next minute run at 16:05:00
also returned `ok`. Fresh runtime/provider proof at 16:05:49 confirmed:

- Enabled guard and restore mode, bot enabled, empty inbound ARQ queue.
- Approved sender equals the outbound allowlist; protected settings fingerprint
  `57552c05d85e1647b59f56d07c77006bc55662af82cbc8add38491c263cbae0a`
  equals the predeployment fingerprint, including the Telegram inbound boundary.
- Correct callback and unchanged flags: `messagesAndStatuses=true`,
  `contactsAndDealsCreation=false`, `channelsUpdates=true`,
  `wabaTemplatesStatus=false`.
- Only expected restore-mode functions and cron jobs are registered.

At 16:05:44, a one-off process used the deployed guard against the real provider
and Redis. Its first two GET responses were modified **only in process memory**
to present a controlled invalid host. The real callback was checked before
each observation and was never diverted. The deployed repair path performed
exactly one real PATCH assigning the already-correct callback and identical
subscriptions; real GET readback passed and the lease was released. Result:
`restored`, three observed GETs, one PATCH, plus an independent final GET.
Administrator notification was disabled only in that one-off process to avoid
a false drift alert. This proves the deployed repair path with injected drift;
it is not evidence of a naturally observed competing overwrite.

During image build, brief SSH/HTTPS probe timeouts coincided with high global
memory/I/O pressure (15 GB of 15.6 GB RAM, full 2 GB swap). Internal Noor health
remained OK on the previous release. Access recovered and deployment completed;
no unrelated process was stopped or runtime resource policy changed.

## Bot-response acceptance

The earlier natural owner message from suffix 0921 on October 13 was received,
processed and answered with text plus three photos; the owner confirmed receipt
before this release. That evidence establishes the repaired route at that time.
It does not establish a fresh postdeployment customer round trip.

Postdeployment fresh natural-message acceptance is pending: the owner was asked
to send another message from suffix 0921 to bot suffix 0665. Do not promote
health, registration ping, injected drift or provider `sent` to actual receipt.
`tj-vqcc` stays in progress until the fresh round trip is checked.

## Recovery

Private rollback directory:
`/opt/noor/.hotfix-backups/tj-vqcc-20261013T154629Z`.
It retains the original `.env`, compose and activation receipt; files are 0600.
Old images are tagged `noor-guard-rollback-app:20261013t154629z` and
`noor-guard-rollback-worker:20261013t154629z`. Only the guard flag was added to
the runtime environment. To disable recovery, set the flag false and recreate
the worker under owner authority; the last correct callback remains in place.
No database, Redis queue or customer-history rollback is needed.

docs-reviewed: updated - runbook, runtime/source receipts and remaining live gate.
graph-reviewed: no-change-needed - no enabled task-owned graph; existing worker/provider boundary.
