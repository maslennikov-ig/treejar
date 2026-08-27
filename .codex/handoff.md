# Orchestrator Handoff

Updated: 2026-08-27
Current branch: `main`
Current stage id: `tj-7w8f-prod-host-remediation`
Status: in progress. The deployed Noor runtime remains healthy while confirmed
host-maintenance failures are remediated through reversible production changes.

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
- Production `/api/v1/health` reports exact SHA
  `7e21de2b04611065e75936d0281e7aed55e0b2f3`, Redis and PostgreSQL are healthy,
  the API smoke passed 8/8, app/worker have zero restarts or OOM events, and
  fresh access logs show zero logging or formatter errors.
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
- Staged Wazzup `crmKey` Bearer authentication is merged locally. Its security
  review has no blocking findings; production deploy, provider key rotation,
  observe proof and enforcement remain pending.
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
Recommended action: finish `tj-7w8f-prod-host-remediation`, run one production
host and public API acceptance, then resume the owner's controlled testing.

## Starter prompt for next orchestrator

Use $orchestrator-stage for `tj-7w8f`. Treat
`tj-pk9v-pretest-health-glm53` and `tj-fmee` as accepted and deployed history at
runtime SHA `7e21de2`. Keep production mutations reversible and sequential. Do
not run the five-call paid verifier, send real messages, or mutate Zoho/order
data without fresh explicit authority.

## Explicit defers

- The five-call paid live route verifier remains deferred and requires separate
  explicit authority; configuration and startup readback prove activation, not
  a paid inference round.
- Existing product defects remain tracked and unresolved: `tj-gwg1`,
  `tj-2f1u`, `tj-c58g`, `tj-wvuk` and `tj-jlx4`.
- Referral activation remains an excluded client decision.
- Reader-gap drift remains tracked in `tj-4q79`; no second reader was used.
