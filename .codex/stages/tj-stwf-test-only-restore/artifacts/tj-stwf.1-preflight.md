---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-stwf-test-only-restore/stage-manifest.json
stream_owner: prod_restore_preflight
orchestration_level: slice_acceptance
scope_kind: product_slice
immediate_consumer: root-orchestrator
public_facade: n/a
bounded_acceptance: read-only-production-restore-preflight
non_goals:
  - no-git-or-production-mutation
  - no-provider-send-or-paid-verifier
  - no-retained-message-replay-or-delete
evidence:
  - none
task_id: tj-stwf.1-preflight
epic_id: tj-stwf
stage_id: tj-stwf-test-only-restore
session_id: n/a
milestone: test-only-wazzup-safe-production-restore
milestone_status: accepted
agent_type: custom
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: high-risk-production-deploy-and-channel-authorization-preflight
repo: treejar
branch: codex/test-channel-safety
base_branch: main
base_commit: b3655501eb3ac71d2bb45086c7761a966784f403
worktree: /home/me/code/treejar/.worktrees/test-channel-safety
write_zone:
  - .codex/stages/tj-stwf-test-only-restore/artifacts/tj-stwf.1-preflight.md
success_criteria:
  - exact-safe-push-deploy-recreate-and-containment-rollback-path
  - current-git-github-production-and-provider-readback-without-secrets
  - confirmed-facts-separated-from-preconditions-and-assumptions
selected_docs:
  - AGENTS.md
  - .codex/orchestrator.toml
  - .codex/handoff.md
  - .github/workflows/ci.yml
  - scripts/vps-deploy.sh
  - docker-compose.yml
  - docs/operations-runbook.md
  - docs/plans/2026-04-07-prod-deploy-contract-design.md
selected_skills:
  - orchestrator-stage
  - technical-premortem
selected_agents:
  - none
catalog_candidates:
  - none
parallel_group: production-restore-preflight
depends_on_streams:
  - tj-stwf.1-queue
parallel_decision: parallel
status: accepted
delivery_method: manual integration
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: Read-only stream ended in the shared worktree; root integrated the accepted gates.
risk_level: high
verification_tier: delta
risk_tags:
  - authorization
  - state-transition
  - concurrency
  - rollback
  - data
affected_surfaces:
  - backend
  - database
  - data
invariants:
  - state-transition
  - rollback
  - idempotency
docs_impact: ops-deploy
docs_reviewed: no-change-needed
docs_review_notes: existing-deploy-contract-is-accurate-but-cannot-stage-app-before-worker
verification:
  - sed -n 1,400p .github/workflows/ci.yml: passed
  - sed -n 1,500p scripts/vps-deploy.sh: passed
  - git ls-remote --symref origin HEAD refs/heads/main: passed
  - gh repo workflow run branch and secret metadata readback: passed
  - ssh noor-server sanitized compose env redis database and health readback: passed
  - Wazzup GET channels sanitized suffix and state readback: passed
  - python3 scripts/orchestration/validate_artifact.py artifact: passed
changed_files:
  - .codex/stages/tj-stwf-test-only-restore/artifacts/tj-stwf.1-preflight.md
explicit_defers:
  - tj-stwf.1-queue-must-return-atomic-quarantine-proof-before-push
  - current-ci-needs-app-only-deploy-fix-before-push
  - root-owns-ci-delivery-production-mutations-and-final-acceptance
  - fresh-owner-message-proof-remains-separate-and-no-manual-send-is-authorized
---

# Summary

Verdict: **GO WITH CONDITIONS**. Do not push to `main` until the queue stream
has atomically quarantined all 9 retained `wazzup_msgs` items (including the one
from forbidden9235), proved `arq:queue=0` and `wazzup_msgs:*=0`, and production
`bot_enabled` has been changed from `true` to `false` with readback. The current
CI also needs the bounded app-only deploy change below. Queue isolation and DB
disable reduce risk, but are not a reason to keep an avoidable simultaneous
app/worker rollout.

Confirmed facts at 2026-09-01 10:13-10:24 UTC:

- Local and remote `main` are exactly
  `b3655501eb3ac71d2bb45086c7761a966784f403`; GitHub `main` is unprotected.
  The candidate branch is still uncommitted at that base.
- Workflow `ci.yml` is active, has no queued/running run, and the required
  action-secret names `VPS_HOST`, `VPS_USERNAME`, and `VPS_SSH_KEY` exist.
  Secret values were not read.
- A push to `main` containing `src/**` runs lint, format, Mypy and full pytest;
  on green it deploys automatically. The deploy job archives the exact SHA,
  uploads it, and calls `scripts/vps-deploy.sh` for `/opt/noor`.
