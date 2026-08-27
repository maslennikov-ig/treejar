---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-pk9v-pretest-health-glm53/stage-manifest.json
stream_owner: tj-pk9v-model-health-worker
orchestration_level: inner_loop
scope_kind: product_slice
immediate_consumer: root-orchestrator-final-acceptance
public_facade: customer-facing-sales-chat-and-followup-model-route
bounded_acceptance: repository-default-core-reasoning-policy-and-local-route-verifier
non_goals:
  - paid-model-calls
  - live-provider-verification
  - production-or-staging-mutation
  - live-database-redis-messaging-crm-or-deploy-access
  - full-suite-release-or-process-acceptance
evidence:
  - none
task_id: tj-pk9v
epic_id: n/a
stage_id: tj-pk9v-pretest-health-glm53
session_id: tj-pk9v-model-health-worker
milestone: glm53-flash-repository-default-and-local-health
milestone_status: accepted
agent_type: worker
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: The bounded implementation and focused audit inherit the orchestrator model; no model override was authorized or needed.
repo: treejar
branch: codex/pretest-health-glm53-flash-impl
base_branch: codex/pretest-health-glm53-flash
base_commit: 05d56283b34c0260b2afc3c8e4f31f245fd43871
worktree: /home/me/code/.worktrees/treejar-pretest-health-glm53-impl
write_zone:
  - src/core/config.py
  - .env.example
  - src/llm/safety.py
  - scripts/verify_model_routes.py
  - tests/test_webhook_audio.py
  - tests/test_llm_safety.py
  - tests/test_scripts_verify_model_routes.py
  - .codex/stages/tj-pk9v-pretest-health-glm53/artifacts/tj-pk9v.md
success_criteria:
  - repository-and-env-example-main-default-is-z-ai-glm-5.3-flash
  - core-chat-and-followup-send-reasoning-effort-low-for-the-exact-model
  - luna-and-other-core-models-retain-provider-default-reasoning
  - primary-fast-repair-evaluator-and-stt-routes-remain-unchanged
  - local-route-verifier-requires-reasoning-and-builds-the-low-effort-sales-payload
  - focused-tests-and-diff-check-pass-without-paid-or-live-calls
selected_docs:
  - AGENTS.md
  - .codex/orchestrator.toml
  - .codex/handoff.md
  - README.md
selected_skills:
  - superpowers-test-driven-development
  - superpowers-systematic-debugging
selected_agents:
  - none
catalog_candidates:
  - none
parallel_group: n/a
depends_on_streams:
  - none
parallel_decision: local
status: accepted
delivery_method: merge
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: Root reviewed and merged the stream, removed the clean dedicated worktree, and deleted the merged local worker branch.
risk_level: medium
verification_tier: inner
risk_tags:
  - user-flow
  - data
affected_surfaces:
  - backend
  - user-flow
invariants:
  - test-matrix
docs_impact: behavior
docs_reviewed: updated
docs_review_notes: Config and environment-example comments now state repository fallback and runtime DB override semantics; root owns stage summary and current-state handoff updates.
verification:
  - uv sync --locked --all-extras --dev: passed after the fresh worktree initially lacked the optional dev test tools
  - focused config and core-policy RED: expected 4 failures for the old Luna default and missing low effort on core chat followup and runtime merge
  - focused config and core-policy GREEN: passed 6 tests
  - focused verifier RED: expected 2 failures for the stale 5.2 model id and missing main reasoning capability requirement
  - focused verifier GREEN: passed 3 tests
  - uv run pytest tests/test_webhook_audio.py tests/test_llm_safety.py tests/test_scripts_verify_model_routes.py -q --tb=short: passed 154 tests
  - local settings and route probe with model env overrides removed: passed with GLM core low Luna core provider-default DeepSeek repair disabled and dedicated STT unchanged
  - git diff --check: passed
  - uv run python scripts/orchestration/validate_artifact.py .codex/stages/tj-pk9v-pretest-health-glm53/artifacts/tj-pk9v.md: passed
  - scripts/verify_model_routes.py: not run because it performs five paid calls and no such authority was granted
changed_files:
  - .env.example
  - scripts/verify_model_routes.py
  - src/core/config.py
  - src/llm/safety.py
  - tests/test_llm_safety.py
  - tests/test_scripts_verify_model_routes.py
  - tests/test_webhook_audio.py
  - .codex/stages/tj-pk9v-pretest-health-glm53/artifacts/tj-pk9v.md
explicit_defers:
  - none
---

# Summary

`z-ai/glm-5.3-flash` is now the repository and environment-example fallback
for the customer-facing sales model. The exact model receives
`reasoning: {effort: low}` on core chat and follow-up only. The local route
verifier now names the same model, requires its reasoning capability, and
builds the same bounded reasoning request.

# Scope / Routing

The core guard is both exact-model and core-scope bounded. Luna and other core
models retain the provider default. The primary fast and evaluator routes
remain on `deepseek/deepseek-v4-flash`, the repair judge remains on that same
separate model with reasoning disabled, and speech-to-text remains on
`openai/gpt-4o-mini-transcribe`.

The runtime database value `system_configs.openrouter_model_main` still wins
when present. The repository fallback is used only when that lookup is absent
or fails, so this commit is not evidence that a deployed database already
selects GLM 5.3 Flash.

# Verification

Both behavior changes were developed test-first and observed failing for the
intended reason. The combined local focused set passed 154 tests. A read-only
settings probe confirmed the route identities and reasoning payloads, and
`git diff --check` passed. No full suite, release gate, process verification,
live route verifier, provider call, or external mutation was run; root owns the
single final acceptance boundary.

# Delivery / Cleanup

Root reviewed and merged `codex/pretest-health-glm53-flash-impl` into the
stage branch. The clean dedicated worktree and merged local worker branch were
then removed. Root release and process acceptance subsequently passed on the
integrated tree. No push, deploy, production mutation, or paid call was
performed.

# Risks / Follow-ups / Explicit Defers

- Production activation is unverified because environment variables and the
  database override may still select another main model. Checking or changing
  them requires a separate authorized live boundary.
- Provider behavior at the verifier's 400-token ceiling is not locally proved.
  The live verifier makes five paid calls and was deliberately not run.
- The primary auto-FAQ candidate route remains on the fast model. Its existing
  last-resort fallback aliases `settings.openrouter_model_main`, so that fallback
  follows the new main repository default; this is an indirect consequence of
  the existing fallback design, not a primary fast-route change.
- Root-owned release and process verification passed before stage acceptance.
  There is no worker-owned explicit defer.
