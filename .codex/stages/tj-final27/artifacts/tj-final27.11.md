---
schema_version: orchestration-artifact/v1
task_id: tj-final27.11
stage_id: tj-final27
repo: treejar
branch: codex/tj-final27-11-sales-fallback
base_branch: origin/main
base_commit: 93e9bc40f3c663a9f48fed6ab635064d7bbfa996
worktree: /home/me/code/treejar/.worktrees/codex-tj-final27-11-sales-fallback
status: merged
delivery_method: manual integration
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: Accepted content is preserved in main; source branch/worktree cleanup is complete or no longer applicable.
risk_level: medium
verification:
  - "bd delete tj-final27.12 --force: passed"
  - "bd update tj-final27.11 --status in_progress --append-notes ...: passed"
  - "uv run --extra dev python -m pytest -s tests/test_verified_answers.py::test_policy_routes_price_objection_to_sales_fallback tests/test_verified_answers.py::test_policy_routes_retention_dropoff_to_sales_fallback tests/test_verified_answers.py::test_policy_routes_known_off_catalog_request_to_sales_fallback tests/test_verified_answers.py::test_policy_keeps_payment_terms_on_manager_handoff tests/test_llm_engine.py::test_process_message_price_objection_uses_compact_sales_fallback tests/test_llm_engine.py::test_process_message_retention_uses_compact_sales_fallback tests/test_llm_engine.py::test_process_message_off_catalog_uses_compact_sales_fallback tests/test_llm_engine.py::test_process_message_payment_terms_still_use_manager_handoff -q: failed before implementation, 7 failed / 1 passed"
  - "uv run --extra dev python -m pytest -s tests/test_verified_answers.py::test_policy_routes_price_objection_to_sales_fallback tests/test_verified_answers.py::test_policy_routes_retention_dropoff_to_sales_fallback tests/test_verified_answers.py::test_policy_routes_known_off_catalog_request_to_sales_fallback tests/test_verified_answers.py::test_policy_keeps_payment_terms_on_manager_handoff tests/test_llm_engine.py::test_process_message_price_objection_uses_compact_sales_fallback tests/test_llm_engine.py::test_process_message_retention_uses_compact_sales_fallback tests/test_llm_engine.py::test_process_message_off_catalog_uses_compact_sales_fallback tests/test_llm_engine.py::test_process_message_payment_terms_still_use_manager_handoff -q: passed, 8 passed"
  - "uv run --extra dev python -m pytest -s tests/test_verified_answers.py tests/test_llm_engine.py -q: passed, 92 passed"
  - "uv run ruff check src/ tests/: passed"
  - "uv run ruff format --check src/ tests/: passed after formatting src/llm/verified_answers.py and tests/test_llm_engine.py"
  - "git diff --check: passed"
  - "uv run python scripts/orchestration/validate_artifact.py .codex/stages/tj-final27/artifacts/tj-final27.11.md: passed"
  - "uv run mypy src/: passed"
  - "env DYLD_FALLBACK_LIBRARY_PATH=\"${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}\" uv run pytest tests/ -v --tb=short: blocked by known pytest capture FileNotFoundError before collection"
  - "npm ci in frontend/admin: passed with Node 18 engine warnings and existing npm audit advisories"
  - "env DYLD_FALLBACK_LIBRARY_PATH=\"${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}\" uv run pytest -s tests/ -v --tb=short: passed, 826 passed / 19 skipped"
  - "scripts/orchestration/run_process_verification.sh: passed"
  - "bd close tj-final27.11 --reason ...: passed"
  - "main fast-forward merge and push: passed, 93e9bc4..2b841f9"
  - "GitHub Actions run 25149869000: passed, deploy job 73717907853 passed"
  - "Runtime release check: /opt/noor/.release-sha=2b841f95546137de4b698cecadc5a69dce9e813d, /api/v1/health ok, verify_api.py 7 passed / 0 failed"
  - "Controlled live WhatsApp E2E on 79262810921 with suffix tj-final27-11-*: price and retention returned no pending escalation but fell through to z-ai/glm-5; off-catalog returned z-ai/glm-5|sales-fallback"
  - "Hotfix RED targeted tests for live product objection/retention phrasings: failed, 4 failed"
  - "Hotfix GREEN targeted tests for live product objection/retention phrasings: passed, 4 passed"
  - "uv run --extra dev python -m pytest -s tests/test_verified_answers.py tests/test_llm_engine.py -q after hotfix: passed, 94 passed"
  - "ruff check, ruff format --check, git diff HEAD~1..HEAD --check, artifact validation, process verification, mypy after hotfix: passed"
  - "env DYLD_FALLBACK_LIBRARY_PATH=\"${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}\" uv run pytest -s tests/ -v --tb=short after hotfix: passed, 828 passed / 19 skipped"
  - "main second fast-forward merge and push: passed, 2b841f9..ab89787"
  - "GitHub Actions run 25150153084: passed, deploy job 73718851402 passed"
  - "Runtime release check: /opt/noor/.release-sha=ab897878e2f0ee339bd7626b63d5c6f3a9497042, /api/v1/health ok, verify_api.py 7 passed / 0 failed"
  - "Controlled live WhatsApp E2E on 79262810921 with suffix tj-final27-11-*-hotfix-20260430T060831Z: price, retention, and off-catalog all returned z-ai/glm-5|sales-fallback with escalation_status=none"
  - "Conversation API readback for phone_match=fuzzy tj-final27-11: total=6, pending=0"
