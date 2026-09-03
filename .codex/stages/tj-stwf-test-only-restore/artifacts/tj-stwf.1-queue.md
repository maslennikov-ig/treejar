---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-stwf-test-only-restore/stage-manifest.json
stream_owner: retained_queue_safety
orchestration_level: release
scope_kind: product_slice
immediate_consumer: root-release-integrator
public_facade: wazzup-inbound-worker-boundary
bounded_acceptance: retained-redis-preserved-without-replay-and-app-before-worker-gate
non_goals:
  - redis-or-database-mutation-during-this-review
  - retained-payload-export-or-customer-identifier-disclosure
  - provider-call-manual-send-or-paid-model-call
  - service-start-deploy-or-neighboring-product-change
evidence:
  - none
task_id: tj-stwf.1-queue
epic_id: tj-stwf
stage_id: tj-stwf-test-only-restore
session_id: retained-queue-safety-review
milestone: test-only-wazzup-production-restoration
milestone_status: accepted
agent_type: reviewer
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: Production queue replay, background execution and rollback require a read-only correctness review.
repo: treejar
branch: codex/test-channel-safety
base_branch: main
base_commit: b3655501eb3ac71d2bb45086c7761a966784f403
worktree: /home/me/code/treejar/.worktrees/test-channel-safety
write_zone:
  - .codex/stages/tj-stwf-test-only-restore/artifacts/tj-stwf.1-queue.md
success_criteria:
  - exact-retained-key-inventory-without-phones-or-message-bodies
  - retained-work-isolation-and-reverse-rename-rollback-defined
  - arq-startup-and-all-background-side-effects-mapped
  - app-before-worker-gate-is-explicit-and-fail-closed
selected_docs:
  - AGENTS.md
  - .codex/orchestrator.toml
  - .codex/handoff.md
  - .codex/stages/tj-stwf-prod-wazzup-channel/containment-2026-08-28.md
  - .codex/stages/tj-stwf-test-only-restore/stage-manifest.json
selected_skills:
  - code-review
  - technical-premortem
selected_agents:
  - none
catalog_candidates:
  - none
parallel_group: production-restore-preflight
depends_on_streams:
  - none
parallel_decision: parallel-read-only-audit
status: accepted
delivery_method: manual integration
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: Read-only stream ended in the shared worktree; root applied the accepted atomic hold procedure.
risk_level: high
verification_tier: n/a
risk_tags:
  - authorization
  - concurrency
  - atomicity
  - retry
  - state-transition
  - rollback
  - data
affected_surfaces:
  - data
  - database
  - backend
invariants:
  - state-transition
  - idempotency
  - rollback
docs_impact: ops-deploy
docs_reviewed: updated
docs_review_notes: This artifact records the current read-only production inventory and safe restore gates.
verification:
  - sanitized-production-container-and-redis-metadata-readback: passed
  - sanitized-arq-function-age-status-readback: passed-no-arq-jobs-present
  - sanitized-retained-channel-and-key-relation-readback: passed
  - source-startup-background-and-deploy-path-audit: passed
  - executable-quarantine-script-python-syntax: passed
  - production-held-state-check-rollback: passed-read-only-nine-fingerprints-matched
  - tests: not-run-by-read-only-scope
changed_files:
  - .codex/stages/tj-stwf-test-only-restore/artifacts/tj-stwf.1-queue.md
explicit_defers:
  - production-rename-bot-toggle-deploy-and-service-start-remain-root-owned
  - fresh-owner-message-proof-must-follow-all-preflight-gates
---

# Summary

Verdict: **BLOCKED for the normal CI deploy or the normal worker; GO WITH
CONDITIONS for an app-only restoration after retained-key isolation.** No
production state was changed by this review.

## Findings

### P0 — one retained test message can be replayed with a fresh inbound (`must-fix`)

