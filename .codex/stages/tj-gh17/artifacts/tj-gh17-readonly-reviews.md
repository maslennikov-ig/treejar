---
schema_version: orchestration-artifact/v1
artifact_type: delegated-stream
task_id: tj-gh17-readonly-reviews
stage_id: tj-gh17
repo: treejar
branch: codex/tj-gh17-sales-order-hardening
base_branch: main
base_commit: 8483f36
worktree: /home/me/code/treejar/.worktrees/codex-tj-gh14-main-merge
status: accepted
delivery_method: manual integration
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: read-only spawned agents; no child worktree cleanup required
risk_level: medium
verification:
  - read-only subagent review; no files changed by subagents
  - OPENROUTER_API_KEY=dummy uv run pytest tests/test_llm_engine.py -k "sales_order or exact_quote or purchase_selection" -q: passed
changed_files:
  - src/llm/engine.py
  - tests/test_llm_engine.py
explicit_defers:
  - no deploy/live WhatsApp/GitHub closure until separately authorized
---

# Summary

Two read-only Codex explorers reviewed the GitHub #38 fix while implementation
continued locally.

## Parser / Catalog Review

- Confirmed the original sales-order parser was biased toward `ITEM - 1 pcs`
  lists, so `2 SKYLAND LUMA 9719-4 and 3 TORR Cabinet` could be misread by
  treating `-4` as a quantity separator.
- Confirmed the broad exact-quote parser could consume the first `2` and merge
  both requested products into one item.
- Recommended keeping catalog-backed matching in `_resolve_exact_quote_candidate_sku`
  rather than expanding prompts.
- Found one real residual risk: `SKYLAND LUMA 9719-4` could match a product
  containing `9719-5` because the generic token scorer drops one-character
  suffixes. This was fixed with a strict full numeric-hyphen anchor guard and
  regression test.

## Media Leak Review

- Confirmed exact-quote fail-closed could return queued product photos because
  `SalesDeps` copies shared the same `pending_product_media` list and the final
  static fail-closed response did not pass `allow_product_media=False`.
- Confirmed early exact-quote escalation and verified-policy handoff should also
  suppress deferred product media.
- Recommended implementing suppression in `src/llm/engine.py`, because
  `src/services/chat.py` sends whatever `LLMResponse.deferred_product_media`
  contains.

# Resulting Local Changes

- Added quantity-first sales-order parsing for GitHub #38.
- Prevented exact-quote fallback from swallowing multi-item sales-order lists.
- Added strict full-anchor resolution for numeric-hyphen model/SKU fragments.
- Suppressed product media after exact-quote fail-closed, exact-quote escalation,
  and verified-policy handoff.

# Verification

- `OPENROUTER_API_KEY=dummy uv run pytest tests/test_llm_engine.py -k "sales_order or exact_quote or purchase_selection" -q` -> `52 passed`.
- `OPENROUTER_API_KEY=dummy uv run pytest tests/test_llm_engine.py -q` -> `165 passed`.
- `uv run ruff check src/ tests/` -> passed.
- `uv run ruff format --check src/ tests/` -> passed.
- `uv run mypy src/` -> passed.
- `env DYLD_FALLBACK_LIBRARY_PATH="${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}" OPENROUTER_API_KEY=dummy uv run pytest tests/ -v --tb=short` -> `1049 passed, 19 skipped`.
- `scripts/orchestration/run_process_verification.sh` -> passed.

# Risks / Follow-ups / Explicit Defers

- No deploy, production mutation, live WhatsApp test, or GitHub issue closure was
  performed in this implementation step.
