# Stage `tj-pk9v-pretest-health-glm53`

Status: accepted locally; not deployed and not production-activated.
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

- No paid model call, push, deploy, production/staging mutation, live database,
  Redis, WhatsApp, Zoho or Telegram action was performed.
- A present `system_configs.openrouter_model_main` value still overrides the
  repository fallback. Production activation and current production health are
  therefore unverified.
- The live route verifier makes five paid calls and was not run.
- The existing auto-FAQ candidate fallback follows the main repository default;
  its primary fast route remains unchanged.

## Documentation and graph

- `docs-reviewed: updated` — configuration comments, this summary and current
  handoff state explain fallback versus runtime override.
- `graph-reviewed: no-change-needed` — no ownership, entrypoint or structural
  boundary changed and Graphify is not initialized.

## Explicit defers

- Production activation/readback and the five-call live route proof require
  separate explicit authority.
- Existing accepted-stage product defects remain tracked in Beads: `tj-gwg1`,
  `tj-2f1u`, `tj-c58g`, `tj-wvuk` and `tj-jlx4`. This model switch does
  not claim to resolve them.