- **Evidence:** at 2026-09-01 10:16 UTC Redis held nine persistent
  `wazzup_msgs:*` lists, one item each. Eight items were from test0665 and one
  from forbidden9235. One test item is stored under the current HMAC safe-ref;
  the other seven test items and the forbidden item use legacy exact-chat keys.
  The webhook appends a fresh event to the same current key and enqueues a job
  (`src/api/v1/webhook.py:343-356`). The worker claims the entire list
  (`src/services/chat.py:344-361`, `src/services/chat.py:824-890`) and finalizes
  it by deleting the processing copy (`src/services/chat.py:966-970`).
- **Impact:** a fresh owner message from the colliding chat can batch with the
  retained item and trigger its LLM/CRM/Wazzup path. Even a channel-filtered
  retained item is removed from Redis, violating preservation.
- **Fix:** atomically rename all nine source lists to a non-runtime hold prefix
  before starting app or worker. Do not copy-only: the original names would
  remain executable. Do not restore held keys while any worker can run.
- **Expected value:** old work remains byte-identical and rollbackable, while
  runtime scans and queue claims cannot see it.
- **Trade-off:** held work needs a later explicit disposition; it cannot be
  silently drained.
- **Confidence:** high.

### P0 — the normal deploy bypasses the required app-before-worker gate (`must-fix`)

- **Evidence:** `scripts/vps-deploy.sh:166-168` runs one unscoped
  `docker compose ... up -d --build`; the GitHub deploy calls it directly
  (`.github/workflows/ci.yml:268-277`). Compose defines both app and worker with
  `restart: unless-stopped` (`docker-compose.yml:12-36`).
- **Impact:** the current CI path recreates and starts app and worker together,
  undoing containment before root can verify the exact release, environment,
  held queues, or background-job mode.
- **Fix:** do not use the current main-push deploy path. Stage the exact release
  without `up`, then recreate app only with restart `no`; worker stays absent or
  stopped until the fresh-job gate below passes.
- **Expected value:** health and environment can be proved without queue
  execution.
- **Trade-off:** delivery needs a bounded manual/no-start path or a reviewed
  deploy option.
- **Confidence:** high.

### P0 — app startup itself calls Telegram and can accept pending mutating callbacks (`must-fix`)

- **Evidence:** FastAPI lifespan always runs `sync_telegram_webhook()`
  (`src/main.py:22-29`). It calls Telegram `getWebhookInfo`, `setWebhook`, and
  `setMyCommands` (`src/integrations/notifications/telegram_webhook.py:46-85`).
  Once reachable, Telegram callbacks can call an LLM, send Wazzup replies and
  commit DB changes (`src/api/telegram_webhook.py:148-175`,
  `src/api/telegram_webhook.py:496-648`, `src/api/telegram_webhook.py:760-915`).
  The web entrypoint also runs Alembic and contains a duplicate-version DELETE
  path (`scripts/entrypoint.sh:13-56`).
- **Impact:** app-only is not content-free under the present environment;
  Telegram/provider and DB effects may occur before the fresh authorized
  WhatsApp inbound.
- **Fix:** start the new app with Telegram webhook sync and Telegram inbound
  fail-closed (a reviewed feature gate is preferred; a protected temporary
  app-container override with empty Telegram token also makes startup sync skip
  and causes old-secret callbacks to fail). Production has one Alembic row at
  the current source head `2026_06_04_customer_memory`, so retain a read-only
  equality check immediately before app start and abort on drift.
- **Expected value:** app health cannot send, register, or process Telegram work.
- **Trade-off:** manager Telegram functions stay unavailable during the
  controlled test.
- **Confidence:** high for the code path; pending provider-side updates remain
  unknown because provider calls were prohibited.

### P0 — the normal worker has unrelated startup and cron side effects (`must-fix`)

- **Evidence:** worker startup loads the embedding model
  (`src/worker.py:35-72`, `src/rag/embeddings.py:32-66`). Its registered cron
  starts metrics immediately (`src/worker.py:98-112`), and the metrics job
  upserts/commits DB state (`src/services/metrics.py:12-87`). Other crons can
  call catalog/Zoho APIs, Wazzup, LLMs, CRM and Telegram
  (`src/worker.py:99-140`; `src/integrations/inventory/sync.py:173-214`;
  `src/services/followup.py:958-1080`; `src/quality/job.py:549-724`;
  `src/quality/manager_job.py:301-509`; `src/services/notifications.py:618-630`;
  `src/services/reports.py:487-500`; `src/services/runtime_monitoring.py:481-521`).
