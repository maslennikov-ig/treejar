---
schema_version: orchestration-artifact/v1
artifact_type: delegated-stream
task_id: tj-gh12.15-second-post-deploy-live-e2e
stage_id: tj-gh12
repo: treejar
branch: main
base_branch: main
base_commit: 0a283a42a94b10e77456f641ee0b87a789f13efd
worktree: /home/me/code/treejar/.worktrees/codex-tj-gh12-name-gate-hotfix-clean
status: blocked
delivery_method: n/a
accepted_by_orchestrator: no
cleanup_status: cleaned
cleanup_notes: "Synthetic conversation d82cb1ca-4cde-4042-9f18-4c3129901f93 had pending escalation e1c22bde-754d-4ef2-95dc-e4dc73aca8dc from the missing-data quotation blocker; after df3f3b1 was deployed and rechecked, cleanup used the repo application service and readback showed both conversation and escalation resolved."
risk_level: high
verification:
  - "ssh noor-server 'cd /opt/noor && cat .release-sha && cat .release-run-id'": passed
  - "uv run python scripts/verify_api.py --base-url https://noor.starec.ai": passed
  - "worker Franklin live bot_test first-turn product request": passed
  - "worker Franklin live bot_test name-only reply": passed
  - "worker Franklin live bot_test showroom Maps reply": passed
  - "worker Franklin live bot_test missing quotation data": failed
changed_files:
  - .codex/stages/tj-gh12/artifacts/tj-gh12.15-second-post-deploy-live-e2e.md
explicit_defers:
  - "Resolved by tj-gh12.19 and final accepted E2E artifact tj-gh12.15-final-live-e2e.md."
---

# Summary

Second post-deploy E2E on `main@0a283a42a94b10e77456f641ee0b87a789f13efd` verified that `tj-gh12.18` works in production: first-turn product requests still stop at the Noor name gate, and a following name-only reply stores `customer_name` and returns `name-capture` without manager escalation.

The same worker run found a new quotation blocker converted into Bead `tj-gh12.19`: `Please create a quotation for 1 x CH-620. Deliver to UAE.` entered `exact-quote-fallback` and created a pending manager escalation instead of asking for missing company/specific-address details. That blocker was fixed and rechecked in `tj-gh12.15-final-live-e2e.md`.

# Scenario Results

| Scenario | Result | Evidence |
| --- | --- | --- |
| Production readback | passed | `.release-sha=0a283a42a94b10e77456f641ee0b87a789f13efd`; `.release-run-id=25792412177`. |
| API smoke | passed | `verify_api.py --base-url https://noor.starec.ai -> 7 passed, 0 failed`. |
| First-turn unknown-name product request | passed | Conversation `d82cb1ca-4cde-4042-9f18-4c3129901f93`; model `name-gate`; escalation `none`; reply only greeting/name question. |
| Name-only reply after gate | passed | Same conversation; model `name-capture`; escalation `none`; `customer_name=E2E Tester`. |
| Showroom Maps | passed | Same conversation; model `z-ai/glm-5|showroom-location`; reply included a plain Google Maps URL; escalation `none`. |
| Missing quotation data | failed | Same conversation; model `z-ai/glm-5|exact-quote-fallback`; escalation row `e1c22bde-754d-4ef2-95dc-e4dc73aca8dc` created as `pending`. |

# Verification

The E2E worker used only controlled text messages to the approved suffix under `+79262810921`, read-only DB checks through the app container, and local API smoke. It did not run `scripts/verify_wazzup.py`, mutate GitHub issues, mutate production config, send templates, or test voice/audio.

# Risks / Follow-ups / Explicit Defers

The pending synthetic escalation was cleaned after `tj-gh12.19` was deployed/rechecked. Live happy quotation/PDF and pending quote resume remain intentionally skipped because they would create real external Zoho/PDF/WhatsApp side effects without a dedicated approved synthetic quote path.
