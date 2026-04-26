---
task_id: tj-prl26.5
stage_id: tj-prl26
repo: treejar
branch: codex/tj-prl26-prelaunch-readiness
base_branch: origin/main
base_commit: f1136fc2a6d6c8c49535b4460c89f3486b2521c1
worktree: /home/me/code/treejar/.worktrees/codex-tj-prl26-prelaunch-readiness
status: deployed-rechecked
verification:
  - production logs/read-only checks for SKU 00-07024023: passed
  - uv run --extra dev python -m pytest -s tests/test_llm_pii.py::test_mask_pii_keeps_numeric_sku_when_labeled -q: failed before fix
  - uv run --extra dev python -m pytest -s tests/test_llm_pii.py tests/test_llm_context.py tests/test_llm_engine.py -q: passed
  - uv run ruff check src/ tests/: passed
  - uv run ruff format --check src/ tests/: passed
  - uv run mypy src/: passed
  - GitHub Actions run 24963241165 for d93b954: passed
  - post-deploy uv run python scripts/verify_api.py --base-url https://noor.starec.ai: passed
  - post-deploy release SHA/Alembic/health/auth guards: passed
  - production SKU recheck conversation 8ad66895-1caa-45df-9f03-8907cc96f21f: passed
changed_files:
  - src/llm/pii.py
  - tests/test_llm_pii.py
  - .codex/stages/tj-prl26/artifacts/tj-prl26.5.md
  - .codex/stages/tj-prl26/summary.md
  - .codex/handoff.md
---

# Summary

Investigated, fixed, deployed, and narrowly rechecked launch blocker `tj-prl26.5`.

Root cause: the generic phone PII regex masked the exact product SKU `00-07024023` in the customer message as a `[PII-*]` placeholder before the LLM/tool roundtrip. Production logs show the worker executed `get_stock(sku='[PII-4ae8]')`, so the tool searched for the placeholder instead of the actual SKU and the assistant told the customer the active SKU did not exist.

Production read-only evidence:

- Conversation: `23ce4397-93e8-4b81-97f0-33846d7f795c`.
- User asked for `SKU 00-07024023`.
- Worker log: `LLM Tool called: get_stock(sku='[PII-4ae8]')`.
- Product table exact lookup: SKU `00-07024023`, name `Rectangular operative table, IMAGO-S, SP-3.1SD, 1400x600x755, White/aluminum`, price `264.00`, stock `12`, `zoho_item_id=378603000001589001`, active, embedding present.
- Zoho `get_stock("00-07024023")` returned the item with stock `12.0`, rate `685.0`, item id `378603000001589001`.
- Zoho `get_stock("00-07024023.")` and `get_stock("SKU 00-07024023")` returned `None`, confirming the lookup is exact and sensitive to the value passed.

Fix:

- `mask_pii()` now preserves numeric strings when they are directly labeled as product identifiers (`SKU`, `model`, `item`, `article`, or `product code`).
- Existing phone and email masking behavior is preserved.

Deployment/recheck:

- Commit `d93b95480ec4ca53459f3a0bd527b1a27eb73358` was pushed to `main`.
- GitHub Actions run `24963241165` completed successfully, including deploy.
- Production `/opt/noor/.release-sha` reports `d93b95480ec4ca53459f3a0bd527b1a27eb73358`; `/opt/noor/.release-run-id` reports `24963241165`.
- Post-deploy `uv run python scripts/verify_api.py --base-url https://noor.starec.ai` -> `7 passed, 0 failed`.
- Post-deploy `/api/v1/health` -> ok with Redis ok; anonymous `/dashboard/` -> `401`; anonymous `/api/v1/conversations/` -> `403`; Alembic -> `2026_04_26_outbound_audit (head)`.
- Narrow synthetic production recheck conversation `8ad66895-1caa-45df-9f03-8907cc96f21f` for `79262810921#tj-prl26-sku-recheck-20260426180210` returned SKU `00-07024023`, stock `12`, and price `685.00 AED` instead of saying the SKU does not exist.
- Read-only DB readback for the recheck found `escalation_status='none'`, pending recheck conversations `0`, persisted user/assistant messages, and outbound audit `f3f63b53-5b98-4c96-9979-569b03544c16` with `status='sent'`, provider message id, and `crm_message_id`.

# Verification

- RED: `uv run --extra dev python -m pytest -s tests/test_llm_pii.py::test_mask_pii_keeps_numeric_sku_when_labeled -q` failed before the fix because `00-07024023` became `[PII-*]`.
- GREEN: `uv run --extra dev python -m pytest -s tests/test_llm_pii.py -q` -> `6 passed`.
- Relevant slice: `uv run --extra dev python -m pytest -s tests/test_llm_pii.py tests/test_llm_context.py tests/test_llm_engine.py -q` -> `62 passed`.
- `uv run ruff check src/ tests/` -> passed.
- `uv run ruff format --check src/ tests/` -> passed.
- `uv run mypy src/` -> passed.
- GitHub Actions run `24963241165` -> passed: `changes`, `lint`, `test`, `type-check`, `deploy`.
- Post-deploy smoke -> passed: `verify_api.py` 7/0, health ok, auth guards 401/403, release SHA and Alembic head verified.
- Narrow production SKU recheck -> passed: conversation `8ad66895-1caa-45df-9f03-8907cc96f21f` returned stock and price for SKU `00-07024023`.

# Risks / Follow-ups / Explicit Defers

- The specific blocker is resolved: production no longer masks labeled SKU `00-07024023` before stock lookup.
- The bot currently reports Zoho exact rate `685.00 AED`; the products table/public catalog row observed during investigation had price `264.00`. This is not treated as this blocker because the repo handoff says Zoho is exact stock/price truth, but it is worth watching during broader acceptance.
- `tj-prl26.2` still needs to be rerun for quotation, manager, escalation, and closeout branches; those branches were intentionally skipped when the original blocker appeared.
- No `verify_wazzup.py`, scheduled AI Quality Controls, broad production suite, unsolicited media test, production config mutation, secret change, or manual DB/Redis mutation was run.
