# Orchestrator Handoff

Updated: 2026-08-27
Current branch: `main`
Current stage id: `tj-pk9v-pretest-health-glm53`
Status: accepted, delivered, deployed, production-smoked, and ready for
owner-directed production testing.

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

## Accepted history

- `tj-dak8-loosen-opening` remains accepted and deployed history from
  2026-08-14. This new model/readiness stage does not reopen or rewrite its
  measurement.
- The frozen replay and the no-second-reader owner decision remain unchanged.

## Next recommended

Next stage id: not opened
Recommended action: begin the owner's controlled production testing against
`https://noor.starec.ai`, keeping real-customer messaging and business-data
mutations inside the owner's intended test plan.

## Starter prompt for next orchestrator

Use $orchestrator-stage only for a new production-testing or remediation goal.
Treat `tj-pk9v-pretest-health-glm53` and `tj-fmee` as accepted and deployed
history at runtime SHA `7e21de2`. Do not run the five-call paid verifier, send
real messages, or mutate Zoho/order data without fresh explicit authority.

## Explicit defers

- The five-call paid live route verifier remains deferred and requires separate
  explicit authority; configuration and startup readback prove activation, not
  a paid inference round.
- Existing product defects remain tracked and unresolved: `tj-gwg1`,
  `tj-2f1u`, `tj-c58g`, `tj-wvuk` and `tj-jlx4`.
- Referral activation remains an excluded client decision.
- Reader-gap drift remains tracked in `tj-4q79`; no second reader was used.
