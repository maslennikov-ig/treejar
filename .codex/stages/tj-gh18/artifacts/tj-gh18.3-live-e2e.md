---
schema_version: orchestration-artifact/v1
artifact_type: live-e2e
task_id: tj-gh18.3
stage_id: tj-gh18
repo: treejar
branch: main
base_branch: origin/main
base_commit: 20bad53c2292
worktree: /home/me/code/treejar/.worktrees/codex-tj-gh14-main-merge
status: accepted
delivery_method: merge
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: Approved production test-phone state was deleted before E2E; no child worktrees or child branches remained. Synthetic evidence conversations were intentionally kept for audit.
risk_level: medium
verification:
  - git merge --ff-only codex/tj-gh18-open-issues-hardening: passed, main at 49d7d066e4ec1228bf0397e163c3196b6a74f831
  - git push origin main: passed
  - GitHub Actions run 26086747707: passed, deployed 49d7d066e4ec1228bf0397e163c3196b6a74f831
  - uv run python scripts/verify_api.py --base-url https://noor.starec.ai: passed, 7 passed and 0 failed
  - initial production SKU parser/policy matrix: failed, repeated-space CH   616 did not parse
  - OPENROUTER_API_KEY=dummy uv run pytest tests/test_llm_engine.py::test_extract_purchase_selection_accepts_generic_sku_spacing_variants tests/test_llm_engine.py::test_context_purchase_selection_accepts_bare_quantity_sku_after_product_choice tests/test_llm_engine.py::test_process_message_ch616_selection_confirms_without_manager_handoff tests/test_verified_answers.py::test_policy_routes_generic_sku_quantity_selection_to_product_path -v --tb=short: passed, 7 passed
  - uv run ruff check src/ tests/: passed
  - uv run ruff format --check src/ tests/: passed
  - uv run mypy src/: passed
  - env DYLD_FALLBACK_LIBRARY_PATH="${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}" OPENROUTER_API_KEY=dummy uv run pytest tests/ -v --tb=short: passed, 1057 passed and 19 skipped
  - git push origin main: passed, hotfix commit af39abc4a1f299eb2c37af916c14d476ea2ab1b7
  - GitHub Actions run 26087478319: passed, deployed af39abc4a1f299eb2c37af916c14d476ea2ab1b7
  - ssh noor-server cat /opt/noor/.release-sha: passed, af39abc4a1f299eb2c37af916c14d476ea2ab1b7
  - uv run python scripts/verify_api.py --base-url https://noor.starec.ai: passed, 7 passed and 0 failed
  - final production SKU parser/policy matrix: passed
  - live webhook #39 conversation e3b12221-7206-4be8-8e59-d70d0732d446: passed
  - live webhook #35 media conversation d331625b-84be-442e-9b6a-f92ce6139101: passed
changed_files:
  - src/llm/engine.py
  - src/llm/prompts.py
  - src/llm/verified_answers.py
  - tests/test_llm_engine.py
  - tests/test_outbound_audit.py
  - tests/test_services_chat_batch.py
  - tests/test_verified_answers.py
  - .codex/stages/tj-gh18/artifacts/tj-gh18.1-2.md
  - .codex/stages/tj-gh18/artifacts/tj-gh18.3-live-e2e.md
  - .codex/stages/tj-gh18/summary.md
  - .codex/handoff.md
explicit_defers:
  - none for tj-gh18
---

# Summary

Delivered `tj-gh18` to production and completed deployed E2E for GitHub #39 and
#35 on the approved production test number `79262810921`.

# Delivery

The feature branch was fast-forward merged to `main` and deployed by GitHub
Actions run `26086747707` at release
`49d7d066e4ec1228bf0397e163c3196b6a74f831`.

The first production matrix caught a related SKU spacing defect:
`I need   6   CH   616` did not parse. I fixed it with a narrow SKU-regex
hotfix, added a regression case, re-ran local gates, pushed
`af39abc4a1f299eb2c37af916c14d476ea2ab1b7`, and verified GitHub Actions run
`26087478319` deployed it. `/opt/noor/.release-sha` and `.release-run-id` match
that final run.

# E2E Evidence

Approved cleanup for `79262810921%` / `+79262810921%` removed 1 conversation,
4 messages, and 2 outbound audit rows; after cleanup all matching counts were 0.

Final #39 live webhook conversation
`e3b12221-7206-4be8-8e59-d70d0732d446`:

- first turn returned `name-gate`;
- bare `Lili` stored `customer_name=Lili`;
- `I need   6   CH   616` returned
  `z-ai/glm-5|selection-confirmation`;
- DB metadata stored pending quote item `CH 616 NEW black` quantity `6`;
- `escalation_status=none` and pending escalations `0`.

Final production SKU matrix passed:

- `I need 6 CH 616`
- `I want 6 CH-616`
- `I need 6 CH616`
- lowercase `ch 616`
- Cyrillic homoglyph `СН 616`
- repeated spaces `CH   616`
- bare `6 CH 616` rejected without product-choice context
- bare `6 CH 616` accepted after assistant product-choice prompt
- verified-policy classified SKU quantity selections as `product/allow` with no
  manager handoff.

Final #35 live media conversation
`d331625b-84be-442e-9b6a-f92ce6139101`:

- product recommendation produced 3 product media rows with provider message ids;
- 3 hidden caption audit rows were retained with `provider_message_id=NULL`;
- every hidden caption row had `details={"customer_visible": false}`;
- no separate customer-visible caption text was sent.

# Verification

See the frontmatter `verification` list for the full command and deployment
evidence set. Local gates, GitHub Actions deploy, production API smoke, SKU
matrix, live #39, and live #35 all passed.

# Risks / Follow-ups

No `tj-gh18` defers remain. GitHub #11 remains outside this stage and still
waits for Lilia's answers.