- **Impact:** starting the normal worker violates the no-provider/no-unrelated-
  mutation boundary even though no retained ARQ job currently exists.
- **Fix:** use a reviewed restore-mode WorkerSettings that registers only
  `process_incoming_batch`, has `cron_jobs=[]`, and performs no embedding
  warmup. Do not let unknown jobs be consumed as “function not found”; require
  the ARQ queue to contain exactly the one fresh `process_incoming_batch` job.
- **Expected value:** only the owner-created fresh message can execute.
- **Trade-off:** monitoring, metrics, quality, reports, summaries, follow-ups and
  sync remain paused until a separately authorized normal-worker restoration.
- **Confidence:** high.

### P1 — `bot_enabled=false` is necessary before delivery, but is not sufficient (`must-fix`)

- **Evidence:** PROD currently has `bot_enabled=true`; disk env targets test0665
  but `WAZZUP_OUTBOUND_ALLOWED_CHANNEL_ID` is absent. The stopped containers are
  release `43d6430`, still contain forbidden9235 and have no outbound allow.
  Candidate Wazzup sends fail closed when bot or allow state is wrong
  (`src/services/outbound_safety.py:45-76`), but the core path can call LLM/Zoho
  before it attempts the guarded send (`src/services/chat.py:1519-1651`). Cron
  and Telegram paths are not controlled by the DB bot flag.
- **Impact:** leaving bot true can spend on LLM/CRM and persist an assistant
  result even when Wazzup later blocks. Setting it false alone does not stop
  worker metrics/cron or app Telegram effects.
- **Fix:** set and read back `bot_enabled=false` before any new container start,
  after preserving its prior value. Keep it false through app-only health and
  fresh-job inspection. Set it true only immediately before the inbound-only
  worker starts, after both Wazzup channel variables match test0665.
- **Expected value:** an accidental core worker cannot reach LLM or Wazzup
  during app validation.
- **Trade-off:** if a worker consumes the fresh job while bot is false, it will
  acknowledge/finalize it without a reply; therefore the worker must remain
  stopped until after the true readback.
- **Confidence:** high.

## Fresh production inventory

At 2026-09-01 10:15-10:20 UTC:

- `noor-app-1` and `noor-worker-1`: `exited`, `Running=false`, restart `no`.
- DB, Redis and nginx: running, restart `unless-stopped`, zero restarts.
- Redis DB0: 45 keys. Nine retained Wazzup lists / nine items / nine distinct
  chats; no `arq:queue`, `arq:job:*`, `arq:in-progress:*`, `arq:retry:*`, or
  `arq:result:*`; no inbound processing, lock or quarantine key.
- Thirty-four `wazzup:inbound:execution:*` keys are all `completed`, with about
  2.3-3.2 days TTL remaining. Leave them in place; they do not initiate work.
- ARQ function/age/status inspection therefore returned **zero jobs**. The stale
  prior “one in-progress” observation has expired and must not be reused.
- Retained message ages were about 34-152 days. No body, text, phone, raw chat
  identifier, Redis suffix, ARQ args or kwargs was printed or stored here.

The exact privacy-safe allowlist is the following key-name SHA256 -> exact Redis
`DUMP` SHA256 mapping. Every source was `type=list`, `LLEN=1`, `PTTL=-1`:

