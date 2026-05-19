# Stage tj-gh17: GitHub #38 Sales Order SKU Resolver

Status: local implementation complete; not deployed
Branch: `codex/tj-gh17-sales-order-hardening`
Base: `origin/main@8483f36`
GitHub issue: `gh-38`
Beads: `tj-gh17`, `tj-gh17.1`, `tj-gh17.2`, `tj-gh17.3`, `tj-gh17.4`

## Scope

GitHub #38 reports that an explicit sales-order request:

`Can I have sales order ? I need 2 SKYLAND LUMA 9719-4 and 3 TORR Cabinet`

was handled as exact-quote fail-closed / manager verification and still sent
product photos. This stage fixes the deterministic runtime path without adding
prompt bulk.

## Implemented

- Added quantity-first sales-order parsing so explicit lists like
  `2 SKYLAND LUMA 9719-4 and 3 TORR Cabinet` become separate line candidates.
- Preserved existing item-before-quantity parsing for lists like
  `SKYLAND NOVO 1800 - 1 pcs and CH 620 black - 2 pcs`.
- Prevented generic exact-quote parsing from swallowing a multi-item
  sales-order list as one item.
- Added sales-order SKU hint handling that preserves numeric-hyphen fragments
  like `9719-4` and does not invent `LUMA-9719`.
- Added strict full-anchor matching for numeric-hyphen fragments so `9719-4`
  cannot resolve to a catalog product containing only `9719-5`.
- Kept unresolved or ambiguous sales-order items on pending quote clarification
  instead of manager escalation.
- Suppressed deferred product media after exact-quote fail-closed,
  exact-quote escalation, and verified-policy handoff.
- Tightened purchase-selection stated-price parsing so the word `and` is not
  interpreted as a currency after SKU suffixes.

## Context7

- PydanticAI docs confirmed `@agent.tool` with `RunContext[Deps]` is the
  supported pattern, so deterministic preprocessing can remain outside the tool
  prompt/schema path.
- SQLAlchemy 2.0 docs confirmed the repo's existing async
  `await session.execute(select(...))` style is current for ORM lookups.

## Delegation

- Spawned two visible read-only Codex explorers:
  - parser/catalog edge-case review for `tj-gh17.1`
  - deferred media leak review for `tj-gh17.3`
- No write-heavy worker was launched because all production changes converged on
  `src/llm/engine.py` and `tests/test_llm_engine.py`; parallel writes would have
  created conflict risk without meaningful speedup.
- Subagent findings were independently checked and incorporated where valid.

## Verification

- `OPENROUTER_API_KEY=dummy uv run pytest tests/test_llm_engine.py -k "quantity_before_item_list or rejects_multi_item_sales_order_list or quantity_before_item_unresolved or fails_closed_without_exact_sku" -q` -> initially failed before implementation, then passed.
- `OPENROUTER_API_KEY=dummy uv run pytest tests/test_llm_engine.py -k "sales_order or exact_quote or purchase_selection" -q` -> `52 passed`.
- `OPENROUTER_API_KEY=dummy uv run pytest tests/test_llm_engine.py -q` -> `165 passed`.
- `uv run ruff check src/ tests/` -> passed.
- `uv run ruff format --check src/ tests/` -> passed.
- `uv run mypy src/` -> passed.
- `env DYLD_FALLBACK_LIBRARY_PATH="${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}" OPENROUTER_API_KEY=dummy uv run pytest tests/ -v --tb=short` -> `1049 passed, 19 skipped`.
- `scripts/orchestration/run_process_verification.sh` -> passed.
- `uv run python scripts/orchestration/validate_artifact.py .codex/stages/tj-gh17/artifacts/tj-gh17-readonly-reviews.md` -> passed.
- `scripts/orchestration/check_stage_ready.py tj-gh17` -> passed.
- `OPENROUTER_API_KEY=dummy scripts/orchestration/run_stage_closeout.py --stage tj-gh17` -> passed.

## Delivery Boundary

- No deploy was performed.
- No production database or live WhatsApp state was mutated.
- GitHub #38 was not commented on or closed; that should wait for merge/deploy
  and, if approved, live E2E evidence.
