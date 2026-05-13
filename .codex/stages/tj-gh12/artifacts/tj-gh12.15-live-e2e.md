---
schema_version: orchestration-artifact/v1
artifact_type: delegated-stream
task_id: tj-gh12.15
stage_id: tj-gh12
repo: treejar
branch: main
base_branch: main
base_commit: cc3fcf5a5f3e3dd13249aaf7091a1b0d975a180a
worktree: /home/me/code/treejar
status: blocked
delivery_method: n/a
accepted_by_orchestrator: no
cleanup_status: cleaned
cleanup_notes: "Subagent stopped on scenario A. Orchestrator later resolved the synthetic pending conversation through the normal approved faq_private manager-resolution path; final pending count for tj-gh12-e2e was 0."
risk_level: high
verification:
  - "ssh noor-server 'cd /opt/noor && printf release-sha= && cat .release-sha && printf release-run-id= && cat .release-run-id'": passed
  - "uv run python scripts/verify_api.py --base-url https://noor.starec.ai": passed
  - "ssh noor-server 'cd /opt/noor && set -a && . ./.env && set +a && python3 scripts/bot_test.py ...scenario A...'": failed
  - "ssh noor-server 'cd /opt/noor && docker compose exec -T app python ...read-only SELECT evidence...'": passed
changed_files:
  - .codex/stages/tj-gh12/artifacts/tj-gh12.15-live-e2e.md
explicit_defers:
  - "B-H live/readback coverage skipped because scenario A hit a stop rule."
---

# Summary

Controlled production E2E stopped on scenario A. Runtime matched deployed `main@cc3fcf5a5f3e3dd13249aaf7091a1b0d975a180a`, API smoke passed, and the visible assistant reply correctly used Noor and asked for the customer's name:

```text
Hello, I'm Noor from Treejar. May I know your name so I can address you properly?
```

The same conversation still became `escalation_status=pending` and sent `product_media` price captions before the customer provided a name. That violated the first-turn name gate and triggered the stop rule.

# Runtime Evidence

- Release SHA: `cc3fcf5a5f3e3dd13249aaf7091a1b0d975a180a`
- Release run id: `25785931360`
- API smoke: `7 passed, 0 failed`
- Test suffix: `79262810921#tj-gh12-e2e-a-20260513081336`
- Bot marker: `[smoke:23137ea4]`
- Conversation id: `ceb13f3e-2af6-44fa-ad69-b2e56c2bf9e5`

# Readback Evidence

Initial readback:

```text
customer_name=null
sales_stage=greeting
escalation_status=pending
bot_reply text sent: Hello, I'm Noor from Treejar. May I know your name so I can address you properly?
product_media caption sent: SkyLand CH 620 ... (GREY) - 290.00 AED
```

Cleanup readback after normal `faq_private` manager-resolution path:

```text
conversation ceb13f3e-2af6-44fa-ad69-b2e56c2bf9e5: escalation_status=resolved
tj-gh12-e2e pending_count=0
```

The cleanup also exposed `tj-gh12.17`: the manager private reply adapter introduced unsupported CH-620 price/stock/immediate-delivery facts that were absent from the manager draft. A separate regression/fix was added in the hotfix branch.

# Scenario Results

- A: failed/blocking on deployed `cc3fcf5`.
- B-H: skipped due to A stop rule.

# Verification

Commands recorded in frontmatter were run by the delegated E2E worker and orchestrator. Artifact validation is run separately during hotfix closeout.

# Delivery / Cleanup

No code was accepted from the E2E worker. The production finding was converted into follow-up Beads `tj-gh12.16` and `tj-gh12.17`.

The synthetic pending conversation was resolved through the normal approved `faq_private` manager-resolution path after the worker stopped. No direct DB/Redis cleanup mutation was used.

# Risks / Follow-ups

- `tj-gh12.16`: fixed first-turn unknown-name side effects after this failed E2E.
- `tj-gh12.17`: fixed risky manager reply adaptation after cleanup exposed unsupported claims.
- B-H live E2E remains pending until the hotfix is deployed and scenario A passes.

# Guardrails

No `scripts/verify_wazzup.py`, broad production suite, config/secret change, deploy, GitHub issue mutation, scheduled AI Quality Controls, unapproved template send, voice/audio test, or manual DB/Redis mutation was run.
