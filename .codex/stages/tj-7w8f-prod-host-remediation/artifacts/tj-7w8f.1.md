---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-7w8f-prod-host-remediation/stage-manifest.json
stream_owner: prod-noor-host-worker
orchestration_level: slice_acceptance
scope_kind: foundation
immediate_consumer: root-orchestrator production host remediation
public_facade: https://noor.starec.ai/api/v1/health
bounded_acceptance: root-owned logrotate repair plus Noor host and public health verification
non_goals:
  - no production mutation, service restart, swapoff, cleanup, deploy, paid call, or client-log content read in this stream
evidence:
  - none
task_id: tj-7w8f.1
epic_id: tj-7w8f
stage_id: tj-7w8f-prod-host-remediation
session_id: n/a
milestone: production-host-maintenance-health
milestone_status: accepted
agent_type: custom
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: production host diagnosis inherited the orchestrator model and used the devops_engineer role because no override was authorized
repo: treejar
branch: codex/prod-noor-host-remediation
base_branch: main
base_commit: 25598101f33f47c9d1117499daeb1f4a02928046
worktree: /home/me/code/treejar/.worktrees/prod-noor-host
write_zone:
  - .codex/stages/tj-7w8f-prod-host-remediation/artifacts/tj-7w8f.1.md
success_criteria:
  - identify every included owner of the Noor nginx log paths and the exact duplicate mechanism
  - measure log size and activity without reading client-log content
  - attribute process swap and determine whether current pressure justifies a reset
  - provide a minimal root-owned repair, rollback, and focused verification runbook
  - prove Noor public health and container stability before and after read-only diagnosis
selected_docs:
  - AGENTS.md
  - .codex/orchestrator.toml
  - .codex/handoff.md
  - .codex/stages/tj-7w8f-prod-host-remediation/stage-manifest.json
  - .codex/stages/tj-7w8f-prod-host-remediation/summary.md
selected_skills:
  - orchestrator-stage
  - senior-devops
  - technical-premortem
selected_agents:
  - devops_engineer
catalog_candidates:
  - none
parallel_group: prod-noor-host-maintenance
depends_on_streams:
  - none
parallel_decision: parallel
status: returned
delivery_method: cherry-pick
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: dedicated worktree and merged local branch removed by the stage cleanup entrypoint
risk_level: high
verification_tier: slice_acceptance
risk_tags:
  - rollback
  - state-transition
affected_surfaces:
  - backend
invariants:
  - rollback
  - test-matrix
docs_impact: ops-deploy
docs_reviewed: no-change-needed
docs_review_notes: this artifact is the bounded operational handoff; stable application and operator documentation were not changed
verification:
  - "curl --fail --silent --show-error --max-time 15 https://noor.starec.ai/api/v1/health before diagnosis": passed
  - "ssh noor-server logrotate inclusion, config metadata, user-level debug, unit state, and journal readback": passed with duplicate reproduced; root-only debug unavailable to noor-dev
  - "ssh noor-server two-snapshot nginx log metadata, filesystem, unit, process, and mount readback": passed
  - "ssh noor-server free, meminfo, pressure, vmstat, per-process VmSwap, container stats/state, OOM journal, and sysstat history": passed
  - "ssh noor-server sudo -n -l command-name boundary readback": passed
  - "curl plus Noor container state, PSI, and vmstat after diagnosis": passed
  - "python3 scripts/orchestration/validate_artifact.py .codex/stages/tj-7w8f-prod-host-remediation/artifacts/tj-7w8f.1.md": passed
changed_files:
  - .codex/stages/tj-7w8f-prod-host-remediation/artifacts/tj-7w8f.1.md
explicit_defers:
  - swap reset is explicitly not recommended on current evidence; investigate custdev-whisper memory lifecycle separately only if sustained pressure appears
---

# Summary

Read-only diagnosis confirmed one configuration defect and no current memory
incident on the shared production host `noor-hetzner`.

- Logrotate root cause is confirmed: `/etc/logrotate.conf` includes every file in
  `/etc/logrotate.d`; `/etc/logrotate.d/nginx` owns
  `/var/log/nginx/*.log`, while `/etc/logrotate.d/noor` declares
  `noor.access.log` and `noor.error.log` a second time. Logrotate reports both as
  duplicate entries, skips the redundant `noor` block, and exits 1.
- The smallest safe fix is to preserve `/etc/logrotate.d/noor` as a mode-`0600`
  root-only rollback copy and remove only that file from the included directory.
  The existing nginx wildcard remains the single owner; no log file is removed
  or truncated.
- Swap is full but not under current pressure. Of 2,096,924 KiB used swap,
  1,779,116 KiB (84.8%) belongs to the Uvicorn process in the neighboring
  `custdev-whisper-1` container, running since 2026-04-04. Noor app and worker
  use 0 KiB swap. A swap reset is not justified and is deliberately excluded.
- Noor was healthy before and after diagnosis at release
  `7e21de2b04611065e75936d0281e7aed55e0b2f3`; Redis and PostgreSQL were healthy,
  and all five Noor containers retained restart count 0 and `OOMKilled=false`.

