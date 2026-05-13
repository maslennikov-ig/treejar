---
schema_version: orchestration-artifact/v1
artifact_type: delegated-stream
task_id: tj-gh12.15-final-live-e2e
stage_id: tj-gh12
repo: treejar
branch: main
base_branch: main
base_commit: df3f3b10f4ee0ab4ee36aa523d4e9cfa4beb2456
worktree: /home/me/code/treejar/.worktrees/codex-tj-gh12-name-gate-hotfix-clean
status: accepted
delivery_method: manual integration
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: "The stale synthetic pending escalation from conversation d82cb1ca-4cde-4042-9f18-4c3129901f93 was resolved through the repo application service resolve_conversation_pending_escalations; no direct SQL update was used."
risk_level: high
verification:
  - "GitHub Actions CI 25793771538": passed
  - "ssh noor-server release marker readback": passed
  - "uv run python scripts/verify_api.py --base-url https://noor.starec.ai": passed
  - "bot_test first-turn product request on 79262810921#tj-gh12-final-20260513133925": passed
  - "bot_test name-only reply on 79262810921#tj-gh12-final-20260513133925": passed
  - "bot_test showroom Maps on 79262810921#tj-gh12-final-20260513133925": passed
  - "bot_test missing quotation data on 79262810921#tj-gh12-final-20260513133925": passed
  - "read-only DB evidence for c7be1bf8-20c2-4cf2-9f55-d7ca207a9b1c": passed
  - "cleanup readback for d82cb1ca-4cde-4042-9f18-4c3129901f93": passed
changed_files:
  - .codex/stages/tj-gh12/artifacts/tj-gh12.15-final-live-e2e.md
  - .codex/stages/tj-gh12/artifacts/tj-gh12.15-second-post-deploy-live-e2e.md
  - .codex/stages/tj-gh12/artifacts/tj-gh12.19-quantity-x-hotfix.md
  - .codex/stages/tj-gh12/summary.md
  - .codex/handoff.md
explicit_defers:
  - "Live happy quotation/PDF creation and pending quote resume were not executed because they would create real external Zoho/PDF/WhatsApp side effects without a dedicated approved synthetic quote path."
  - "Wazzup typing remains provider-blocked because public docs do not expose a supported typing endpoint; no fake endpoint was called."
  - "Proposal follow-up sends remain disabled until approved templates/freeform copy and template transport confirmation are provided."
---

# Summary

Final production E2E on `main@df3f3b10f4ee0ab4ee36aa523d4e9cfa4beb2456` passed the approved text-only scenarios using suffix `79262810921#tj-gh12-final-20260513133925`.

Release readback matched the deployed hotfix:

```text
release-sha=df3f3b10f4ee0ab4ee36aa523d4e9cfa4beb2456
release-run-id=25793771538
verify_api.py --base-url https://noor.starec.ai -> 7 passed, 0 failed
```

# Verification

## Scenario Results

| Scenario | Result | Evidence |
| --- | --- | --- |
| First-turn unknown-name product/SKU request | passed | Conversation `c7be1bf8-20c2-4cf2-9f55-d7ca207a9b1c`; model `name-gate`; reply only Noor greeting + name question; escalation `none`. |
| Name-only reply after gate | passed | Same conversation; model `name-capture`; reply acknowledged `E2E Tester`; DB `customer_name=E2E Tester`; escalation `none`. |
| Showroom Maps | passed | Same conversation; model `z-ai/glm-5|showroom-location`; reply included plain Google Maps URL; escalation `none`. |
| Missing quotation data with `1 x CH-620` + generic `UAE` | passed | Same conversation; model `z-ai/glm-5|exact-quote-missing-details`; reply asked for company/individual confirmation and specific delivery address; escalation `none`. |
| Side-effect readback | passed | DB outbound audit for the final conversation contained only `4` sent text `bot_reply` rows; no media/PDF rows; no escalation rows. |

## Cleanup

The failed second post-deploy E2E conversation `d82cb1ca-4cde-4042-9f18-4c3129901f93` had one synthetic pending escalation, `e1c22bde-754d-4ef2-95dc-e4dc73aca8dc`. It was resolved through the application service `resolve_conversation_pending_escalations`; readback showed conversation status `resolved` and the escalation row status `resolved`.

# Risks / Follow-ups

## Boundaries

No GitHub issues were commented on or closed. No production config, templates, voice/audio, `scripts/verify_wazzup.py`, or broad production suites were run. The E2E worker and orchestrator used only controlled text bot_test messages plus read-only DB checks, except for the explicit cleanup of the synthetic pending escalation.
