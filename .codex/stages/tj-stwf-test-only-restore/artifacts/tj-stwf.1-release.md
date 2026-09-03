---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-stwf-test-only-restore/stage-manifest.json
stream_owner: release-integrator
orchestration_level: release
scope_kind: product_slice
immediate_consumer: production-test-channel-runtime
public_facade: wazzup-inbound-to-outbound-reply-path
bounded_acceptance: test-channel-0665-only-release-and-fresh-owner-message-proof
non_goals:
  - any-channel-other-than-owner-approved-test-0665
  - historical-message-replay-or-retained-payload-inspection
  - manual-or-agent-authored-customer-message
  - neighboring-product-or-shared-host-service-remediation
  - paid-second-reader
evidence:
  - none
task_id: tj-stwf.1-release
epic_id: tj-stwf
stage_id: tj-stwf-test-only-restore
session_id: root-release-integration
milestone: test-only-wazzup-production-restoration
milestone_status: accepted
agent_type: root
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: Root owns the single release acceptance and production delivery boundary.
repo: treejar
branch: main
base_branch: main
base_commit: b3655501eb3ac71d2bb45086c7761a966784f403
worktree: /home/me/code/treejar/.worktrees/test-channel-safety
write_zone:
  - candidate-branch-and-production-release
success_criteria:
  - release-gates-pass-on-the-exact-merged-release
  - retained-work-is-preserved-and-cannot-execute
  - new-app-and-worker-use-the-exact-release-and-test-0665-only
  - public-health-and-fresh-owner-message-reply-are-proved-with-zero-foreign-egress
selected_docs:
  - AGENTS.md
  - .codex/orchestrator.toml
  - .codex/handoff.md
  - .github/workflows/ci.yml
  - scripts/vps-deploy.sh
selected_skills:
  - orchestrator-stage
  - technical-premortem
  - senior-devops
  - finishing-a-development-branch
  - verification-before-completion
  - format-commit-message
selected_agents:
  - prod_restore_preflight
  - retained_queue_safety
catalog_candidates:
  - none
parallel_group: production-restore-preflight
depends_on_streams:
  - tj-stwf.1-preflight
  - tj-stwf.1-queue
parallel_decision: fan-in-before-delivery
status: accepted
delivery_method: merge
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: Accepted candidate worktree and merged local branch were removed; production runtime and rollback backup were untouched.
risk_level: high
verification_tier: release
risk_tags:
  - privacy
  - rollback
  - state-transition
affected_surfaces:
  - backend
invariants:
  - exact-test-channel-authorization
  - no-historical-replay
  - neighboring-services-preserved
  - rollback
docs_impact: ops-deploy
docs_reviewed: updated
docs_review_notes: Current stage, handoff and operator configuration document the fail-closed test-only release.
verification:
  - prior-focused-candidate-acceptance: passed-130-tests
  - prior-ruff-check-format-and-mypy: passed
  - independent-authorization-review-after-dialogue-isolation-fix: passed
  - retained-production-work-quarantine: passed-nine-held-zero-live-zero-arq
  - production-bot-disable-and-test0665-restore-env: passed
  - app-only-and-restore-mode-focused-tests: passed-34-tests
  - final-independent-production-risk-review: one-p1-fixed-no-other-findings
  - worker-stop-postcondition-regression: passed-5-tests
  - legacy-downstream-test-fixtures-and-current-state-pins: passed-32-tests
  - exact-merged-release-gates: passed-3925-tests-20-skipped-plus-risk-groups
  - github-ci-33759923277-and-app-only-deploy: passed
  - production-release-and-content-free-smoke: passed-release-af93ebd
  - fresh-owner-message-correlated-reply: passed-one-allowed-zero-foreign
changed_files:
  - .codex/goals/tj-stwf.1/scope-criterion-snapshot.json
  - .codex/handoff.md
  - .codex/orchestrator.toml
  - .codex/stages/tj-ee5f/traceability-manifest.json
  - .codex/stages/tj-stwf-prod-wazzup-channel/artifacts/tj-stwf-test-only-safety.md
  - .codex/stages/tj-stwf-prod-wazzup-channel/containment-2026-08-28.md
  - .codex/stages/tj-stwf-prod-wazzup-channel/scope-preservation-ledger.json
  - .codex/stages/tj-stwf-prod-wazzup-channel/stage-manifest.json
  - .codex/stages/tj-stwf-prod-wazzup-channel/summary.md
  - .codex/stages/tj-stwf-test-only-restore/artifacts/tj-stwf.1-release.md
  - .codex/stages/tj-stwf-test-only-restore/stage-manifest.json
  - .codex/stages/tj-stwf-test-only-restore/summary.md
  - .github/workflows/ci.yml
  - .env.example
  - README.md
  - docs/operations-runbook.md
  - docs/admin-guide.md
  - scripts/vps-deploy.sh
  - src/core/config.py
  - src/api/telegram_webhook.py
  - src/integrations/messaging/wazzup.py
  - src/main.py
  - src/services/chat.py
  - src/services/outbound_audit.py
  - src/services/outbound_safety.py
  - src/worker.py
  - tests/test_messaging_wazzup.py
  - tests/conftest.py
  - tests/test_chat_escalation.py
  - tests/test_dialog_scenarios.py
  - tests/test_e2e_tools.py
  - tests/test_escalation_fallback.py
  - tests/test_llm_engine.py
  - tests/test_llm_quotation.py
  - tests/test_order_review_flow.py
  - tests/test_product_images.py
  - tests/test_outbound_audit.py
  - tests/test_proposal_followup.py
  - tests/test_scripts_vps_deploy.py
  - tests/test_safe_logging.py
  - tests/test_services_chat.py
  - tests/test_services_chat_batch.py
  - tests/test_services_followup_details.py
  - tests/test_wazzup_outbound_safety.py
  - tests/test_webhook_manager.py
  - tests/test_worker.py
explicit_defers:
  - normal-cron-jobs-telegram-and-all-non-test-channels-remain-disabled
---

# Summary

The fail-closed test-channel release is accepted, merged and deployed.
Production app and the fresh-inbound-only worker run release
`af93ebd5a07d50e1689df76a28d465ddbbec2c17`. Both Wazzup channel settings
authorize only test0665, and the main model is
`z-ai/glm-5.3-flash`.

The exact merged release passed Ruff, format, Mypy, 3,925 tests with 20 explicit
skips, all repository risk groups and process verification. GitHub Actions run
`33759923277` passed and deployed only the app. The worker was then recreated
from the same release in restore mode.

# Verification

Production health reports the exact release with healthy PostgreSQL and Redis.
App and worker have zero restarts and no OOM event. A fresh owner-authored
message produced one user row and one assistant row using
`z-ai/glm-5.3-flash|verified-policy-clarify`; the outbound audit records one
sent Wazzup message on test0665 with a provider message id and zero foreign
egress. Live inbound and ARQ queues returned to zero, while all nine historical
lists remain held under `hold:tj-stwf:20260901T104616Z:`.

# Risks / Follow-ups

The worker remains running for production testing only on test0665. Restore
mode intentionally keeps Telegram, cron jobs, embedding warmup and every
non-test channel disabled. Historical held messages must not be replayed,
deleted or inspected. Moving to normal multi-channel operation is a separate
future release boundary.