- `vps-deploy.sh` preserves `.env`, creates a pre-deploy code backup, rsyncs the
  release, then runs `docker compose --project-name noor up -d --build` for the
  whole project. It cannot start app first: it starts/recreates app and worker
  in the same command. A new release SHA is copied into both images, so a
  successful build changes their image identity and Compose should recreate
  them; container-ID readback remains a mandatory proof, not an assumption.
- Production release is `43d6430...` / run `33047773974`. DB, Redis and nginx
  are running; app and worker are exited with `restart=no`; local health is the
  expected `502`. Current `/opt/noor/.env` is mode `0600`, maps to active
  WhatsApp ending0665, and has no outbound allow setting. The stopped app and
  worker environments map to active WhatsApp ending9235. Never use
  `docker start`, `docker unpause`, or `docker compose start` on them.
- Production `bot_enabled=true`. Automatic payment reminders, proposal
  follow-ups, legacy follow-ups, all AI quality scopes, runtime Telegram
  monitoring and its Telegram delivery are disabled/default-disabled. There
  are no feedback candidates due for the allowed channel.
- Initial readback found `arq:queue=0`, 9 `wazzup_msgs` items, and no processing,
  quarantine or lock keys. The queue audit then identified one of the 9 as
  forbidden9235 and requires atomic quarantine before deploy. Do not replay,
  delete or inspect message bodies.
- The current allowed channel owns 532 attributed conversations; 12 belong to
  other channels and 56 are unattributed. The candidate's DB provenance guard
  blocks the latter two sets, but channel scope is not a single-conversation
  scope.
- Compose/runtime deploy-script hashes match the candidate base. Five code
  backups exist and `/opt/noor` has about 120 GiB free. The next deploy will
  retain only the five newest code backups. `.env` is excluded from those
  backups, so it needs its own protected backup.

No Git, production, provider or database mutation was performed in this stream.

## Smallest durable deploy fix

Add optional `--app-only` to `scripts/vps-deploy.sh`. Without the flag, retain
the exact current full-stack behavior for backward compatibility. With it, run:

```bash
docker compose --project-name "$PROJECT_NAME" -f "$COMPOSE_FILE" up -d --build --no-deps app
```

For the current safety policy, `.github/workflows/ci.yml` must pass
`--app-only`. Root later creates worker separately after quarantine, app/env/SHA
readback. This is smaller and safer than a generic free-form `--services`
argument: it has no service-name parsing or command-injection surface and
cannot accidentally include DB, Redis or nginx.

Required implementation files:

- `scripts/vps-deploy.sh`: help, argument parser, default full-stack branch and
  explicit app-only branch;
- `.github/workflows/ci.yml`: pass `--app-only` in the remote deploy command;
- `tests/test_scripts_vps_deploy.py`: preserve the existing no-flag assertion,
  add an app-only assertion for the exact Compose call, and assert the workflow
  passes the flag;
- `docs/operations-runbook.md` and the canonical deploy section of
  `docs/admin-guide.md`: app is automatic; worker activation is a separate
  root-owned gate.

Minimum focused tests after implementation:

```bash
uv run pytest tests/test_scripts_vps_deploy.py -v --tb=short
uv run ruff check tests/test_scripts_vps_deploy.py
git diff --check
```

The root-selected acceptance still owns the broader release commands. Callers
that omit the flag must retain current full-stack behavior. Operationally,
making CI always app-only means future main deploys can leave worker on an older
SHA until the explicit worker gate runs. CI health proves only app; every
release therefore needs a visible worker-pending state and exact post-activation
worker SHA/env readback. Silent app/worker version skew is the main residual
risk.

## Exact safe order

1. **Queue and DB gate before push.** Accept `tj-stwf.1-queue` only when its
   atomic operation proves retained count `9 -> quarantine 9`, source
   `wazzup_msgs:*=0`, processing/lock keys `0`, and `arq:queue=0`, without
   replay or deletion. Then disable the bot in one DB transaction and read it
   back as `false`:

   ```bash
   ssh noor-server "docker exec noor-db-1 psql -v ON_ERROR_STOP=1 -U treejar -d treejar -c \"BEGIN; SELECT key,value::text FROM system_configs WHERE key='bot_enabled' FOR UPDATE; UPDATE system_configs SET value='false'::json WHERE key='bot_enabled' AND value::text='true'; COMMIT;\""
   test "$(ssh noor-server "docker exec noor-db-1 psql -U treejar -d treejar -Atqc \"select value::text from system_configs where key='bot_enabled'\"")" = false
   ```

   Stop if the guarded update does not affect the expected existing `true`
   row. Reconfirm `.env` channel resolves read-only to active0665 and outbound
   allow is absent. Record current app/worker container IDs; do not start them.

