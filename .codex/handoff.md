# Orchestrator Handoff

Updated: 2026-08-27
Current branch: `main`
Current stage id: `tj-stwf-prod-wazzup-channel`
Status: production Wazzup channel-routing incident in progress. The owner
authorized switching app and worker to the active Treejar Trading channel.

Documentation: current OpenRouter catalog and reasoning documentation establish
the external model capability boundary. Repository code defines routing and
fallback behavior.

## Current truth

- Incident `tj-stwf`: tester messages reached Noor but were rejected before the
  queue because production expected a disconnected Wazzup channel. The approved
  runtime switch targets the active Treejar Trading channel, with no replay or
  manual answer of previously dropped messages.

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
- No paid model call, real-user message, Zoho mutation, quotation/order action,
  or broad live E2E was performed.
- The duplicate Noor logrotate owner was removed with a protected backup;
  `logrotate.service` and its timer are green. Swap belongs mostly to the
  neighboring Whisper container, but current pressure, OOM and Noor swap use
  are zero, so no disruptive swap reset was performed.
- The stale, unused local `relay.starec.ai` Certbot lineage was backed up and
  retired. The live relay endpoint is hosted elsewhere and both relay and Noor
  TLS are green.
- Wazzup unexpected-channel warnings were proven to be correct fail-closed
  filtering. The expected channel matches runtime configuration and all 532
  linked production conversations, so accepted channel scope was not widened.
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

Next stage id: not opened
Recommended action: begin controlled Treejar product testing on production.
Keep Wazzup in `observe`; do not repeat webhook PATCH or enable `enforce` before
the postponed provider-binding work is deliberately scheduled and proven.

## Starter prompt for next orchestrator

Use $orchestrator-stage for the next material defect found during production
testing. Treat `tj-7w8f`, `tj-pk9v-pretest-health-glm53`, and `tj-fmee` as
accepted and deployed history at runtime SHA `43d6430`. Begin from any defect
found during controlled production testing. Polska is outside Treejar scope. Keep Wazzup in
`observe`; do not use `PATCH /v3/webhooks` for `crmKey`. Do not run the five-call
paid verifier, send real messages, or mutate Zoho/order data without fresh
explicit authority.

## Explicit defers

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