changed_files:
  - src/llm/engine.py
  - src/llm/verified_answers.py
  - tests/test_llm_engine.py
  - tests/test_verified_answers.py
  - .codex/handoff.md
  - .codex/stages/tj-final27/summary.md
  - .codex/stages/tj-final27/artifacts/tj-final27.11.md
explicit_defers:
  - none
---

# Summary

Implemented a compact deterministic sales fallback for the three quality gaps found in `tj-final27.9`: price objection, retention/drop-off, and known off-catalog requests. The base system prompt was not expanded.

The removed DeepSeek sandbox follow-up (`tj-final27.12`) was deleted from Beads per user decision.

After the first production deploy, controlled live E2E showed that product-qualified price objection and retention messages were still routed through the main `z-ai/glm-5` sales path instead of the deterministic fallback, although they did not create pending escalations. A hotfix moved sales-fallback routing ahead of the product early return while preserving high-risk manager handoff. The hotfix was deployed to production as `main@ab897878e2f0ee339bd7626b63d5c6f3a9497042` and retested live.

# Changed Behavior

- Price objections like "too expensive" or competitor comparison no longer open a generic verified-policy manager handoff. Noor asks for competitor model/spec/price and offers a fair comparison without promising unapproved pricing.
- Retention/drop-off messages like "we don't need this anymore" no longer open manager escalation. Noor acknowledges the pause and gives a concise path to resume later with quantity, budget, and timeline.
- Known off-catalog requests such as helicopter spare parts or gaming laptops no longer open generic manager escalation. Noor says Treejar focuses on office furniture/workplace products and redirects to relevant categories.
- High-risk commitments still use the verified manager handoff. A regression test covers `net 30` plus `20% discount`.

# Implementation Notes

- Added a small `SalesFallbackIntent` detector in `src/llm/verified_answers.py`.
- Added short English/Arabic static responses via `build_sales_fallback_response()`.
- `process_message()` returns these as `model|sales-fallback` before the generic verified-policy handoff branch.
- Hotfix routes product-class price objections and retention/drop-off messages through the fallback before the product early return.
- The logic is intentionally deterministic and small to avoid prompt bloat and model drift.

# Verification

- RED targeted tests failed before implementation: `7 failed / 1 passed`.
- GREEN targeted tests passed: `8 passed`.
- Extended targeted suite passed before hotfix: `tests/test_verified_answers.py tests/test_llm_engine.py`, `92 passed`.
- First deploy evidence passed: GitHub Actions run `25149869000`, deploy job `73717907853`, runtime `.release-sha=2b841f95546137de4b698cecadc5a69dce9e813d`, health ok, `verify_api.py` `7 passed / 0 failed`.
- First live E2E on approved test number `79262810921` showed `0` pending escalations, but price objection and retention fell through to `z-ai/glm-5`; off-catalog used `z-ai/glm-5|sales-fallback`.
- Hotfix RED targeted tests failed on live product objection/retention phrasings: `4 failed`.
- Hotfix GREEN targeted tests passed on the same phrasings: `4 passed`.
- Extended targeted suite after hotfix passed: `tests/test_verified_answers.py tests/test_llm_engine.py`, `94 passed`.
- Full code gates after hotfix passed: ruff check, ruff format check, mypy, artifact validation, process verification, git diff check, and full pytest with capture disabled (`828 passed`, `19 skipped`).
- Final deploy evidence passed: GitHub Actions run `25150153084`, deploy job `73718851402`, runtime `.release-sha=ab897878e2f0ee339bd7626b63d5c6f3a9497042`, health ok, `verify_api.py` `7 passed / 0 failed`.
- Final controlled live WhatsApp E2E passed for `price_objection`, `retention`, and `off_catalog`: all three replies used `z-ai/glm-5|sales-fallback`, `escalation_status=none`, and conversation API readback for `tj-final27-11` showed `total=6`, `pending=0`.
- Plain full pytest without `-s` hit the already-known repo-local pytest capture `FileNotFoundError` before collection; the `-s` rerun passed after installing `frontend/admin` dependencies.

# Risks / Follow-ups / Explicit Defers

- The off-catalog detector is intentionally conservative and only covers known non-Treejar categories from the quality pass and obvious adjacent electronics terms. Unknown off-catalog goods may still take the existing manager-confirmation path.
- Live retest covered only text WhatsApp objection/fallback scenarios. No media, voice, payment, referral, feedback, broad production suite, `verify_wazzup.py`, or scheduled AI Quality Controls were run.
- `npm ci` reported Node 18 engine warnings for current frontend packages and existing npm audit advisories; no dependency updates were made in this task.
