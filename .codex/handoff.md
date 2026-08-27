# Orchestrator Handoff

Updated: 2026-08-27
Current branch: `main`
Current stage id: `tj-7w8f-prod-host-remediation`
Status: blocked on two external ownership facts. Completed Noor repairs are
healthy; Polska source lineage and Wazzup WAuth connection ownership are still
required before the stage can close.

Documentation: current OpenRouter catalog and reasoning documentation establish
the external model capability boundary. Repository code defines routing and
fallback behavior.

## Current truth

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
  successfully match a bounded synthetic Bearer probe.
- Production enforcement is blocked at the provider boundary. Official
  `PATCH /v3/webhooks` does not accept `crmKey`; two same-key PATCH test POSTs
  arrived without a matching Bearer while preserving the exact callback and
  subscriptions. `crmKey` requires an owner-controlled WAuth
  `POST /v3/connect` context, which is not available in the repository or host.
- Polska remains blocked outside Treejar: the current CBOSA source endpoint
  returns HTTP 403 and `/opt/polska/app` has no Git/release lineage. No canonical
  Polska source repository was found locally or in accessible GitHub repos.
- Bead `tj-7w8f` owns the active remediation stage. Five child streams isolate
  Noor host maintenance, relay TLS, Polska jobs, Wazzup filtering and Wazzup
  sender authentication.

## Accepted history

- `tj-dak8-loosen-opening` remains accepted and deployed history from
  2026-08-14. This new model/readiness stage does not reopen or rewrite its
  measurement.
- The frozen replay and the no-second-reader owner decision remain unchanged.

## Next recommended

Next stage id: not opened
Recommended action: obtain the canonical Polska source repository/owner and
confirm whether the Wazzup account has an existing WAuth connection with a
supported reconnect path. Keep Wazzup in `observe`; do not repeat webhook PATCH
or enable `enforce` before provider binding is proven.

## Starter prompt for next orchestrator

Use $orchestrator-stage for `tj-7w8f`. Treat
`tj-pk9v-pretest-health-glm53` and `tj-fmee` as accepted and deployed history at
runtime SHA `43d6430`. Treat logrotate, relay TLS and channel filtering as
completed. Keep Wazzup in `observe`; do not use `PATCH /v3/webhooks` for
`crmKey`. Resume Polska only from its canonical source/owner. Do not run the
five-call paid verifier, send real messages, or mutate Zoho/order data without
fresh explicit authority.

## Explicit defers

- The five-call paid live route verifier remains deferred and requires separate
  explicit authority; configuration and startup readback prove activation, not
  a paid inference round.
- Polska CBOSA repair is blocked by upstream HTTP 403 and missing canonical
  source/release lineage. Do not disable its timer or mask exit status as green.
- Wazzup Bearer enforcement is blocked until the owner supplies a valid WAuth
  reconnect context or Wazzup confirms another supported callback-auth path.
- Existing product defects remain tracked and unresolved: `tj-gwg1`,
  `tj-2f1u`, `tj-c58g`, `tj-wvuk` and `tj-jlx4`.
- Referral activation remains an excluded client decision.
- Reader-gap drift remains tracked in `tj-4q79`; no second reader was used.
