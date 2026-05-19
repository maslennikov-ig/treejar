---
schema_version: orchestration-artifact/v1
artifact_type: live-e2e
task_id: tj-gh17.4
stage_id: tj-gh17
repo: treejar
branch: codex/tj-gh17-sales-order-hardening
base_branch: origin/main
base_commit: 8483f36
worktree: /home/me/code/treejar/.worktrees/codex-tj-gh14-main-merge
status: accepted
delivery_method: merge
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: Approved production test phone state was deleted in one audited transaction before live E2E.
risk_level: medium
verification:
  - "git pull --rebase": passed
  - "OPENROUTER_API_KEY=dummy uv run pytest tests/test_llm_engine.py -k \"sales_order or exact_quote or purchase_selection\" -q": passed, 52 passed
  - "uv run ruff check src/ tests/": passed
  - "uv run ruff format --check src/ tests/": passed
  - "uv run mypy src/": passed
  - "env DYLD_FALLBACK_LIBRARY_PATH=\"${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}\" OPENROUTER_API_KEY=dummy uv run pytest tests/ -v --tb=short": passed, 1049 passed and 19 skipped
  - "scripts/orchestration/run_process_verification.sh": passed
  - "OPENROUTER_API_KEY=dummy scripts/orchestration/run_stage_closeout.py --stage tj-gh17": passed
  - "git push -u origin codex/tj-gh17-sales-order-hardening": passed
  - "git push origin HEAD:main": passed, origin/main fast-forwarded to 3d24007713d5a2ca5068aeacc9c8719f101fe8d1
  - "GitHub Actions run 26083979252": passed
  - "ssh noor-server cat /opt/noor/.release-sha": passed, 3d24007713d5a2ca5068aeacc9c8719f101fe8d1
  - "uv run python scripts/verify_api.py --base-url https://noor.starec.ai": passed, 7 passed and 0 failed
  - "production SKU parser matrix": passed, 8 variants
  - "production direct runtime #38 check": passed, sales-order-clarify, no escalation, no media, pending quote stored
  - "production cleanup for 79262810921/+79262810921 prefixes": passed, before conversations/messages/outbound/escalations/manager_reviews/quality_reviews/conversation_summaries/feedbacks/llm_attempts 1/16/26/0/0/0/1/0/0, after all 0
  - "live webhook E2E conversation 58550f16-7530-4177-9980-224d1513c995": passed
changed_files:
  - src/llm/engine.py
  - tests/test_llm_engine.py
  - .codex/stages/tj-gh17/artifacts/tj-gh17-readonly-reviews.md
  - .codex/stages/tj-gh17/artifacts/tj-gh17.4-delivery-e2e.md
  - .codex/stages/tj-gh17/summary.md
  - .codex/handoff.md
explicit_defers:
  - none
---

# Summary

Delivered `tj-gh17` to production and verified GitHub #38 on the approved test
phone `79262810921`.

# SKU Matrix

The deployed production container passed parser coverage for:

- canonical quantity-first list:
  `2 SKYLAND LUMA 9719-4 and 3 TORR Cabinet`
- compact quantity marker:
  `2x SKYLAND LUMA 9719-4 and 3x TORR Cabinet`
- comma separator:
  `2 SKYLAND LUMA 9719-4, 3 TORR Cabinet`
- Cyrillic homoglyphs:
  `SКYLAND LUМА 9719-4` and `TОRR Cabinet` normalized to Latin
- SKU hyphen form:
  `CH-190`
- SKU spaced form:
  `CH 190`
- SKU compact form:
  `CH190`
- existing item-before-quantity form:
  `SKYLAND NOVO 1800 - 1 pcs and CH 620 black - 2 pcs`

The direct runtime check for the #38 sentence returned
`z-ai/glm-5|sales-order-clarify`, stored `pending_quote_selection`, and had
`escalation_status=none`, `deferred_media=0`, and `sent_media=0`.

# Live E2E

Production was deployed by GitHub Actions run `26083979252`; `/opt/noor/.release-sha`
is `3d24007713d5a2ca5068aeacc9c8719f101fe8d1`.

Approved test number cleanup cleared the existing matching state:

- before: 1 conversation, 16 messages, 26 outbound audit rows, 0 escalations,
  0 manager reviews, 0 quality reviews, 1 conversation summary, 0 feedbacks,
  0 LLM attempts
- after: all matching counts 0

Live conversation `58550f16-7530-4177-9980-224d1513c995`:

- Turn 1: `Can I have sales order ? I need 2 SKYLAND LUMA 9719-4 and 3 TORR Cabinet`
  returned `name-gate` only: "Hello, I'm Noor from Treejar. May I know your
  name so I can address you properly?"
- Turn 2: `Lili` stored `customer_name=Lili`, cleared
  `name_gate_pending_request`, resumed the original request, and returned
  `z-ai/glm-5|sales-order-clarify`: "I can prepare a sales order, but I need to
  confirm the exact catalog item(s) for: 3 x TORR Cabinet. Please share the SKU
  or choose the exact catalog option for each unresolved item."
- Final DB state: `escalation_status=none`, pending escalations `0`, outbound
  non-text media `0`, `pending_quote_selection` present, and no
  `name_gate_pending_request`.

# Verification

See the frontmatter `verification` list for the full command and evidence set.
The blocking delivery gates, production deploy, API smoke, SKU matrix, and live
webhook E2E all passed.

# Risks / Follow-ups

No `tj-gh17` defers remain.
