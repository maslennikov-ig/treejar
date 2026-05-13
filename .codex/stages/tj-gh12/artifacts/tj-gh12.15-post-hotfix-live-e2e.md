---
schema_version: orchestration-artifact/v1
artifact_type: delegated-stream
task_id: tj-gh12.15-post-hotfix-live-e2e
stage_id: tj-gh12
repo: treejar
branch: main
base_branch: main
base_commit: 91e61fca5390f857b5902f8476b5ee54a87dbf24
worktree: /home/me/code/treejar/.worktrees/codex-tj-gh12-name-gate-hotfix-clean
status: blocked
delivery_method: n/a
accepted_by_orchestrator: no
cleanup_status: cleaned
cleanup_notes: "Scenario B synthetic pending escalation was resolved through the application-level Telegram faq_private manager-reply handler; final readback showed the conversation and escalation row resolved."
risk_level: high
verification:
  - "ssh noor-server 'cd /opt/noor && cat .release-sha && cat .release-run-id'": passed
  - "uv run python scripts/verify_api.py --base-url https://noor.starec.ai": passed
  - "ssh noor-server 'cd /opt/noor && ... bot_test.py scenario A ...'": passed
  - "ssh noor-server 'cd /opt/noor && ... read-only SELECT scenario A evidence ...'": passed
  - "ssh noor-server 'cd /opt/noor && ... bot_test.py scenario B name-only ...'": failed
  - "ssh noor-server 'cd /opt/noor && ... application-level faq_private cleanup handler ...'": passed
changed_files:
  - .codex/stages/tj-gh12/artifacts/tj-gh12.15-post-hotfix-live-e2e.md
explicit_defers:
  - "B-H live E2E paused until tj-gh12.18 is deployed and the name-only reply regression is rechecked."
---

# Summary

Post-hotfix production E2E on `main@91e61fca5390f857b5902f8476b5ee54a87dbf24` confirmed the original scenario A blocker is fixed: the first turn returned only the Noor name gate, kept `escalation_status=none`, and sent no `product_media`.

The run then found a new in-scope blocker for `#21/#29`: after the first-turn name gate, a second user turn containing only `My name is E2E Tester.` left `customer_name=null` and escalated to a manager-confirmation fallback. That was converted into Bead `tj-gh12.18`.

# Scenario Results

| Scenario | Result | Evidence |
| --- | --- | --- |
| A first-turn unknown-name SKU request | passed | Conversation `1916ea0a-2877-4214-a12e-55dd79ce55eb`; reply model `name-gate`; `escalation_status=none`; outbound audit contained only `bot_reply`. |
| B name capture before SKU variants | blocked | Conversation `561e5767-5b3d-4d9f-b0be-75e2186aa915`; second `My name is E2E Tester.` reply used `z-ai/glm-5|verified-policy`, kept `customer_name=null`, and escalated. |
| C showroom Maps | skipped | Blocked by B; continuing would require a stable captured-name state. |
| D quotation missing-data gate | skipped | Blocked by B. |
| E happy quotation/PDF live | skipped | Safety boundary: would create real external Zoho/PDF/send side effects; covered by local tests until a dedicated approved live quote path is provided. |
| F pending quote resume live | skipped | Blocked by B and same external-mutation boundary as E. |
| G proposal follow-up disabled | skipped | No live quotation created; local/runtime config evidence remains covered by tests. |
| H Wazzup typing no fake endpoint | skipped live | No live typing probe; code/docs evidence remains unchanged. |

# Verification

Production readback before live E2E:

```text
release-sha=91e61fca5390f857b5902f8476b5ee54a87dbf24
release-run-id=25789632904
verify_api.py --base-url https://noor.starec.ai -> 7 passed, 0 failed
```

Scenario A send/readback:

```text
suffix=79262810921#tj-gh12-e2e-a2-20260513121800
conversation_id=1916ea0a-2877-4214-a12e-55dd79ce55eb
assistant_model=name-gate
assistant_reply=Hello, I'm Noor from Treejar. May I know your name so I can address you properly?
customer_name=null
sales_stage=greeting
escalation_status=none
outbound_count=1
outbound source=bot_reply
llm_attempts_count=0
```

Scenario B blocker:

```text
suffix=79262810921#tj-gh12-e2e-b-20260513124400
conversation_id=561e5767-5b3d-4d9f-b0be-75e2186aa915
first reply model=name-gate
second reply model=z-ai/glm-5|verified-policy
second reply=I want to be accurate, so our manager will confirm this for you.
customer_name=null
escalation_status=pending
```

# Delivery / Cleanup

The synthetic pending scenario B conversation was resolved through the application-level Telegram `faq_private` manager-reply handler, which sends via the same Wazzup/audit path and calls `resolve_conversation_pending_escalations`. No direct DB/Redis cleanup update was used.

Cleanup readback:

```text
conversation_id=561e5767-5b3d-4d9f-b0be-75e2186aa915
conversation.escalation_status=resolved
escalation.status=resolved
```

# Risks / Follow-ups / Explicit Defers

`tj-gh12.18` must be deployed and rechecked before continuing B-H live E2E. Scenario A remains passed on deployed `91e61fc`.