| Key SHA256 | DUMP SHA256 |
| --- | --- |
| `2f33c4278f75620e432b10049ab551a59f1270c8329b84fa7af95c3fd7e8563c` | `fa767fa57d42fa48edbfa28c669b9ba7544a9888115cd3fd0b4efe75db00902d` |
| `fa50630f2dc1fc006f2d5a60992e26d8e955c7d2b78a339932e481ee42f9d436` | `e86a3d6a7c45d763930e88d6ea2f08ad656cfe8efe8829c80682ce5fe7a90905` |
| `a9014b182728697d92f015272f8fe41460d470cd5f2975cdbfe1e957bf01f401` | `adf88927fb2e2c73a0670390923419bfdabc875e16928b4b6345835cb3597fbe` |
| `feeeebe1a7dea4b2a0b65e4704415da5eedd68244366c28aa3853341391ff1bd` | `82df40e624428d3d65e7b62dca13de39702b359438e764fa4f509ab546f5eec4` |
| `df519d5eb9a94291d501c1510b422670019249afa180f3eb8b775aeb17ef9c92` | `088604d758571856f9441d5672b739b5ffc543d4a9328c1acf985abc8076048f` |
| `68703a8a30ccb9841ee6d7cb26b5982ff69c52d3736471e6a34969b4e4a5de7a` | `56671006d2778e8ec14491622b53d9790cb93c1762af02602d2075ca7440b5a1` |
| `bc43530531b04fbfaad897727c0c2677822fd61acb7e7a6eea21270efc8aac33` | `3f5ee05b75d3286e50d9782f59a7a74ab174ae5de45bfcf48d4b51600fdd6f44` |
| `6facd378797dee058410b0d2df64cf10201161bd58109cae2da61479a5323664` | `9cec629552c2c23c8f593b29f7abf54c62864dde2617b401ce3962823eabf204` |
| `d18a4d572d1ecf33785d21d8765df80183792d086576274858fcd1cf5e9e0a9a` | `ec4f08230e19c81863d864b0d0141911e2478d6b23eacaccce42e07c23a57df6` |

## Exact isolation and rollback procedure (not executed)

Root used the single fixed prefix
`hold:tj-stwf:20260901T104616Z:`. The operator command must resolve raw source
names only inside the server process; output only hashes and counts.

### Executable privacy-safe command

Use the exact heredoc below. `ACTION=check-quarantine` and
`ACTION=check-rollback` are read-only. Use `ACTION=quarantine` for the atomic
forward rename, or `ACTION=rollback` for the guarded reverse rename. The fixed
prefix must be identical in all runs. The script never prints raw keys, message
bodies, phones or Redis values.