2. **Include and accept the app-only deploy fix.** The candidate must contain
   the bounded fix and focused tests above. Root first runs the selected release
   acceptance, checks the exact staged allowlist, then commits and fast-forwards
   only that accepted candidate:

   ```bash
   cd /home/me/code/treejar/.worktrees/test-channel-safety
   git commit -m "fix(wazzup): fail closed outside the test channel"
   candidate_sha="$(git rev-parse HEAD)"
   test "$(git merge-base "$candidate_sha" b3655501eb3ac71d2bb45086c7761a966784f403)" = b3655501eb3ac71d2bb45086c7761a966784f403
   remote_main="$(git ls-remote origin refs/heads/main | awk '{print $1}')"
   test "$remote_main" = b3655501eb3ac71d2bb45086c7761a966784f403
   git -C /home/me/code/treejar merge --ff-only "$candidate_sha"
   git -C /home/me/code/treejar push origin HEAD:main
   ```

   A fresh `ls-remote` immediately before push is mandatory. Stop on ancestry,
   dirty-main, staged-file, or remote-SHA mismatch. Do not force-push.

3. **Let canonical CI deploy app only, still fail-closed.** Watch the run for
   `candidate_sha`; do not dispatch a second run. The deploy is acceptable only
   if lint/type/test and deploy are green, the logged Compose command is
   app-only, and `/opt/noor/.release-sha` equals the exact candidate SHA. Before
   any enablement, prove:

   - app ID differs from the recorded9235 app ID and app reports the candidate;
   - app has `WAZZUP_CHANNEL_ID` resolving to active0665 and outbound allow
     absent/empty, with DB `bot_enabled=false`;
   - the old9235 worker is still exited with `restart=no` and was never started;
   - DB/Redis/nginx container IDs and volumes are unchanged and healthy;
   - retained source queues remain zero and quarantine remains 9;
   - no app/worker restart, OOM, foreign-channel egress or provider-send success
     appears in the bounded post-deploy logs.

4. **Back up and set the outbound allow while the bot remains disabled.** The
   backup must be outside the release archive and mode `0600`:

   ```bash
   ssh noor-server 'bash -s' <<'REMOTE'
   set -euo pipefail
   cd /opt/noor
   umask 077
   stamp="$(date -u +%Y%m%dT%H%M%SZ)"
   env_backup=".hotfix-backups/env-${stamp}-before-test0665-enable"
   cp --preserve=mode,ownership,timestamps .env "$env_backup"
   channel="$(awk -F= '$1 == "WAZZUP_CHANNEL_ID" {sub(/^[^=]*=/, ""); print; exit}' .env)"
   test -n "$channel"
   tmp="$(mktemp ./.env.test0665.XXXXXX)"
   awk -v id="$channel" 'BEGIN{seen=0} /^WAZZUP_OUTBOUND_ALLOWED_CHANNEL_ID=/{print "WAZZUP_OUTBOUND_ALLOWED_CHANNEL_ID=" id; seen=1; next} {print} END{if(!seen) print "WAZZUP_OUTBOUND_ALLOWED_CHANNEL_ID=" id}' .env >"$tmp"
   chmod --reference=.env "$tmp"
   chown --reference=.env "$tmp"
   mv "$tmp" .env
   test "$(stat -c %a .env)" = 600
   test "$(awk -F= '$1 == "WAZZUP_OUTBOUND_ALLOWED_CHANNEL_ID" {sub(/^[^=]*=/, ""); print; exit}' .env)" = "$channel"
   printf '%s\n' "$env_backup"
   REMOTE
   ```

   The operator must also repeat the sanitized provider readback proving that
   `channel` is active0665; equality of the two UUID variables alone is not
   enough.

5. **Recreate app only with the allow setting, still bot-disabled.** Do not
   restart dependencies and do not start old containers:

   ```bash
   ssh noor-server 'cd /opt/noor && docker compose --project-name noor -f docker-compose.yml up -d --force-recreate --no-deps app'
   ```

   Require another new app ID, `restart=unless-stopped`, exact candidate
   image/release, both channel variables resolving to0665, DB false, health 200,
   Redis/DB dependency success, zero restart/OOM, unchanged DB/Redis/nginx, and
   the old worker still exited/restart=no.

6. **Build and create only the worker.** Its first start happens here, after
   quarantine and all app/env readbacks, still with DB false:

   ```bash
   ssh noor-server 'cd /opt/noor && docker compose --project-name noor -f docker-compose.yml up -d --build --force-recreate --no-deps worker'
   ```

   Require a new worker ID (not the9235 container), candidate image/release,
   both channel variables resolving to0665, restart `unless-stopped`, DB false,
   quarantine 9, live retained/ARQ queues zero, and bounded logs with no send or
   paid-QA attempt.

