# Orchestrator Handoff

Updated: 2026-09-01
Current branch: `codex/test-channel-safety`
Current stage id: `tj-stwf-test-only-restore`
Status: SAFE RESTORATION IN PROGRESS. Only test WhatsApp ending0665 is
authorized. Owner QR reconnection is complete. Nine retained inbound lists are
held outside runtime names, `bot_enabled=false`, and the protected environment
is configured for test0665 restore mode. App and worker remain stopped with
automatic restart disabled; do not start old containers.

Documentation: current OpenRouter catalog and reasoning documentation establish
the external model capability boundary. Repository code defines routing and
fallback behavior.

## Current truth

- Incident `tj-stwf`: the owner clarified that only the test number ending 0665
  may be used. The earlier attribution of nearby working-channel traffic to the
  tester was unproven, and switching to Treejar Trading ending 9235 was wrong.
  The previous stage's frozen evidence is historical, not current authority.
- At 2026-08-28 16:45:11 UTC, with fresh owner approval, only `noor-app-1` and
  `noor-worker-1` were stopped with zero grace; restart policy changed from
  `unless-stopped` to `no`. DB, Redis and nginx container IDs/start times were
  unchanged. The API/panel being unavailable is intentional containment.
- At 16:48:01 UTC, `/opt/noor/.env` was restored to test channel
  `b49b1b9d-757f-4104-b56d-8f43d62cc515`. Only `WAZZUP_CHANNEL_ID` changed,
  verified by byte comparison excluding that line. The mode-0600 backup is
  `/opt/noor/.codex-backups/tj-stwf-before-test-only-20260828T164801Z.env`.
  Stopped containers still retain the old 9235 environment: never `docker start`
  or unpause them. Safe recovery requires corrected code and new containers.
- Provider readback at 17:00:25 UTC for test 0665 is `qridle`; its WhatsApp owner
  must reconnect it through the Wazzup QR flow. No provider registration,
  manual message, old-message replay, or neighboring-product change is allowed.
- Incident impact: since the mistaken switch, 33 `bot_reply` audits across
  12 conversations and 12 `product_media` audits across 2 conversations were
  recorded as `sent`. These counts are not delivery proof; media audit counts
  are not a count of separately delivered attachments. Audit rows do not bind
  the historical sender channel independently of mutable runtime state.
- Production logs confirmed 39 status-persistence failures in the observed
  24-hour window: aware PostgreSQL timestamps were compared with naive parsed
  timestamps. This is our defect; missing delivered/read is not proof of a
  current provider failure. Correct it before using statuses for acceptance.
- Safety preparation is verified locally, not deployed. A shared outbound guard
  covers chat, background jobs and Telegram callbacks, requiring enabled state,
  explicit allowed sender and conversation channel/recipient before HTTP/media
  uploads and retries. The new allow setting remains absent in production.
- Conversation lookup now includes the inbound channel. Old foreign or
  unattributed IDs retain their history/order and remain forbidden to send;
  a fresh test-channel message gets a separate dialogue when needed.
- Root correction acceptance: 130 passed, Ruff/format passed, Mypy passed for
  178 files, and independent security re-review found no blocking issues.
  Seven real local PostgreSQL cases passed with rollback-only schemas; all
  HTTP/model/Zoho calls in those tests were local doubles. Evidence is in
  `artifacts/tj-stwf-test-only-safety.md` within the current stage.
- Read-only post-containment DB count: zero outbound audits after 16:45:12 UTC.
  No merge, deploy, restart, replay, provider mutation or manual message followed.
- On 2026-09-01 the test0665 provider state was re-read as active. All nine
  retained `wazzup_msgs` lists, including one from forbidden9235, were matched
  to the frozen privacy-safe fingerprints and atomically renamed under
  `hold:tj-stwf:20260901T104616Z:`. Source lists and ARQ jobs are now zero; no
  payload was printed, deleted or replayed.
- Production `bot_enabled` is temporarily false. A new mode-0600 environment
  backup exists at
  `/opt/noor/.hotfix-backups/env-20260901T104712Z-before-test0665-restore`.
  Disk configuration binds current and outbound-allowed channel only to active
  test0665 and enables `TEST_CHANNEL_RESTORE_MODE=true`; stopped old containers
  remain unchanged and forbidden.
- The current candidate makes CI deploy app only. Restore mode skips Telegram
  startup and inbound, and registers an inbound-only worker with no cron jobs or
  embedding warmup. Focused coverage for these new gates passed 34 tests.
- Final production-risk review found one P1: the app-only path did not stop an
  already-running worker. It now stops worker before replacing files, verifies
  the worker is not running, and aborts if that proof fails. Five deploy tests
  pass; the reviewer found no other issues in the reviewed safety paths.

## Prior release evidence (historical, before containment)

- The repository and `.env.example` now default the customer-facing sales
  model to `z-ai/glm-5.3-flash`.
- Core chat and follow-up send `reasoning: {effort: low}` only for that exact
  model. Luna and other core models retain provider defaults.
- The separate fast, evaluator and repair routes remain
  `deepseek/deepseek-v4-flash`; speech-to-text remains
  `openai/gpt-4o-mini-transcribe`.
- Production `.env` and `system_configs.openrouter_model_main` both resolve to
  `z-ai/glm-5.3-flash`; worker startup confirms the same active model.