```bash
ssh noor-server 'ACTION=check-quarantine python3 -' <<'PY'
import hashlib
import json
import os
import socket
import subprocess
import sys

CONTAINER = "noor-redis-1"
PREFIX = "hold:tj-stwf:20260901T104616Z:"
EXPECTED = {
    "2f33c4278f75620e432b10049ab551a59f1270c8329b84fa7af95c3fd7e8563c": "fa767fa57d42fa48edbfa28c669b9ba7544a9888115cd3fd0b4efe75db00902d",
    "fa50630f2dc1fc006f2d5a60992e26d8e955c7d2b78a339932e481ee42f9d436": "e86a3d6a7c45d763930e88d6ea2f08ad656cfe8efe8829c80682ce5fe7a90905",
    "a9014b182728697d92f015272f8fe41460d470cd5f2975cdbfe1e957bf01f401": "adf88927fb2e2c73a0670390923419bfdabc875e16928b4b6345835cb3597fbe",
    "feeeebe1a7dea4b2a0b65e4704415da5eedd68244366c28aa3853341391ff1bd": "82df40e624428d3d65e7b62dca13de39702b359438e764fa4f509ab546f5eec4",
    "df519d5eb9a94291d501c1510b422670019249afa180f3eb8b775aeb17ef9c92": "088604d758571856f9441d5672b739b5ffc543d4a9328c1acf985abc8076048f",
    "68703a8a30ccb9841ee6d7cb26b5982ff69c52d3736471e6a34969b4e4a5de7a": "56671006d2778e8ec14491622b53d9790cb93c1762af02602d2075ca7440b5a1",
    "bc43530531b04fbfaad897727c0c2677822fd61acb7e7a6eea21270efc8aac33": "3f5ee05b75d3286e50d9782f59a7a74ab174ae5de45bfcf48d4b51600fdd6f44",
    "6facd378797dee058410b0d2df64cf10201161bd58109cae2da61479a5323664": "9cec629552c2c23c8f593b29f7abf54c62864dde2617b401ce3962823eabf204",
    "d18a4d572d1ecf33785d21d8765df80183792d086576274858fcd1cf5e9e0a9a": "ec4f08230e19c81863d864b0d0141911e2478d6b23eacaccce42e07c23a57df6",
}
ACTION = os.environ.get("ACTION", "check-quarantine")


class SafetyAbort(Exception):
    pass


def abort(code):
    raise SafetyAbort(code)


def run(argv):
    result = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        abort("local_command_failed")
    return result.stdout


def cli(*args):
    output = run(["docker", "exec", CONTAINER, "redis-cli", "--raw", *args])
    text = output.decode("utf-8", "replace").rstrip("\r\n")
    if text.startswith(("ERR ", "(error)")):
        abort("redis_command_failed")
    return text


def scan(pattern):
    result = cli("--scan", "--pattern", pattern)
    return [key for key in result.splitlines() if key]


def redis_ip():
    value = run(
        [
            "docker",
            "inspect",
            "-f",
            "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}",
            CONTAINER,
        ]
    ).decode().strip()
    if not value:
        abort("redis_ip_missing")
    return value


REDIS_IP = redis_ip()


def resp_bulk(*parts):
    encoded = [str(part).encode("utf-8") for part in parts]
    request = b"*" + str(len(encoded)).encode() + b"\r\n"
    for part in encoded:
        request += b"$" + str(len(part)).encode() + b"\r\n" + part + b"\r\n"
    try:
        with socket.create_connection((REDIS_IP, 6379), timeout=5) as sock:
            sock.sendall(request)
            stream = sock.makefile("rb")
            header = stream.readline()
            if not header.startswith(b"$"):
                abort("unexpected_redis_response")
            length = int(header[1:-2])
            if length < 0:
                abort("redis_value_missing")
            data = stream.read(length)
            if len(data) != length or stream.read(2) != b"\r\n":
                abort("truncated_redis_response")
            return data
    except SafetyAbort:
        raise
    except Exception:
        abort("redis_socket_failed")


def dump_fingerprints(key):
    # Both digests must come from one exact binary DUMP read. If they came from
    # separate reads, a concurrent mutation between them could let Lua accept a
    # value that did not match the recorded SHA256 allowlist.
    value = resp_bulk("DUMP", key)
    return (
        hashlib.sha256(value).hexdigest(),
        hashlib.sha1(value, usedforsecurity=False).hexdigest(),
    )


def assert_redis_sha1(key, expected):
    # Prove the locally derived SHA1 is exactly Redis Lua's sha1hex(DUMP).
    # A mutation after the single DUMP read also fails this comparison; any
    # later mutation is caught again inside the atomic EVAL.
    actual = cli(
        "EVAL_RO",
        "return redis.sha1hex(redis.call('DUMP', KEYS[1]))",
        "1",
        key,
    )
    if actual != expected:
        abort("source_dump_sha1_drift")


def assert_services_stopped():
    for name in ("noor-app-1", "noor-worker-1"):
        state = json.loads(run(["docker", "inspect", name]))[0]
        if (
            state["State"].get("Status") != "exited"
            or state["State"].get("Running") is not False
            or state["HostConfig"]["RestartPolicy"].get("Name") != "no"
        ):
            abort("service_not_contained")


def assert_background_empty():
    patterns = (
        "arq:*",
        "wazzup:inbound:processing:*",
        "wazzup:inbound:lock:*",
        "wazzup:inbound:quarantine:*",
    )
    for pattern in patterns:
        if scan(pattern):
            abort("background_state_not_empty")


def original_for(source, mode):
    if mode == "quarantine":
        return source
    if not source.startswith(PREFIX):
        abort("hold_prefix_mismatch")
    return source[len(PREFIX) :]


def sources_for(mode):
    pattern = "wazzup_msgs:*" if mode == "quarantine" else PREFIX + "wazzup_msgs:*"
    sources = scan(pattern)
    if len(sources) != 9:
        abort("source_count_drift")
    by_digest = {}
    for source in sources:
        original = original_for(source, mode)
        digest = hashlib.sha256(original.encode("utf-8")).hexdigest()
        if digest in by_digest or digest not in EXPECTED:
            abort("source_allowlist_drift")
        by_digest[digest] = source
    if set(by_digest) != set(EXPECTED):
        abort("source_allowlist_drift")
    return [by_digest[digest] for digest in sorted(EXPECTED)]


def fingerprint_sources(sources, mode):
    sha1_values = []
    for index, source in enumerate(sources, 1):
        original = original_for(source, mode)
        key_digest = hashlib.sha256(original.encode("utf-8")).hexdigest()
        if cli("TYPE", source) != "list":
            abort("source_type_drift")
        if cli("LLEN", source) != "1":
            abort("source_length_drift")
        if cli("PTTL", source) != "-1":
            abort("source_ttl_drift")
        value_digest, lua_digest = dump_fingerprints(source)
        if value_digest != EXPECTED[key_digest]:
            abort("source_dump_drift")
        assert_redis_sha1(source, lua_digest)
        sha1_values.append(lua_digest)
        print(
            "fingerprint",
            "index=" + str(index),
            "key_sha256=" + key_digest,
            "dump_sha256=" + value_digest,
            "type=list llen=1 pttl_ms=-1",
        )
    return sha1_values


LUA = r"""
local n = #KEYS
local source_pattern = ARGV[2 * n + 1]
local expected_source_count = tonumber(ARGV[2 * n + 2])
local destination_pattern = ARGV[2 * n + 3]
local expected_destination_count = tonumber(ARGV[2 * n + 4])
if #redis.call('KEYS', source_pattern) ~= expected_source_count then
  return redis.error_reply('source_namespace_drift')
end
if #redis.call('KEYS', destination_pattern) ~= expected_destination_count then
  return redis.error_reply('destination_namespace_drift')
end
if #redis.call('KEYS', 'arq:*') ~= 0
   or #redis.call('KEYS', 'wazzup:inbound:processing:*') ~= 0
   or #redis.call('KEYS', 'wazzup:inbound:lock:*') ~= 0
   or #redis.call('KEYS', 'wazzup:inbound:quarantine:*') ~= 0 then
  return redis.error_reply('background_state_not_empty')
end
for i = 1, n do
  local src = KEYS[i]
  local dst = ARGV[i]
  local want_sha1 = ARGV[n + i]
  if redis.call('EXISTS', src) ~= 1 then
    return redis.error_reply('source_missing_' .. i)
  end
  if redis.call('EXISTS', dst) ~= 0 then
    return redis.error_reply('destination_collision_' .. i)
  end
  if redis.call('TYPE', src).ok ~= 'list'
     or redis.call('LLEN', src) ~= 1
     or redis.call('PTTL', src) ~= -1 then
    return redis.error_reply('source_metadata_drift_' .. i)
  end
  if redis.sha1hex(redis.call('DUMP', src)) ~= want_sha1 then
    return redis.error_reply('source_content_drift_' .. i)
  end
end
for i = 1, n do
  redis.call('RENAME', KEYS[i], ARGV[i])
end
return n
"""


def main():
    if ACTION not in {
        "check-quarantine",
        "quarantine",
        "check-rollback",
        "rollback",
    }:
        abort("invalid_action")
    assert_services_stopped()
    assert_background_empty()
    mode = (
        "quarantine"
        if ACTION in {"check-quarantine", "quarantine"}
        else "rollback"
    )
    sources = sources_for(mode)
    sha1_values = fingerprint_sources(sources, mode)
    if mode == "quarantine":
        destinations = [PREFIX + source for source in sources]
        source_pattern = "wazzup_msgs:*"
        destination_pattern = PREFIX + "wazzup_msgs:*"
    else:
        destinations = [original_for(source, mode) for source in sources]
        source_pattern = PREFIX + "wazzup_msgs:*"
        destination_pattern = "wazzup_msgs:*"
    for destination in destinations:
        if cli("EXISTS", destination) != "0":
            abort("destination_collision")
    print("preflight_ok action=" + ACTION + " sources=9 destinations_clear=9")
    if ACTION.startswith("check-"):
        print("read_only_check_complete mutation=false")
        return
    result = cli(
        "EVAL",
        LUA,
        str(len(sources)),
        *sources,
        *destinations,
        *sha1_values,
        source_pattern,
        "9",
        destination_pattern,
        "0",
    )
    if result != "9":
        abort("atomic_rename_failed")
    if scan(source_pattern):
        abort("post_source_namespace_not_empty")
    held_mode = "rollback" if ACTION == "quarantine" else "quarantine"
    after_sources = sources_for(held_mode)
    fingerprint_sources(after_sources, held_mode)
    assert_background_empty()
    print("atomic_rename_complete action=" + ACTION + " renamed=9 mutation=true")


try:
    main()
except SafetyAbort as exc:
    print("ABORT code=" + str(exc))
    sys.exit(2)
except Exception:
    print("ABORT code=unexpected_failure")
    sys.exit(2)
PY
```