7. **Enable last.** Only after every previous readback passes:

   ```bash
   ssh noor-server "docker exec noor-db-1 psql -v ON_ERROR_STOP=1 -U treejar -d treejar -c \"BEGIN; SELECT key,value::text FROM system_configs WHERE key='bot_enabled' FOR UPDATE; UPDATE system_configs SET value='true'::json WHERE key='bot_enabled' AND value::text='false'; COMMIT;\""
   test "$(ssh noor-server "docker exec noor-db-1 psql -U treejar -d treejar -Atqc \"select value::text from system_configs where key='bot_enabled'\"")" = true
   ```

   Content-free smoke is health/dependency/release/container/log readback only.
   Do not send a manual message. The one fresh owner-sent message to0665 is a
   later root-owned proof; historical retained work stays quarantined.

## Smoke and rollback

Minimum smoke: GitHub run success for exact SHA and app-only command;
`/api/v1/health` HTTP 200 with that SHA and DB/Redis healthy; new app/worker IDs
after their separate gates; both allowed/current channel
suffix0665; `bot_enabled=true`; restart/OOM zero; DB/Redis/nginx unchanged;
quarantine still 9 and live retained/ARQ queues zero; no9235 container running;
no foreign Wazzup send in the bounded logs.

At any failed gate, contain first. Candidate code rechecks DB state before every
outbound retry, but an already submitted provider request cannot be recalled:

```bash
ssh noor-server "docker exec noor-db-1 psql -v ON_ERROR_STOP=1 -U treejar -d treejar -c \"UPDATE system_configs SET value='false'::json WHERE key='bot_enabled';\""
ssh noor-server 'cd /opt/noor && docker compose --project-name noor -f docker-compose.yml stop app worker && docker update --restart=no noor-app-1 noor-worker-1'
```

Then restore the protected pre-enable `.env` backup atomically while app/worker
remain stopped. Keep DB, Redis, nginx, volumes and the quarantine untouched.
This returns the externally visible state to the pre-restore outage (health
502, no outbound). Do **not** run a predecessor archive through
`vps-deploy.sh`: that script would start the old unguarded release. Do not use
`docker start/unpause` on any9235 container. Code can be rolled forward with a
fix; if an exact predecessor file restore is required, restore its unique
`deploy-...-from-43d6430...tar.gz` into `/opt/noor` only while app/worker are
stopped, verify `.release-sha`, and keep them stopped pending a new safety
decision. No database rewind or retained-message replay is part of rollback.

# Verification

Read-only evidence was collected with:

```bash
sed -n '1,400p' .github/workflows/ci.yml
sed -n '1,500p' scripts/vps-deploy.sh
git ls-remote --symref origin HEAD refs/heads/main
gh repo view --json nameWithOwner,defaultBranchRef,url,isPrivate
gh run list --workflow ci.yml --limit 12 --json databaseId,headSha,headBranch,event,status,conclusion,createdAt,updatedAt,url
gh api repos/maslennikov-ig/treejar/actions/workflows/ci.yml --jq .state
gh secret list --app actions --json name
ssh noor-server 'cd /opt/noor && docker compose --project-name noor -f docker-compose.yml ps -a --format json'
ssh noor-server 'docker ps -a --filter label=com.docker.compose.project=noor'
ssh noor-server 'docker exec noor-redis-1 redis-cli --raw ZCARD arq:queue'
ssh noor-server 'docker exec noor-db-1 psql -U treejar -d treejar -Atqc <bounded SELECT>'
curl -fsS -H 'Authorization: Bearer <runtime key>' '<runtime Wazzup API>/channels' | <sanitized state/suffix parser>
```

The SSH inspection reported only modes, hashes, release IDs, service states,
restart policy, channel suffixes, aggregate counts and allow/enable flags. No
secret or customer message body was printed. No tests were run in this stream;
prior local130 and independent review remain candidate evidence, while root
owns the one release acceptance.

# Risks / Follow-ups

- **Block:** no push until atomic quarantine, temporary DB disable and the
  app-only deploy fix are all returned and reviewed.
- CI is not currently an app-first deployer. Any claim that worker starts later
  is false until the recommended script/workflow change lands.
- The automatic code backup excludes `.env`; without the separate protected
  env backup, activation rollback is incomplete.
- Health checks only the app HTTP path. They do not prove worker image/env,
  channel authorization, quarantine preservation, zero provider egress, or
  release parity; the explicit post-deploy readbacks are mandatory.
- The candidate permits any of the 532 conversations already attributed to
  test0665, not one phone only. This matches channel-scoped authority but must
  not be described as single-tester isolation.
- Rollback is containment to the prior stopped state. Starting release43d via
  the standard rollback script would reintroduce unguarded outbound behavior.
- Required GitHub secrets are present by name, but their current values and SSH
  usability are only proven when the deploy job succeeds.
- Root owns production mutations, CI monitoring, final acceptance and the
  later fresh owner-message proof. This preflight explicitly defers all of them.
