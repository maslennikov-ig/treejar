# Orchestrator Handoff

Updated: 2026-08-27
Current branch: `codex/pretest-health-glm53-flash`
Current stage id: `tj-pk9v-pretest-health-glm53`
Status: accepted locally and ready for owner-directed testing; not deployed or
production-activated.

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
- The bounded route verifier names GLM 5.3 Flash, requires reasoning support
  and sends low effort. It was not executed because it performs five paid
  calls.
- A present `system_configs.openrouter_model_main` value overrides the code
  fallback. No production value was read or changed, so production activation
  and current production health are not claimed.
- Focused TDD is green: 154 tests passed and `git diff --check` passed.
- Root release acceptance is green: Ruff lint and format passed, Mypy passed
  for 177 source files, full pytest passed with 3851 passed and 20 skipped,
  PostgreSQL migration tests passed 13, end-to-end tests passed 37, integration
  tests passed 162, and process verification passed.
- The audit also repaired local protected-corpus index permissions to `0600`
  and canonically refreshed mutable current-state traceability pins.
- Bead `tj-pk9v` is closed with the local acceptance evidence recorded.
- No push, deploy, live data mutation, real-user message or paid model call was
  performed.

## Accepted history

- `tj-dak8-loosen-opening` remains accepted and deployed history from
  2026-08-14. This new model/readiness stage does not reopen or rewrite its
  measurement.
- The frozen replay and the no-second-reader owner decision remain unchanged.

## Next recommended

Next stage id: not opened
Recommended action: begin local or separately prepared test-environment
testing from the accepted branch. Production activation remains a separate
approval boundary.

## Starter prompt for next orchestrator

Use $orchestrator-stage only for a separately authorized production-activation
or testing continuation. Treat `tj-pk9v-pretest-health-glm53` as locally
accepted, not as proof of the deployed production model. Do not read or change
production model state, run the five-call paid verifier, push, deploy, or send
real messages without fresh explicit authority.

## Explicit defers

- Production model activation/readback and the five-call live route verifier
  require separate explicit authority; neither blocks local test readiness.
- Existing product defects remain tracked and unresolved: `tj-gwg1`,
  `tj-2f1u`, `tj-c58g`, `tj-wvuk` and `tj-jlx4`.
- Referral activation remains an excluded client decision.
- Reader-gap drift remains tracked in `tj-4q79`; no second reader was used.
