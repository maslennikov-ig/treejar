---
schema_version: orchestration-artifact/v1
artifact_type: live-e2e
task_id: tj-gh14-delivery.3
stage_id: tj-gh14-delivery
repo: treejar
branch: main
base_branch: origin/main
base_commit: 76ea00fc32ba59974fb1430f1fbc7dde7f47dc74
worktree: /home/me/code/treejar/.worktrees/codex-tj-gh14-main-merge
status: accepted
delivery_method: merge
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: Local hotfix worktree and branch codex/tj-gh14-live-e2e-hotfix were removed after merge.
risk_level: high
verification:
  - "uv run ruff check src/ tests/": passed
  - "uv run ruff format --check src/ tests/": passed
  - "uv run mypy src/": passed
  - "env OPENROUTER_API_KEY=dummy DYLD_FALLBACK_LIBRARY_PATH=\"${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}\" uv run pytest tests/ -v --tb=short": passed
  - "scripts/orchestration/run_process_verification.sh --stage tj-gh14-delivery": passed
  - "GitHub Actions CI 25872745415": passed
  - "uv run python scripts/verify_api.py --base-url https://noor.starec.ai": passed
  - "Live WhatsApp E2E via scripts/bot_test.py on approved number +79262810921": passed
changed_files:
  - src/llm/engine.py
  - tests/test_llm_engine.py
  - .codex/stages/tj-gh14-delivery/artifacts/tj-gh14-delivery-live-e2e.md
explicit_defers:
  - "No GitHub issue comments/closures were performed."
  - "No production config mutation was performed."
---

# Summary

Live WhatsApp E2E passed on the user-approved personal number
`+79262810921` after deploying hotfix release
`7075be5831dd0e09e29a319d842003f24c6dcf0f`.

The first live attempt exposed a real blocker: `Hi, I need 5 x CH 190.`
was stored through first-turn name gate, but the resumed request escalated
instead of entering exact quote missing-data flow. Root cause was deterministic
SKU parsing/resolution around punctuated and spaced SKU aliases.

# Hotfix Delivery

- `7966ac9b6512f4215aa178bcf1379f8c5932428d`:
  `fix(runtime): accept punctuated bare sku quote requests`
- `7075be5831dd0e09e29a319d842003f24c6dcf0f`:
  `fix(runtime): resolve spaced sku quote aliases`
- `origin/codex/tj-gh14-live-e2e-hotfix` was pushed.
- `main` was fast-forwarded and pushed to `7075be5`.
- GitHub Actions run `25872745415` passed `changes`, `lint`, `test`,
  `type-check`, and `deploy`.
- Production `/opt/noor/.release-sha` equals
  `7075be5831dd0e09e29a319d842003f24c6dcf0f`.

# Verification

Final hotfix verification:

- `uv run ruff check src/ tests/` -> passed.
- `uv run ruff format --check src/ tests/` -> passed.
- `uv run mypy src/` -> passed.
- `env OPENROUTER_API_KEY=dummy DYLD_FALLBACK_LIBRARY_PATH="${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}" uv run pytest tests/ -v --tb=short`
  -> `1019 passed, 19 skipped`.
- `scripts/orchestration/run_process_verification.sh --stage tj-gh14-delivery`
  -> passed.

Production smoke:

- `uv run python scripts/verify_api.py --base-url https://noor.starec.ai`
  -> `7 passed, 0 failed`.

# Live E2E Evidence

Approved live number: `+79262810921`.

## Scenario A: Name Gate + CH 190 Quote Resume

Synthetic chat suffix:
`79262810921#tj-gh14-live-quote-20260514165102`.

Conversation ID: `451d7d3b-af68-4d37-b154-c47b787df744`.

Steps:

1. Sent `Hi, I need 5 x CH 190.`
   - Marker: `[smoke:afb1bb68]`
   - Assistant model: `name-gate`
   - Reply: asked for the customer's name only.
   - Escalation status: `none`
2. Sent `My name is E2E Tester.`
   - Marker: `[smoke:a6e85238]`
   - Assistant model: `z-ai/glm-5|exact-quote-missing-details`
   - Reply: requested company-or-individual confirmation and specific delivery
     address before preparing the quotation.
   - Escalation status: `none`

DB readback:

- `customer_name = E2E Tester`
- `escalation_status = none`
- `escalations = 0`
- `metadata.pending_quote_selection = {"source": "exact_quote", "items": [{"sku": "CH-190", "quantity": 5}], "unresolved_items": []}`
- Outbound audits: two `bot_reply` text sends, no manager handoff.

## Scenario B: Product + Quantity No Handoff + Media Captions

Synthetic chat suffix:
`79262810921#tj-gh14-live-product-20260514165102`.

Conversation ID: `866e8e62-d760-443b-86b8-4d0c913ab90c`.

Steps:

1. Sent name capture messages for `E2E Product Tester`.
2. Sent `I need 5 office chairs.`
   - Marker: `[smoke:cf5e96cf]`
   - Assistant model: `z-ai/glm-5`
   - Reply: product options for office chairs, not order confirmation handoff.
   - Escalation status: `none`

DB readback:

- `customer_name = E2E Product Tester`
- `escalation_status = none`
- `escalations = 0`
- Product media rows were created and sent for media only.
- Product caption audit rows have `provider_message_id = None` and
  `details = {"customer_visible": false}`.
- Product media audit rows have provider message ids and `caption = None`.

# Risks / Follow-ups

No GitHub issue comments/closures were made. No production configuration was
changed. The only live external side effects were the approved WhatsApp test
messages/media to `+79262810921`.
