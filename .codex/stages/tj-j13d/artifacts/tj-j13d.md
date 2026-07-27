---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-j13d/stage-manifest.json
stream_owner: root-implementation-and-deployment
orchestration_level: release
scope_kind: product_slice
immediate_consumer: Noor production model routing and sales responses
public_facade: runtime model settings and customer-facing grounding behavior
bounded_acceptance: grounded GLM-5.2 sales and V4 Flash helper adoption through verified production deployment
non_goals:
  - real customer messages, outbound Wazzup, quotation/order creation, Zoho mutation, unrelated prompt redesign
evidence:
  - focused-tdd
  - provider-smoke
  - production-readback
task_id: tj-j13d
epic_id: n/a
stage_id: tj-j13d
session_id: n/a
milestone: cohesive-vertical-slice
milestone_status: accepted
agent_type: worker
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: Root owns the shared model, prompt, deployment, and rollback boundary; one context-isolated reviewer is reserved for release risk.
repo: treejar
branch: main
base_branch: main
base_commit: dbd02f0
worktree: /home/me/code/treejar
write_zone:
  - model configuration, grounding policy, focused tests, verification script, stage documentation, protected production model variables and deploy evidence
success_criteria:
  - Deliver the accepted Beads criterion without customer-facing or business-system side effects.
selected_docs:
  - docs/superpowers/specs/2026-07-27-noor-model-switch-grounding-design.md
  - docs/faq.md
  - .codex/orchestrator.toml
selected_skills:
  - orchestrator-stage
  - brainstorming
  - writing-plans
  - test-driven-development
  - prompt-authoring
  - verification-before-completion
  - orchestration-closeout
selected_agents:
  - correctness reviewer at release boundary
catalog_candidates:
  - none; installed workflows and repository policy cover the stage
parallel_group: noor-grounded-model-adoption
depends_on_streams:
  - none
parallel_decision: sequential local implementation, release review, deploy, and post-deploy verification due shared files and hard dependency
status: accepted
delivery_method: manual integration
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: No stage worktree or branch was created; unrelated untracked user files remain untouched.
risk_level: high
verification_tier: release
risk_tags:
  - public-api
  - retry
affected_surfaces:
  - backend
invariants:
  - core-main-model
  - helper-fast-model
  - evidence-grounded-claims
  - tool-and-manager-authority
  - rollback-readiness
docs_impact: behavior
docs_reviewed: updated
docs_review_notes: Project index, stage summary, artifact, handoff, rollback manifest, and review evidence reflect the durable model-route and verification entrypoint changes.
verification:
  - focused TDD and review delta: 73 passed
  - full local release: 1608 passed, 19 skipped; Ruff, format, and Mypy passed
  - pre-deploy provider smoke: 5/5 passed
  - GitHub Actions run 30270308830: lint, type-check, test, changes, and deploy passed
  - production API probe: 8/8 passed
  - production model-route smoke: 5/5 passed
changed_files:
  - .env.example
  - src/core/config.py
  - src/llm/communication_policy.py
  - src/llm/fact_extractor.py
  - src/llm/prompts.py
  - src/llm/safety.py
  - scripts/verify_model_routes.py
  - tests/test_llm_prompts.py
  - tests/test_llm_safety.py
  - tests/test_scripts_verify_model_routes.py
  - tests/test_webhook_audio.py
  - .codex/project-index.md
  - .codex/handoff.md
  - .codex/stages/tj-j13d/
explicit_defers:
  - Real customer messaging and business-system mutations remain outside this stage.
  - Pre-existing Ruff drift in scripts/orchestration is tracked by tj-n8p6.
---

# Summary

GLM-5.2 now owns core sales, DeepSeek V4 Flash owns default helper routes with
reasoning disabled, and the immutable evidence-grounding/capability contract is
deployed. The bounded verifier and rollback snapshots cover the release.

# Verification

- Local release gates: `1608 passed, 19 skipped`; Ruff, format, and Mypy passed.
- Provider smoke before deploy: `5/5`.
- GitHub Actions run `30270308830`: all jobs passed and deployed
  `8ec2f71f3acb3ba37d514b2b220720c724c9f410`.
- Production health/API: dependencies healthy, `8/8` API checks.
- Production synthetic model-route smoke: `5/5`.

# Risks / Follow-ups

- Protected previous `.env` and release archives remain available with
  verified SHA-256 values in the rollback manifest.
- Broad non-canonical scripts lint debt is outside this slice and tracked by
  `tj-n8p6`.