Expected read-only output terminates with:

```text
preflight_ok action=check-quarantine sources=9 destinations_clear=9
read_only_check_complete mutation=false
```

For the authorized forward operation, use the identical heredoc with
`ACTION=quarantine`; success terminates with
`atomic_rename_complete action=quarantine renamed=9 mutation=true`. For exact
rollback, first stop app/worker and set restart `no`, then use the identical
heredoc first with `ACTION=check-rollback`, then with `ACTION=rollback`; success terminates with
`atomic_rename_complete action=rollback renamed=9 mutation=true`.

1. Abort unless app/worker are still exited, `Running=false`, restart `no`.
2. `SCAN MATCH wazzup_msgs:*`; abort unless exactly nine keys are present and
   their sorted key SHA256 set and exact RESP `DUMP` SHA256 mapping equal the
   table above. Assert each is list/one item/persistent.
3. Abort if any `arq:queue`, `arq:job:*`, `arq:in-progress:*`, `arq:retry:*`,
   `arq:result:*`, `wazzup:inbound:processing:*`, `...:lock:*`, or
   `...:quarantine:*` key exists. Any nonzero result requires a new audit, not a
   widened glob.
4. For every resolved source, set destination to
   `<fixed-prefix><full-source-key>` and abort if any destination exists. This
   is the collision precheck; `RENAME` must never overwrite.
