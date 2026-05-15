---
schema_version: orchestration-artifact/v1
artifact_type: live-e2e
task_id: tj-e2e16.4-5
stage_id: tj-e2e16
repo: treejar
branch: main
base_branch: origin/main
base_commit: 37c2b88fc6eec5cb4ed3d16c06b5c52a07a0e564
worktree: /home/me/code/treejar/.worktrees/codex-tj-gh14-main-merge
status: accepted
delivery_method: merge
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: Approved production test phone state was deleted in audited transactions before live reruns.
risk_level: medium
verification:
  - "git push origin main": passed, main delivered 37c2b88 and hotfix 2b86b0366fde0358fed255e8da3c89aacedf556f
  - "GitHub Actions run 25930025028": passed, deployed 37c2b88
  - "Live E2E on 37c2b88": failed, saved-context summary question still routed to verified-policy handoff
  - "Hotfix commit 2b86b0366fde0358fed255e8da3c89aacedf556f": passed
  - "uv run pytest targeted saved-context tests": passed, 5 passed
  - "uv run ruff check src/ tests/": passed
  - "uv run ruff format --check src/ tests/": passed
  - "uv run mypy src/": passed
  - "uv run pytest tests/test_llm_engine.py tests/test_verified_answers.py -q": passed, 193 passed
  - "env DYLD_FALLBACK_LIBRARY_PATH=\"${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}\" uv run pytest tests/ -v --tb=short": passed, 1043 passed, 19 skipped
  - "scripts/orchestration/run_process_verification.sh": passed
  - "GitHub Actions run 25932016725": passed, deployed 2b86b0366fde0358fed255e8da3c89aacedf556f
  - "ssh noor-server cat /opt/noor/.release-sha": passed, 2b86b0366fde0358fed255e8da3c89aacedf556f
  - "uv run python scripts/verify_api.py --base-url https://noor.starec.ai": passed, 7 passed and 0 failed
  - "production cleanup for 79262810921% before final E2E": passed, before conversations/messages/outbound/escalations/manager_reviews/quality_reviews/conversation_summaries/feedbacks 1/19/25/1/0/0/1/0, after all 0
  - "live long-dialog E2E conversation ae1c7a38-d7e6-401c-a520-07a0a480cd2e": passed
  - "production DB assertions for ae1c7a38-d7e6-401c-a520-07a0a480cd2e": passed
changed_files:
  - src/llm/engine.py
  - tests/test_llm_engine.py
  - .codex/stages/tj-e2e16/artifacts/tj-e2e16.4-5-live-e2e.md
  - .codex/stages/tj-e2e16/summary.md
  - .codex/handoff.md
explicit_defers:
  - none
---

# Summary

Delivered `tj-e2e16` to production and repeated the long-dialog memory E2E on
the approved phone `79262810921`.

The first deploy (`37c2b88`) fixed neutral detail capture and product/quantity
turns, but live E2E exposed one remaining gap: a saved-context summary question
still routed through `verified-policy` handoff. Hotfix `2b86b03` added
deterministic saved-context summary handling and delivery-timing memory.

# Verification

Final deployed production release:

- GitHub Actions run `25932016725`: success.
- `/opt/noor/.release-sha`: `2b86b0366fde0358fed255e8da3c89aacedf556f`.
- Production API smoke: 7 passed, 0 failed.
- Final cleanup for approved phone prefix `79262810921%`: before cleanup there
  were 1 conversation, 19 messages, 25 outbound audit rows, 1 escalation,
  0 manager reviews, 0 quality reviews, 1 conversation summary, and 0 feedbacks;
  after cleanup all matching counts were 0.

Final live conversation `ae1c7a38-d7e6-401c-a520-07a0a480cd2e`:

- Turn 1 first product/delivery/assembly request returned `name-gate` only;
  escalation stayed `none`.
- Turn 2 `Lili` stored the name, consumed pending name-gate request, and resumed
  the original workstations/mobile drawers/delivery/assembly request.
- Turn 3 `The company is Memory Test LLC.` returned `detail-capture`; escalation
  stayed `none`.
- Turn 4 delivery address returned `detail-capture`; escalation stayed `none`.
- Turns 5-6 product comparison and quantity update stayed on the normal
  `z-ai/glm-5` product path; no manager handoff.
- Turn 7 assembly/no-quotation instruction returned `detail-capture`; no handoff.
- Turn 8 saved-context summary returned `saved-context-summary` with customer,
  company, address, products/quantities, `2-3 days`, assembly required, and quote
  hold.
- DB readback confirmed `customer_name=Lili`, `escalation_status=none`,
  no `name_gate_pending_request`, pending escalations `0`, and metadata contains
  `quote_customer_details` plus `sales_memory`.

# Risks / Follow-ups

No `tj-e2e16` defers remain. Lili's real WhatsApp thread was not mutated; only
the approved personal test number was cleaned and used.
