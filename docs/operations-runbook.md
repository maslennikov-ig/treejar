# Noor Operations Runbook

This runbook covers pending-escalation reconciliation, Docker storage
maintenance, and privacy-safe runtime signals. Mutating workflows are
read-only by default. Do not run an apply, cron installation, monitoring config
change, external notification test, or rollback against the canonical VPS
until the exact production action has been approved.

## Pending escalation reconciliation

The audit reads pending escalation rows and current conversation state. Its JSON
contains UUIDs and state classifications, but no phone numbers, customer
messages, or escalation reason text.

### Archive a dry-run

Run from the deployed repository with production configuration only after
read-only production access has been approved:

```bash
umask 077
mkdir -p ops/escalation-manifests
manifest="ops/escalation-manifests/$(date -u +%Y%m%dT%H%M%SZ)-pending.json"
temporary="${manifest}.tmp"
uv run python scripts/escalation_guard.py > "$temporary"
python -m json.tool "$temporary" >/dev/null
mv "$temporary" "$manifest"
sha256sum "$manifest"
```

Default invocation does not commit or roll back a database transaction and does
not send Telegram alerts. Review these manifest sections:

- `summary`: total pending rows, safe action count, human-review count, and
  privacy-safe source counts;
- `records`: every audited row and its valid, stale, or ambiguous disposition;
- `actions`: the exact UUIDs eligible for automatic resolution.

Only two combinations enter `actions`: a pending row for a
closed/resolved conversation, or a pending row older than the configured
threshold for an active/unpaused (`none`) conversation. Active pending,
in-progress, manual-takeover, recent mismatches, and unknown combinations remain
human review.

The manifest embeds a deterministic digest. Any edit after archival makes apply
fail. Record the file checksum, embedded digest, exact action UUIDs, reviewer,
and approval together.

### Apply and read back

Apply requires both the explicit flag and an archived regular file:

```bash
uv run python scripts/escalation_guard.py \
  --apply \
  --manifest "$manifest" | tee "${manifest%.json}-apply.json"
```

The apply locks all exact rows, verifies every conversation ID and expected
state, and commits the set as one transaction. A missing row or changed state
rolls back the entire set. It changes only pending escalation-row status to
`resolved`; it never changes conversation state and sends no external alert.

Read the result's `changed_escalation_ids`, then run a new default audit and
compare counts. Repeat the exact apply command once: the expected idempotency
readback is an empty `changed_escalation_ids` and the same UUIDs under
`already_applied_escalation_ids`.

### Escalation rollback

An apply failure before commit rolls back automatically. A committed
reconciliation has no automatic inverse because changing a row back to pending
can reintroduce false manager work or bot-pause ambiguity. If the approved
manifest was wrong:

1. stop further reconciliation;
2. preserve the manifest, apply result, and post-apply audit;
3. identify the exact UUIDs and their pre-apply states from the archived
   manifest;
4. obtain manager and production-mutation approval for a separate exact-ID
   recovery transaction;
5. read back row status, conversation pause status, and pending counts.

Do not use a broad status update as rollback.

## Docker maintenance

The maintenance script never prunes volumes or running resources. Its default
mode is a preview; conservative apply bounds builder cache and prunes only
unused images older than the retention window.

### Preview

```bash
cd /opt/noor
bash scripts/docker-maintenance.sh
```

The preview runs read-only `df -h /` and `docker system df`, then prints the
planned prune commands. It does not execute either prune.

### Approved one-off apply

After explicit production cleanup approval:

```bash
bash scripts/docker-maintenance.sh --apply
```

Apply requires `docker`, `df`, and `curl`; records usage before and after; and
fails unless the local canonical health endpoint returns success. Do not add
`--aggressive` to scheduled maintenance. Aggressive one-off cleanup needs its
own exact approval.

### Install, read back, and roll back cron

Before an approved installation, archive the existing crontab:

```bash
umask 077
crontab -l > "ops/crontab-before-docker-maintenance.txt"
bash scripts/install-docker-maintenance-cron.sh
crontab -l
```

