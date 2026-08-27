# Stage `tj-pk9v-pretest-health-glm53`

Status: accepted, delivered to `main`, deployed, and production-smoked.
Goal: `tj-pk9v` (closed after local acceptance).
Branch: `codex/pretest-health-glm53-flash`.
Base: `main` at `fe92a3d28f507cb5feba7a57443bad034af7b092`.
Acceptance owner: root orchestrator.

## Outcome

- The repository and development-environment fallback for the customer-facing
  sales model is `z-ai/glm-5.3-flash`.
- Core chat and follow-up send `reasoning: {effort: low}` only for that exact
  model. This prevents the model's mandatory default-max reasoning from
  consuming nearly all of the customer reply budget.
- Luna and other core models keep their provider defaults. Fast, evaluator,
  repair-judge and speech-to-text routes remain separate and unchanged.
- The bounded route verifier now names GLM 5.3 Flash, requires the model's
  reasoning capability and builds the same low-effort request.

## Verification

- Focused TDD RED: four expected failures for the old default and missing core
  low-effort settings, then two expected verifier failures for the old model
  and capability contract.
- Focused GREEN: 154 tests passed.
- `git diff --check`: passed.
- Delegated artifact validation: passed in the worker worktree; root validation
  passed again from the integrated branch.
- Root-owned release closeout passed on the integrated tree:
  - Ruff lint and format checks passed.
  - Mypy passed for 177 source files.
  - Full pytest passed: 3851 passed, 20 skipped.
  - PostgreSQL migration subset passed: 13 tests.
  - End-to-end subset passed: 37 tests.
  - Integration subset passed: 162 tests.
  - Process verification and stage-readiness checks passed.
- The first closeout attempts exposed three repository-health issues, all fixed
  before the green closeout: Python formatting drift, overly broad permissions
  on the protected corpus Git index, and stale mutable-current-state
  traceability pins/handoff fields. The protected index is now mode `0600` and
  the current-state pins were refreshed with the canonical repin script.

## Boundaries and risks

- GitHub Actions run `33042181803` deployed the accepted model release
  `4e56e0fcffdb8f66c8dae9e796edd18dd1a99c0f`.
- Production readback found both `.env` and
  `system_configs.openrouter_model_main` still overriding the new repository
  fallback with `openai/gpt-5.6-luna`. Under the owner's explicit production
  authorization, both were changed to `z-ai/glm-5.3-flash`; `app` and `worker`
  were recreated and both runtime sources then matched the target.
- The prior `.env` is protected at
  `.codex-backups/model-main-before-glm53-run-33042181803.env` on the VPS with
  mode `0600`; the previous database value was `openai/gpt-5.6-luna`.
- Production smoke then exposed `tj-fmee`: the URL-redaction filter cleared the
  five structured arguments required by Uvicorn's access formatter, producing
  a logging traceback on every request. The test-first hotfix `7e21de2` kept
  URL redaction while preserving that formatter contract.
- GitHub Actions run `33042943557` passed and deployed
  `7e21de2b04611065e75936d0281e7aed55e0b2f3`. Public health reports that exact
  SHA with Redis and PostgreSQL healthy; the API smoke passed 8/8, `app` and
  `worker` are running with zero restarts/OOM, and fresh access logs contain 12
  normal request records with zero logging/formatter errors.
- The hotfix release boundary passed Ruff, formatting, Mypy, process
  verification and full pytest: 3852 passed, 20 skipped.
- The live route verifier makes five paid calls and was not run.
- No paid model call, real-user message, Zoho mutation, quotation/order action,
  or broad live E2E was performed.
- The existing auto-FAQ candidate fallback follows the main repository default;
  its primary fast route remains unchanged.

## Documentation and graph

- `docs-reviewed: updated` — configuration comments, this summary and current
  handoff state explain fallback versus runtime override.
- `graph-reviewed: no-change-needed` — no ownership, entrypoint or structural
  boundary changed and Graphify is not initialized.

## Explicit defers

- The five-call paid live route proof remains deferred and requires separate
  explicit authority.
- Existing accepted-stage product defects remain tracked in Beads: `tj-gwg1`,
  `tj-2f1u`, `tj-c58g`, `tj-wvuk` and `tj-jlx4`. This model switch does
  not claim to resolve them.
