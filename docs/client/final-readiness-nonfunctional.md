# Final Readiness: Nonfunctional Evidence

Date: 2026-04-30
Scope: `tj-final27.8`
Runtime target: `https://noor.starec.ai`

This note records the current evidence for load, security, backup/restore,
rollback, monitoring, and SLA posture. It is intentionally limited to local
tests, local mocked load, and public read-only production health/auth checks.
No deploy, SSH, customer-data access, live WhatsApp traffic, broad production
load, or production mutation was performed for this check.

## Load and concurrency

Evidence command:

```bash
uv run python scripts/load_test_conversations.py \
  --conversations 50 \
  --messages-per-conversation 3 \
  --concurrency 10 \
  --processing-delay-ms 25 \
  --ack-budget-ms 50 \
  --p95-budget-ms 1000
```

Measured result from the bounded local/mock harness:

| Metric | Result |
|---|---:|
| Conversations | 50 |
| Messages | 150 |
| Concurrency cap | 10 |
| Max in-flight mocked processors | 10 |
| Failed batches | 0 |
| p95 mocked ack | 0.177 ms |
| p95 mocked total | 125.917 ms |
| Wall time | 126.202 ms |

Interpretation: the harness proves only the local queue/backpressure envelope
for mocked inbound batches. It does not prove end-to-end live latency through
Wazzup, OpenRouter, Zoho, PostgreSQL, Redis, and manager escalation paths.

## Security and auth boundaries

Fresh local tests cover these boundaries:

- `/dashboard/` rejects anonymous and `X-API-Key` requests without the admin
  session cookie.
- `/api/v1/admin/*` rejects anonymous and `X-API-Key` requests without the
  admin session cookie.
- `/api/v1/products/sync` and `/api/v1/admin/products/sync` reject internal
  API-key access without the admin session and do not enqueue sync work.
- `/api/v1/conversations/*` requires the internal API key and rejects missing
  or wrong keys.
- Wazzup webhook allowlist blocks disallowed origins before Redis queueing.

Public read-only production checks on 2026-04-30:

| Check | Result |
|---|---|
| `GET /api/v1/health` | `200`, `status=ok`, Redis `status=ok`, Redis latency `0.53 ms` |
| `GET /dashboard/` | `401`, `Admin authentication required` |
| `GET /admin/` | `302` to `/admin/login` |
| `GET /api/v1/admin/metrics/` | `401`, `Admin authentication required` |
| `GET /api/v1/conversations/` | `403`, `Invalid or missing API key` |

No tracked secrets were introduced. The tracked-secret scan used only tracked
files and found no high-signal private-key/API-token patterns; the only tracked
environment files are templates: `.env.example` and
`frontend/landing/.env.example`.

## Backup and restore posture

Application deploy rollback is implemented in `scripts/vps-deploy.sh`:

- release artifacts include `.release-sha` and `.release-run-id`;
- before replacing `/opt/noor`, the deploy script writes a rollback archive to
  `.hotfix-backups/deploy-<timestamp>-from-<sha>.tar.gz`;
- the script keeps the newest five deploy backups;
- restore is documented through the same deploy script with a selected backup
  archive and a health check.

Database backup posture is hosted-provider dependent. The developer guide
states the production database is Supabase Cloud managed PostgreSQL with auto
backups. This pass did not verify Supabase console settings or perform a
restore drill because that would require external account access and an
approved operational window.

## Rollback posture

Rollback is artifact-based, not git-checkout based on the VPS. The admin guide
documents restoring a selected `.hotfix-backups/deploy-*.tar.gz` archive via
`scripts/vps-deploy.sh --archive ... --target-dir /opt/noor --health-url ...`.
The deploy script runs a bounded health loop after service restart and fails
with recent app/worker/nginx logs when health does not recover.

## Monitoring posture

Available monitoring surfaces:

- public `/api/v1/health` reports app health and Redis dependency status;
- Docker logs for `app`, `worker`, and `redis` are the documented operator
  first-line diagnostics;
- the protected dashboard exposes operator metrics, weekly report generation,
  catalog sync, notification tests, payment reminder controls, AI Quality
  Controls, and manager-review queues;
- daily Telegram summary is documented as the operational heartbeat for daily
  conversation and quality metrics.

The current public health check proves service and Redis reachability only. It
does not replace full observability, alerting, uptime monitoring, or synthetic
business-journey checks.

## SLA limitations

Current readiness supports a controlled soft-launch SLA posture, not a hard
guarantee for every live conversation. Known limits:

- the local load result is mocked and excludes external dependency latency;
- live response time varies with LLM provider, Wazzup delivery, Zoho API
  latency, manager-review branches, and media/voice processing;
- no broad production load test was run in this pass;
- release SHA and Alembic head were not fetched from production in this pass
  because they are not exposed through public health/auth endpoints and SSH or
  database access was out of scope.

Recommended client decision: accept the current bounded evidence for final
readiness, or approve a separate controlled production load/restore drill with
explicit traffic limits, timing window, and rollback owner.
