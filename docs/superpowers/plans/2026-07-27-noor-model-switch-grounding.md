# Noor Model Switch and Grounding Implementation Plan

**Goal:** Adopt GLM-5.2 for core sales and DeepSeek V4 Flash for default
fast/helper routes, enforce the approved evidence-grounding contract, and
deliver the change through verified production deployment.

**Approach:** Keep one cohesive release boundary because configuration,
prompt policy, provider settings, verification, runtime environment, and
rollback converge on the same model-routing decision. Work is root-owned and
sequential: the implementation determines the release artifact; deployment
depends on passing local gates; post-deploy tests depend on the exact deployed
release and protected environment update.

**Non-goals:** Real customer conversations, outbound Wazzup messages, quotation
or order creation, Zoho mutations, broad prompt redesign, and rewriting
existing admin model overrides.

## Scope ledger

- GLM-5.2 main and V4 Flash fast defaults -> Task 1.
- Correct core/helper routing and V4 Flash reasoning control -> Task 1.
- Immutable grounding contract, capability registry, and fallback -> Task 1.
- Focused, integration, release, provider, and review evidence -> Task 1.
- Authorized production environment update, deploy, smoke, and rollback proof
  -> Task 1.

### Task 1: Deliver the grounded model adoption

**Files:** `src/core/config.py`, `.env.example`, `src/llm/safety.py`,
`src/llm/communication_policy.py`, `src/llm/prompts.py`,
`scripts/verify_model_routes.py`, `tests/test_llm_safety.py`,
`tests/test_llm_prompts.py`, `tests/test_webhook_audio.py`,
`.codex/stages/tj-j13d/`, `.codex/handoff.md`.

**Boundary:** Root owns model routing, sales grounding, provider compatibility,
deployment, rollback, and all acceptance proof. Rollback restores the previous
release plus the two previous production model variables.

**Interfaces:** Consumes repository settings, PydanticAI/OpenRouter model
settings, database-overridable prompt components, existing verified-answer
routes, FAQ capabilities, and the canonical deploy entrypoint. Produces
runtime defaults, an immutable grounding prompt block, a typed capability
registry, bounded provider smoke evidence, and deployed model/health readback.

**Verification lane:** `tdd-required` — model routing, provider request
settings, prompt contracts, and production behavior are shared observable
contracts.

- [ ] Add focused failing tests for the two default model identities, route
  selection, V4 Flash reasoning disable, immutable grounding injection,
  capability modes, and safe fallback.
- [ ] Implement the smallest shared policy/configuration change and a bounded
  no-side-effect provider verification script.
- [ ] Run focused tests, affected integration checks, and the full release
  gates once at their respective boundaries.
- [ ] Run one combined correctness/improvement review; fix blocking findings
  with invariant tests and bounded delta-review.
- [ ] Verify provider capabilities and run bounded synthetic main/fast smoke
  checks without customer data or external business mutations.
- [ ] Back up the protected production environment, update exactly the two
  model variables, deploy the verified release, and read back release/models,
  containers, dependencies, and public health.
- [ ] Run post-deploy synthetic grounding and structured-output smoke checks;
  roll back on any blocking health, provider, grounding, or JSON failure.
- [ ] Close Beads/stage state, update durable documentation, and record
  `docs-reviewed`, `project-index`, and `graph-reviewed` decisions.

## Verification commands

- `uv run pytest tests/test_llm_safety.py tests/test_llm_prompts.py tests/test_webhook_audio.py -q --tb=short`
- `uv run ruff check src/ tests/ scripts/`
- `uv run ruff format --check src/ tests/ scripts/`
- `uv run mypy src/`
- Repo-configured integration and release commands from
  `.codex/orchestrator.toml`.
- `scripts/orchestration/run_process_verification.sh`
- `uv run python scripts/orchestration/run_stage_closeout.py --stage tj-j13d`