Verdict: **GO WITH CONDITIONS** for the logrotate-only root-owned repair below;
**NO-GO** for `swapoff` or workload restarts on current evidence.

Root outcome supersession (2026-08-27): the guarded logrotate repair was later
completed with a protected rollback copy. Privileged validation, a successful
`logrotate.service` run, active timer readback, and unchanged Noor health all
passed. The runbook below is retained as historical worker evidence, not pending
current work.

# Scope / Routing

Operational boundary: host systemd logrotate timer/service ->
`/etc/logrotate.conf` include -> nginx/noor rotation definitions -> host nginx
master and `/var/log/nginx` files. The memory boundary is shared-host RAM/swap ->
container processes -> Noor health. Neighboring relay, Polska job repair, Wazzup,
deployment, Docker cleanup, client-log contents, and workload restarts are outside
this stream.

Access boundary is also confirmed. `noor-dev` can read the world-readable
logrotate configuration, journal, `/proc`, sysstat, and Docker state. Its
`sudo -n -l` permits named Docker/systemctl/journalctl/nginx commands, but does
not permit `logrotate`, `install`, `cp`, `mv`, `rm`, or `tee` for
`/etc/logrotate.d`. A generic `sudo -n` read therefore asks for a password.
Editing the logrotate owner and running privileged logrotate debug require a
root owner; `noor-dev` must not try to work around this boundary.

## Confirmed evidence

- `/etc/logrotate.d/nginx` (root:root, `0644`, unchanged since 2023-11-30) uses
  `/var/log/nginx/*.log`, daily, rotate 14, compress/delaycompress, create
  `0640 www-data adm`, then `invoke-rc.d nginx rotate`.
- `/etc/logrotate.d/noor` (root:root, `0644`, dated 2026-03-31) repeats the two
  Noor paths with the same retention/create policy and a host nginx USR1 hook.
- User-level `logrotate --debug /etc/logrotate.conf` reproduces both duplicate
  errors. It also reports expected permission failures for root state/euid, so
  it proves inclusion/root cause but is not the final privileged acceptance.
- Journal entries from 2026-08-20 through 2026-08-27 show the same duplicate
  pair and `logrotate.service` exit status 1 each day. The timer remains active
  and next fires at 2026-08-28 00:00 UTC.
- The generic owner is actively rotating Noor logs: `noor.access.log.1` is from
  2026-08-26 and compressed generations 2 through 14 exist. Current
  `noor.access.log` was 176,370 bytes and `noor.error.log` 7,260 bytes.
- The busiest current host nginx log grew from 127,902,940 to 127,959,861 bytes
  in 10 seconds; the API proxy log grew 14,740 bytes. The largest uncompressed
  prior generation is 358,839,985 bytes. The filesystem is 59% used with about
  120 GiB available, so there is no immediate disk-pressure incident.
- Host nginx is active. The Noor nginx container has no `/var/log/nginx` mount;
  it mounts only `/opt/noor/nginx` configuration. This confirms the rotation
  target belongs to the host nginx plane, not the Noor container.
- Current memory: 15.2 GiB total, about 8.6 GiB available, 2.0 GiB swap used,
  swappiness 10. Ten one-second `vmstat` samples had `si=0`, `so=0`, no blocked
  tasks, 94-95% idle CPU; memory PSI ended at `some/full avg10=0.00` and
  `avg60=0.00`.
- Noor container swap totals were app 0, worker 0, database 17,352 KiB, nginx
  15,856 KiB, and Redis 2,040 KiB. The dominant swap owner is the old
  `custdev-whisper-1` Uvicorn at 1,779,116 KiB; the next largest is Polska Qdrant
  at about 111 MiB.
- Sysstat history for 2026-08-20 through 2026-08-26 shows daily average one-minute
  load 0.18-0.24 and average memory use 34.3-37.7%, with at least 8.4 GiB
  available. On 2026-08-27 through 06:00 UTC, average load was 1.32, one sample
  reached 8.83 on 8 CPUs, maximum memory use was 42.32%, minimum available RAM
  was 7.95 GiB, and average swap-in/out was only 0.26/0.29 pages per second.
- No kernel OOM entry was found since 2026-08-01. All inspected containers report
  restart count 0 and `OOMKilled=false`.

## Root cause and risk classification