5. Execute one Redis Lua transaction. Before any rename, the Lua script must
   recheck all source existence, destination absence, type, LLEN, PTTL and a
   pre-recorded `redis.sha1hex(DUMP(source))`; only then loop over all nine
   `RENAME source destination` commands. Return exactly `9`. This makes the
   nine-key cutover all-or-nothing and preserves value plus TTL.
6. Read back: no `wazzup_msgs:*`; exactly nine fixed-prefix keys; every held
   key maps to the same key SHA256 after stripping the prefix, and has the same
   exact `DUMP` SHA256/type/LLEN/PTTL. Recheck ARQ remains empty. Record only
   hashes/counts.

Minimal atomic Lua body for step 5 (pass nine source keys as `KEYS`; pass nine
destinations followed by nine exact preflight DUMP-SHA1 values as `ARGV`):

```lua
local n = #KEYS
for i = 1, n do
  local src = KEYS[i]
  local dst = ARGV[i]
  local want_sha1 = ARGV[n + i]
  if redis.call('EXISTS', src) ~= 1 then
    return redis.error_reply('source_missing_' .. i)
  end
  if redis.call('EXISTS', dst) ~= 0 then
    return redis.error_reply('destination_collision_' .. i)
  end
  if redis.call('TYPE', src).ok ~= 'list'
     or redis.call('LLEN', src) ~= 1
     or redis.call('PTTL', src) ~= -1 then
    return redis.error_reply('source_metadata_drift_' .. i)
  end
  if redis.sha1hex(redis.call('DUMP', src)) ~= want_sha1 then
    return redis.error_reply('source_content_drift_' .. i)
  end
end
for i = 1, n do
  redis.call('RENAME', KEYS[i], ARGV[i])
end
return n
```

