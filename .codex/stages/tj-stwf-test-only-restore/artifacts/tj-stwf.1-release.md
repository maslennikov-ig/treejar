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
milestone_status: in-progress
agent_type: root
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: Root owns the single release acceptance and production delivery boundary.
repo: treejar
branch: codex/test-channel-safety
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
status: returned
delivery_method: not accepted
accepted_by_orchestrator: no
cleanup_status: pending
cleanup_notes: Branch and worktree remain required until production acceptance and rollback window complete.
risk_level: high
verification_tier: release
risk_tags:
  - production
  - privacy
  - rollback
  - state-transition
affected_surfaces:
  - backend
  - worker
  - production-runtime
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
  - exact-merged-release-gates: pending
  - production-release-and-content-free-smoke: pending
  - fresh-owner-message-correlated-reply: pending
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
  - fresh-message-proof-must-wait-for-owner-sent-post-recovery-message-to-test-0665
---

# Summary

The fail-closed test-channel release is prepared but not yet accepted or
delivered. Production application and worker processes remain stopped while
retained Redis work is inventoried and moved to a reversible hold namespace.

The final production-risk review found one P1: app-only deploy did not stop an
already-running worker. The deployer now stops worker before replacing files,
verifies that no running worker remains, and aborts before app deployment on a
failed postcondition. Five focused deploy tests pass; the reviewer reported no
other findings in restore-mode, Telegram, worker or Wazzup outbound paths.

# Verification

The final release gate must run once on the exact merged release. Production
acceptance must then confirm the release SHA, new container identities, exact
test-channel environment, preserved DB/Redis/nginx instances, healthy public
dependencies, zero restart/OOM events and zero foreign-channel egress.

# Risks / Follow-ups

Do not start the old application or worker containers. Do not enable outbound
delivery until all retained `wazzup_msgs` keys are isolated without deletion,
both channel environment values match test0665, and the new runtime has passed
content-free checks. A fresh owner-authored message is the only permitted final
reply proof.
