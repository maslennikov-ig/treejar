---
schema_version: orchestration-artifact/v1
artifact_type: delegated-stream
task_id: tj-gh19.3
stage_id: tj-gh19
repo: treejar
branch: main
base_branch: origin/main
base_commit: b05422e1fb6647ffda7a10c337eef9c7c922273d
worktree: /home/me/code/treejar/.worktrees/codex-tj-gh14-main-merge
status: accepted
delivery_method: merge
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: Synthetic failed E2E escalation was resolved in production; no child write worktrees were created for this delivery step.
risk_level: medium
verification:
  - OPENROUTER_API_KEY=dummy uv run pytest tests/test_llm_engine.py tests/test_verified_answers.py -v --tb=short: passed, 215 passed
  - uv run ruff check src/ tests/: passed
  - uv run ruff format --check src/ tests/: passed
  - uv run mypy src/: passed
  - env DYLD_FALLBACK_LIBRARY_PATH="${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}" OPENROUTER_API_KEY=dummy uv run pytest tests/ -v --tb=short: passed, 1066 passed, 19 skipped
  - OPENROUTER_API_KEY=dummy scripts/orchestration/run_stage_closeout.py --stage tj-gh19: passed
  - GitHub Actions CI/deploy run 26094670599: passed
  - uv run python scripts/verify_api.py --base-url https://noor.starec.ai: passed, 7 passed, 0 failed
changed_files:
  - src/llm/engine.py
  - tests/test_llm_engine.py
  - .codex/handoff.md
  - .codex/stages/tj-gh19/summary.md
  - .codex/stages/tj-gh19/artifacts/tj-gh19.3-live-e2e.md
explicit_defers:
  - GitHub #11 remains pending Lilia's answers.
  - tj-b4n / GitHub #24 remains provider-blocked pending an official Wazzup typing endpoint.
---

# Summary

Delivered `tj-gh19` and closed GitHub #40 after deployed production evidence.

The final production release is `b05422e1fb6647ffda7a10c337eef9c7c922273d`,
deployed by GitHub Actions run `26094670599`; `/opt/noor/.release-sha`
matches. Production smoke against `https://noor.starec.ai` passed with
`7 passed, 0 failed`.

# Verification

- Local targeted suite:
  `OPENROUTER_API_KEY=dummy uv run pytest tests/test_llm_engine.py tests/test_verified_answers.py -v --tb=short`
  -> `215 passed`.
- Local static gates: `ruff check`, `ruff format --check`, and `mypy` passed.
- Local full suite:
  `env DYLD_FALLBACK_LIBRARY_PATH="${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}" OPENROUTER_API_KEY=dummy uv run pytest tests/ -v --tb=short`
  -> `1066 passed, 19 skipped`.
- Stage closeout:
  `OPENROUTER_API_KEY=dummy scripts/orchestration/run_stage_closeout.py --stage tj-gh19`
  -> passed.
- GitHub Actions CI/deploy run `26094670599` -> passed.
- Production smoke:
  `uv run python scripts/verify_api.py --base-url https://noor.starec.ai`
  -> `7 passed, 0 failed`.
- Live E2E conversation `640d0cfb-0460-4033-b6f0-7de84eadcc2a` -> passed.

# Production E2E

Final clean synthetic/live conversation:
`640d0cfb-0460-4033-b6f0-7de84eadcc2a`.

Observed flow:

- `I need SKYLAND NOVO 2400 Meeting Table and CH 616` -> `name-gate`.
- `Lil` -> `z-ai/glm-5|product-quantity-clarify`; the bot asked for quantities
  for `SKYLAND NOVO 2400 Meeting Table` and `CH 616`, with no `2400` item
  quantity and no escalation.
- `1 CH 616` -> bot remembered the table context and asked only for the
  `SKYLAND NOVO 2400 Meeting Table` quantity.
- `1 SKYLAND NOVO 2400 Meeting Table` -> bot returned catalog facts for the
  table and CH 616 variants and asked which CH 616 variant was preferred.
- `one Skyland Operative Chair CH 616 NEW black` ->
  `z-ai/glm-5|selection-confirmation`; pending quote selection was stored.
- `Lil, 1 dubay` -> `z-ai/glm-5|quote-resume-missing-details`; the bot stored
  `name=Lil` and `address=1 dubay`, preserved `pending_quote_selection`, asked
  only for company name or individual confirmation, and did not escalate.

Final conversation metadata showed:

- `quote_customer_details`: `{"name": "Lil", "address": "1 dubay"}`
- `pending_quote_selection`: one selected CH 616 item with quantity `1`
- `escalation_status`: `none`

# E2E Findings During Delivery

The first deployed release (`15785943804fff52a4c55259c1eb7785e33ebe46`) fixed
the local regressions but live E2E found that an assistant-generated item table
could ask for quote details without storing `pending_quote_selection`; `Lil, 1
dubay` then fell into verified-policy handoff. This produced synthetic
conversation `1ffc309a-287c-4b9b-903b-515f54829cd2`.

Hotfix `30d8975af45668d6039bc9fd9582efe337b0f25a` added assistant-table
recovery. Live E2E then found a second edge case where the resumed exact product
reference after name-gate could still return a generic LLM preference line.

Final hotfix `b05422e1fb6647ffda7a10c337eef9c7c922273d` added a deterministic
quantity-clarification path for exact product references without quantities,
bounded away from price/availability/payment-term cases.

The synthetic failed E2E escalation in conversation
`1ffc309a-287c-4b9b-903b-515f54829cd2` was resolved in production after the
final fix, so no manager action remains from the test.

# GitHub And Beads

GitHub #40 was commented with release, local verification, production smoke, and
live E2E evidence, then closed.

Beads `tj-gh19`, `tj-gh19.1`, `tj-gh19.2`, and `tj-gh19.3` are closed.

# Risks / Follow-ups

- The live quotation was not continued into PDF creation from the synthetic
  chat because the issue acceptance was the context/missing-details gate, and
  creating/sending a production quotation would add unnecessary external side
  effects for this regression.
- GitHub #11 remains out of scope until Lilia answers its pending questions.
- GitHub #24 / `tj-b4n` remains provider-blocked until Wazzup exposes an
  official typing endpoint.