- The bounded route verifier names GLM 5.3 Flash, requires reasoning support
  and sends low effort. It was not executed because it performs five paid
  calls.
- Focused TDD is green: 154 tests passed and `git diff --check` passed.
- Root release acceptance is green: Ruff lint and format passed, Mypy passed
  for 177 source files, full pytest passed with 3851 passed and 20 skipped,
  PostgreSQL migration tests passed 13, end-to-end tests passed 37, integration
  tests passed 162, and process verification passed.
- The audit also repaired local protected-corpus index permissions to `0600`
  and canonically refreshed mutable current-state traceability pins.
- Bead `tj-pk9v` is closed with the local acceptance evidence recorded.
- Model release `4e56e0f` was fast-forwarded to `main`, pushed, and deployed by
  GitHub Actions run `33042181803`. Production runtime configuration was then
  switched from Luna to GLM 5.3 Flash with a mode-`0600` `.env` backup and the
  previous database value recorded for rollback.
- Production smoke exposed and closed `tj-fmee`, a Uvicorn access-log formatter
  failure caused by the URL-redaction filter. Hotfix `7e21de2` passed 3852
  tests with 20 skips and was deployed by run `33042943557`.
- Remediation release `43d6430` passed Ruff, format, Mypy, 3891 tests with 20
  skips, and the semantic retrieval gate, then deployed through GitHub Actions
  run `33047773974`. Production health reports that exact SHA; Redis and
  PostgreSQL are healthy, and app/worker have zero restarts or OOM events.
- The earlier release verification itself made no paid model call, manual
  real-user message, Zoho mutation, quotation/order action, or broad live E2E.
  Later automatic production replies during the routing incident are counted
  above; do not interpret the earlier statement as zero incident side effects.
- The duplicate Noor logrotate owner was removed with a protected backup;
  `logrotate.service` and its timer are green. Swap belongs mostly to the
  neighboring Whisper container, but current pressure, OOM and Noor swap use
  are zero, so no disruptive swap reset was performed.
- The stale, unused local `relay.starec.ai` Certbot lineage was backed up and
  retired. The live relay endpoint is hosted elsewhere and both relay and Noor
  TLS are green.
- The original guard against the non-test channel was correct. Current owner
  authority is only test 0665; an active channel is not automatically authorized.
- Staged Wazzup Bearer authentication is deployed in non-blocking `observe`
  with a new strong protected secret. App code and the existing audit relay
  successfully match a bounded synthetic Bearer probe. `observe` does not
  authenticate or reject senders.
- Production enforcement is intentionally postponed as a long-term task.
  Official
  `PATCH /v3/webhooks` does not accept `crmKey`; two same-key PATCH test POSTs
  arrived without a matching Bearer while preserving the exact callback and
  subscriptions. `crmKey` requires an owner-controlled WAuth
  `POST /v3/connect` context or another provider-supported path. Production
  remains compatible and non-blocking in `observe` until that work is scheduled.
  The same long-term task owns trustworthy proxy handling and a verified
  source-IP policy; the current empty allowlist is not an authentication proof.
- The owner confirmed that Polska is a separate client product sharing the host,
  not part of Treejar. Its service state is excluded from Treejar health and no
  Polska mutation was made.
- Bead `tj-7w8f` and its remediation stage are accepted. The Wazzup sender-auth
  hardening remains detached as a low-priority long-term backlog item.

## Accepted history

- `tj-dak8-loosen-opening` remains accepted and deployed history from
  2026-08-14. This new model/readiness stage does not reopen or rewrite its
  measurement.
- The frozen replay and the no-second-reader owner decision remain unchanged.

## Next recommended

Current stage: `tj-stwf-test-only-restore`
Next stage id: `tj-stwf-test-only-restore` (continue the active release stage)
Recommended action: complete release and retained-work preflight, deploy one
accepted SHA through the app-only CI path, verify exact app/env/health, then
create the inbound-only worker. Use only one fresh owner-sent test message for
eventual reply proof; never test on Treejar Trading or replay old messages.

## Starter prompt for next orchestrator

Use $orchestrator-stage to continue the active production restore stage.
Continue `tj-stwf` from `codex/test-channel-safety`. Only test 0665 is allowed.
Read the current containment note and scope ledger before any production action.
Do not start old containers, merge to auto-deploying main, change shared provider
registration, replay queues or message real customers. Preserve DB/Redis and
neighboring products. Keep Wazzup auth in `observe`; that deferred work is not
part of this incident. Historical release `43d6430` is stopped, not healthy live.

## Explicit defers

- `tj-stwf`: local outbound isolation is verified, but live restoration and
  fresh-message acceptance wait for phone-owner QR reconnection and a controlled
  safe startup. Hold remains; this is not accepted end-to-end operation.
- The five-call paid live route verifier remains deferred and requires separate
  explicit authority; configuration and startup readback prove activation, not
  a paid inference round.
- Wazzup sender-authentication hardening is a low-priority long-term backlog
  item by owner decision. It includes provider Bearer binding, trustworthy proxy
  handling, and a verified source-IP policy. Production remains compatible and
  non-blocking in `observe`, which does not authenticate senders.
- Existing product defects remain tracked and unresolved: `tj-gwg1`,
  `tj-2f1u`, `tj-c58g`, `tj-wvuk` and `tj-jlx4`.
- Referral activation remains an excluded client decision.
- Reader-gap drift remains tracked in `tj-4q79`; no second reader was used.