Rollback is the same guarded transaction in reverse: first stop app/worker and
set restart `no`; assert all nine original names are absent and all nine held
keys still match the recorded fingerprints; then use held keys as `KEYS` and
original names as destinations. Verify reverse fingerprints. **Do not start a
worker after reverse rename**: rollback restores the stopped pre-isolation
state, not permission to replay. A copy-then-delete strategy is rejected because
it creates a larger partial-failure window; unguarded `RENAME` is rejected
because Redis overwrites an existing destination.

## App-before-worker gate

Required order:

1. Complete and verify the atomic retained-key rename.
2. Preserve the prior DB value, set `bot_enabled=false`, and read back false.
3. Make a protected env backup. The new app container must show both
   `WAZZUP_CHANNEL_ID` and `WAZZUP_OUTBOUND_ALLOWED_CHANNEL_ID` equal only the
   approved test0665 UUID. The stopped old containers must never be started.
4. Stage the exact candidate without the normal all-service deploy. Create only
   app, restart `no`, with Telegram startup/inbound fail-closed; worker remains
   stopped. Abort on any Alembic-head drift.
5. Verify exact release/image/container identity, public health, DB/Redis
   dependencies, nine held fingerprints, zero original Wazzup queues, zero ARQ,
   zero post-start outbound audit rows and zero Telegram/provider calls.
6. Only after root is ready, ask the owner for one new message to test0665.
   With worker still stopped and bot false, require exactly one new
   `process_incoming_batch` ARQ job and one new current safe-ref item whose
   enqueue/message times are after the recorded recovery cutoff. If any older or
   additional event appears, stop and isolate it; do not start worker.
7. Read back both exact channel variables again, set/read back
   `bot_enabled=true`, then start only the inbound-only, cron-free worker from
   the exact image. Correlate that one new job to its one reply.
8. Stop the restore worker after proof. Restoring normal cron/background work is
   a separate decision because it can call LLM/CRM/Telegram and mutate DB/Redis.

# Verification

Read-only production commands used SSH plus `docker inspect`, Redis
`SCAN/TYPE/LLEN/PTTL/DBSIZE/INFO/ZRANGE/GET/DUMP/EVAL_RO`, and PostgreSQL
`SELECT`. ARQ pickle metadata was inspected with a restricted unpickler that
forbids global construction and would have printed only function/age/status;
there were no ARQ jobs to deserialize. Queue JSON was reduced server-side to
channel class, author/type, age and keyed-reference relation; raw values never
left the server command output.

No service was started, no Redis/DB key or row was changed, no test/build was
run, and no provider/model/CRM/Telegram call was made.

# Risks / Follow-ups

- **Provider backlog remains unverified.** Wazzup or Telegram may hold updates
  outside Redis. Provider reads were prohibited. App startup must therefore keep
  Telegram fail-closed, and the one fresh Wazzup job must be timestamp-bounded;
  otherwise an old provider retry arriving after app recovery can masquerade as
  new queue work.
- The 34 completed execution guards will expire naturally in about 2-3 days.
  Held lists remain safe because the hold prefix is unreachable. Reverse rename
  after guard expiry is preservation-only and requires worker stopped.
- PROD disk env already targets test0665, but the outbound allow is absent and
  DB bot is true. Candidate Wazzup egress is currently fail-closed; that is not
  permission to start normal app/worker.
- The exact raw key allowlist necessarily exists only inside the protected
  server process. Never print it: eight source names encode legacy/current chat
  identity forms, including one legacy-phone form.
- Root owns all mutations, release delivery, provider-facing action and the
  fresh-message request. This artifact is a decision gate, not live acceptance.
