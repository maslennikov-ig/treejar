---
schema_version: orchestration-artifact/v1
artifact_type: live-e2e
task_id: tj-gh15.3
stage_id: tj-gh15
repo: treejar
branch: codex/tj-gh15-name-escalation-hardening
base_branch: origin/main
base_commit: 3f539f5cd4e404eaab7fc776945d367e6afa07bb
worktree: /home/me/code/treejar/.worktrees/codex-tj-gh15-name-escalation-hardening
status: accepted
delivery_method: merge
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: The approved test phone state was deleted in one production transaction before live E2E; no child worktree was created.
risk_level: medium
verification:
  - "git push origin codex/tj-gh15-name-escalation-hardening:main": passed, main fast-forwarded to cf966f0e2345da0154c8f11f57c0c60340ff451e
  - "GitHub Actions run 25910228955": passed
  - "ssh noor-server cat /opt/noor/.release-sha": passed, cf966f0e2345da0154c8f11f57c0c60340ff451e
  - "uv run python scripts/verify_api.py --base-url https://noor.starec.ai": passed, 7 passed and 0 failed
  - "production cleanup for 79262810921%": passed, before conversations/messages/outbound/escalations/quality_reviews 72/284/250/41/7, after all 0
  - "python3 scripts/bot_test.py -p 79262810921 <#36 first request>": passed, assistant model name-gate and escalation none
  - "python3 scripts/bot_test.py -p 79262810921 Lili": passed, assistant resumed original request and escalation none
  - "python3 scripts/bot_test.py -p 79262810921 '2 Skyland Novo and 2xten'": passed, product clarification path and escalation none
  - "production DB live assertions for 5e587327-0092-4699-a4ee-df6e23edf0ca": passed
  - "read-only verifier subagent": passed
  - "GitHub issue #36 comment and close": passed, https://github.com/maslennikov-ig/treejar/issues/36#issuecomment-4459034706
  - "GitHub issue #37 comment and close": passed, https://github.com/maslennikov-ig/treejar/issues/37#issuecomment-4459034949
changed_files:
  - .codex/stages/tj-gh15/artifacts/tj-gh15.3-live-e2e.md
  - .codex/stages/tj-gh15/summary.md
  - .codex/handoff.md
explicit_defers:
  - none
---

# Summary

Delivered `tj-gh15` to production and completed the approved live E2E on clean
test phone `79262810921`.

# Verification

- Branch `codex/tj-gh15-name-escalation-hardening` was pushed and `origin/main`
  was fast-forwarded to `cf966f0e2345da0154c8f11f57c0c60340ff451e`.
- GitHub Actions run `25910228955` completed successfully.
- `/opt/noor/.release-sha` is `cf966f0e2345da0154c8f11f57c0c60340ff451e`;
  `/opt/noor/.release-run-id` is `25910228955`.
- Production API smoke passed: `7 passed, 0 failed`.
- Approved cleanup prefix `79262810921%` was cleared in one transaction:
  before cleanup there were 72 conversations, 284 messages, 250 outbound audit
  rows, 41 escalations, and 7 quality reviews; after cleanup all matching counts
  were 0.
- Live conversation `5e587327-0092-4699-a4ee-df6e23edf0ca`:
  - First #36 request returned `name-gate` with only the name question and
    escalation `none`.
  - Bare `Lili` stored `customer_name=Lili`, removed
    `name_gate_pending_request`, resumed the original workstation/drawers
    request, and did not return the generic clarify.
  - `2 Skyland Novo and 2xten` returned a product clarification path, with no
    manager handoff text.
  - Final DB assertions passed: `escalation_status=none`, pending escalations
    `0`, metadata contains `quote_customer_details.name=Lili`, and assistant
    models were `name-gate`, `z-ai/glm-5`, `z-ai/glm-5`.
- Independent read-only verifier subagent returned PASS on release marker,
  Docker runtime health, public/local health endpoints, DB state, transcript,
  metadata, and no escalation text.
- GitHub comments and closures:
  - #36: https://github.com/maslennikov-ig/treejar/issues/36#issuecomment-4459034706
  - #37: https://github.com/maslennikov-ig/treejar/issues/37#issuecomment-4459034949

# Risks / Follow-ups

No `tj-gh15` defers remain. Lili's real production conversation was not mutated.