The installer creates `/opt/noor/logs/maintenance`, requires an executable
maintenance script, writes exactly one marked conservative entry, and reads the
crontab back. It reports `Verified Docker maintenance cron readback` only when
the begin marker, entry, and end marker each occur exactly once. If readback
fails, it restores the previous crontab automatically. Every approved apply
atomically writes
`/opt/noor/logs/maintenance/docker-maintenance.status` with only its final
success/failure state and completion timestamp. Deployment preserves the
runtime `logs/` directory, recreates `logs/maintenance` when absent, and mounts
that directory read-only into the worker at the same path so monitoring can
read the heartbeat without gaining write access to host logs.

Confirm the next approved run with:

```bash
tail -n 100 /opt/noor/logs/maintenance/docker-maintenance.log
tail -n 100 /opt/noor/logs/maintenance/docker-maintenance.cron.log
docker system df
df -h /
curl --fail --silent --show-error \
  http://127.0.0.1:8002/api/v1/health
```

To roll back a successful installation, restore the archived crontab and verify
the managed markers are absent:

```bash
crontab "ops/crontab-before-docker-maintenance.txt"
crontab -l
```

Restoring a crontab does not restore Docker data already pruned. Docker cleanup
is therefore approval-gated and intentionally conservative.

## Runtime failure visibility

`run_runtime_monitoring` is registered as a five-minute ARQ cron job but is
disabled by default. It reads only bounded operational metadata:

- failed ARQ result metadata retained during the previous hour;
- sanitized Zoho OAuth failure events from `zoho:oauth:failures`;
- count and oldest age of queued `process_incoming_batch` jobs;
- count of pending escalation rows older than 30 days;
- direct Redis and database probes;
- the Docker maintenance heartbeat described above.

Terminal inbound batches are also recorded in
`wazzup:inbound:failures` and their original raw payloads are retained under
`wazzup:inbound:quarantine:<batch_id>`. The first key is bounded sanitized
metadata. The quarantine key is restricted recovery data and can contain
customer content; never copy it into logs, tickets, alerts, or chat. Inspect or
replay it only as an exact, separately approved production recovery action.

### Default thresholds and ownership

| Signal | Default threshold | Destination | Owner | First action |
|---|---:|---|---|---|
| `arq_jobs_failed` | 1 failed result in 1 hour | structured log; optional Telegram | Noor operations | Inspect sanitized job result metadata and fix the cause before replay |
| `zoho_oauth_failed` | 1 refresh failure in 1 hour | structured log; optional Telegram | Noor operations | Check the error class and Zoho account configuration |
| `inbound_queue_backlog` | 25 queued inbound jobs | structured log; optional Telegram | Noor operations | Check worker capacity and queue trend |
| `inbound_queue_stalled` | oldest inbound job is 120s old | structured log; optional Telegram | Noor operations | Check worker health before replaying anything |
| `pending_escalations_stale` | 1 row older than 30 days | structured log; optional Telegram | Noor operations | Run and review the read-only escalation audit |
| `health_dependency_failed` | 1 failed Redis/DB probe | structured log; optional Telegram | Noor operations | Inspect dependency health before restart |
| `maintenance_failed` | last heartbeat reports failure | structured log; optional Telegram | Noor operations | Inspect logs and rerun only in dry-run mode |
| `maintenance_stale` | heartbeat is 26 hours old | structured log; optional Telegram | Noor operations | Verify cron installation and last run |
| `maintenance_heartbeat_missing` | status file absent | structured log; optional Telegram | Noor operations | Verify the configured status path and schedule |

Signals contain codes, numeric values, thresholds, sources, ownership, and
remediation only. They do not include tokens, credentials, phone numbers,
message bodies, raw job arguments, or OAuth response payloads. Each Telegram
signal uses a 30-minute Redis cooldown by default.

### Enable after approval

Enabling local collection and structured logs does not enable Telegram:

```dotenv
RUNTIME_MONITORING_ENABLED=true
RUNTIME_MONITORING_TELEGRAM_ENABLED=false
RUNTIME_MONITORING_ALERT_COOLDOWN_SECONDS=1800
RUNTIME_MONITORING_MAINTENANCE_STATUS_PATH=/opt/noor/logs/maintenance/docker-maintenance.status
```

After an approved deployment, read the worker logs for one complete monitoring
interval and confirm that collection succeeds. Set
`RUNTIME_MONITORING_TELEGRAM_ENABLED=true` only after the exact production
notification test has separate approval and the existing Telegram destination
has been verified. Roll back delivery by restoring it to `false`; collection
and structured logs can remain enabled.
