---
schema_version: orchestration-artifact/v1
artifact_type: e2e-plan
task_id: tj-gh22.1
stage_id: tj-gh22
repo: treejar
branch: codex/tj-gh22-fu1-service-window
base_branch: origin/main
base_commit: 32dabb352e8aa8cb584ca575651835a82aef2e0b
worktree: /home/me/code/treejar/.worktrees/codex-tj-gh14-main-merge
status: accepted
delivery_method: n/a
accepted_by_orchestrator: yes
cleanup_status: not_applicable
cleanup_notes: planning artifact only; no separate worker workspace
risk_level: low
runtime_commit: 000dcfbc32c6a0084678c0582c983392e3b27ea6
github_actions_run: "26233069352"
production_smoke: passed
plan_file: docs/specs/e2e-testing/tj-gh22-post-quotation-followup-e2e-plan.md
verification:
  - uv run python scripts/verify_api.py --base-url https://noor.starec.ai: passed (7 passed, 0 failed)
  - GitHub Actions run 26233069352: passed, including deploy
  - scripts/orchestration/validate_artifact.py .codex/stages/tj-gh22/artifacts/tj-gh22.1-e2e-plan.md: passed
changed_files:
  - docs/specs/e2e-testing/tj-gh22-post-quotation-followup-e2e-plan.md
  - .codex/stages/tj-gh22/artifacts/tj-gh22.1-e2e-plan.md
explicit_defers:
  - live WhatsApp E2E execution requires approved run window, number, channel, and synthetic suffixes
  - FU1 live send requires configured EN/AR free-form text
  - complete FU2/FU3 validation requires approved Wazzup WABA EN/AR template ids/codes
---

# Summary

Created a controlled E2E plan for post-quotation follow-up after `tj-gh22`.

The plan covers quotation approval prompt behavior, pre-acceptance bot answers,
acceptance handoff, rejection/no-response handling, FU1 inside the 24-hour
service window, FU1 fallback/blocking outside the window, FU2/FU3 template
transport, Arabic follow-up, and regression scenarios from recent GitHub issues.

# Evidence So Far

- Runtime commit `000dcfbc32c6a0084678c0582c983392e3b27ea6` was deployed by GitHub Actions run `26233069352`.
- Production smoke passed: `uv run python scripts/verify_api.py --base-url https://noor.starec.ai` -> 7 passed, 0 failed.
- Live E2E is not executed yet; this artifact intentionally records planning and blockers only.

# Verification

- Deployment evidence was already collected before this plan: GitHub Actions run `26233069352` succeeded.
- Production smoke passed against `https://noor.starec.ai`.
- Artifact validation passed.

# Risks / Follow-ups

- Do not send live WhatsApp messages until the test window, test number, channel, synthetic suffixes, and scenario list are explicitly approved.
- FU1 can be tested after EN/AR free-form text is configured for the approved test scope.
- FU2/FU3 live sending remains blocked until Wazzup WABA EN/AR template ids/codes are approved and configured.