| Failure / risk | Evidence | Mechanism and signal | Disposition |
| --- | --- | --- | --- |
| Daily logrotate service is failed | Confirmed | A wildcard and two explicit paths are parsed in one include graph; duplicate errors and rc=1 repeat daily | Repair now, logrotate-only |
| Noor logs could become unowned after repair | Dismissed on inspected facts | Removing only `noor` leaves `/var/log/nginx/*.log`; existing generations prove it rotates Noor paths | Verify privileged debug before service start |
| Removing generic nginx ownership could regress other sites | Confirmed risk of the alternative | Generic block owns all host nginx logs and carries the package-supported rotate hook | Do not edit the generic block |
| Full swap means an active memory incident | Dismissed on current and historical evidence | High available RAM, near-zero PSI/churn, no OOM/restarts; occupancy is cold pages, predominantly one old neighbor | No swap reset |
| Future pressure could be masked by full swap | Plausible | A later working-set increase would have less eviction headroom | Monitor PSI, `si/so`, available RAM, OOM; open a separate custdev-whisper lifecycle task if sustained |
| `swapoff` causes latency or OOM | Plausible and avoidable | It would page roughly 2 GiB back into RAM and touch a neighboring four-month-old process for no observed benefit | Explicitly exclude |
| Operator exceeds sudo boundary | Confirmed | `noor-dev` cannot edit `/etc/logrotate.d` or run privileged logrotate debug | Root owner executes file/debug steps; no permission workaround |

# Verification

## Proposed root-owned logrotate repair

Run sequentially in a root shell only after a fresh public health check. The
fixed backup path and `test ! -e` guard prevent accidental overwrite.

```bash
curl --fail --silent --show-error --max-time 15 \
  https://noor.starec.ai/api/v1/health

test -f /etc/logrotate.d/noor
grep -nE '^/var/log/nginx/\*\.log' /etc/logrotate.d/nginx
/usr/sbin/logrotate --debug /etc/logrotate.conf

test ! -e /root/treejar-rollback/tj-7w8f.1-before-logrotate-noor
/usr/bin/install -d -m 0700 -o root -g root \
  /root/treejar-rollback/tj-7w8f.1-before-logrotate-noor
/usr/bin/install -m 0600 -o root -g root /etc/logrotate.d/noor \
  /root/treejar-rollback/tj-7w8f.1-before-logrotate-noor/noor
/usr/bin/cmp -s /etc/logrotate.d/noor \
  /root/treejar-rollback/tj-7w8f.1-before-logrotate-noor/noor
/usr/bin/rm -- /etc/logrotate.d/noor

/usr/sbin/logrotate --debug /etc/logrotate.conf
/usr/bin/systemctl start logrotate.service
/usr/bin/systemctl show logrotate.service logrotate.timer \
  -p Id -p ActiveState -p SubState -p Result -p ExecMainStatus \
  -p LastTriggerUSec -p NextElapseUSecRealtime --no-pager
/usr/bin/journalctl -u logrotate.service --since '-5 minutes' \
  --no-pager -o short-iso

curl --fail --silent --show-error --max-time 15 \
  https://noor.starec.ai/api/v1/health
/usr/bin/docker inspect noor-app-1 noor-worker-1 noor-nginx-1 \
  noor-db-1 noor-redis-1 \
  --format '{{.Name}}|status={{.State.Status}}|restart={{.RestartCount}}|oom={{.State.OOMKilled}}'
```

Pass condition: privileged debug contains no duplicate or other error;
`systemctl start` exits 0; service `Result=success`/`ExecMainStatus=0`; timer stays
active; public health remains `ok` on the same release; Noor restart counts and
OOM flags remain unchanged. `systemctl start` is preferred over `logrotate -f`:
the normal state-aware service path was already due today, while forcing every
host nginx log to rotate again would add risk without better proof.

Do not run `swapoff`, `swapon`, or restart any container for this task. The
appropriate focused observation path, if root wants another preflight window,
is read-only:

```bash
free -h
cat /proc/pressure/memory
vmstat 1 60
sar -W 1 60
```

Escalate to a separate `custdev-whisper-1` investigation only if swap-in/out or
memory PSI becomes sustained, available RAM materially falls, or OOM/latency
appears. Full occupancy alone is not a reset trigger.

## Rollback

Rollback trigger: the privileged debug loses the nginx owner, the service start
returns a new error attributable to removing `noor`, or Noor health/restart/OOM
state changes during the bounded repair.

```bash
test ! -e /etc/logrotate.d/noor
/usr/bin/install -m 0644 -o root -g root \
  /root/treejar-rollback/tj-7w8f.1-before-logrotate-noor/noor \
  /etc/logrotate.d/noor
/usr/bin/cmp -s /etc/logrotate.d/noor \
  /root/treejar-rollback/tj-7w8f.1-before-logrotate-noor/noor
/usr/sbin/logrotate --debug /etc/logrotate.conf
curl --fail --silent --show-error --max-time 15 \
  https://noor.starec.ai/api/v1/health
```

This restores the exact prior configuration, including its known duplicate
error. The repair itself neither deletes nor truncates logs. If the normal
service already rotated a file, its 14-generation retention remains intact;
do not attempt to rename log generations during rollback.

# Delivery / Cleanup

This worker stream changed only this tracked artifact. The root orchestrator
later performed and verified the production repair, accepted the evidence, and
removed the merged local branch and worktree.

# Risks / Follow-ups / Explicit Defers

- **Explicit defer:** do not reset swap. Current evidence says it would widen the
  blast radius without improving health. If pressure later becomes sustained,
  investigate and right-size the neighboring `custdev-whisper-1` process in its
  own ownership/rollback boundary.
