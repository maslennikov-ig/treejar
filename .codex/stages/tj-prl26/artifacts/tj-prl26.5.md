---
task_id: tj-prl26.5
stage_id: tj-prl26
repo: treejar
branch: codex/tj-prl26-prelaunch-readiness
base_branch: origin/main
base_commit: f1136fc2a6d6c8c49535b4460c89f3486b2521c1
worktree: /home/me/code/treejar/.worktrees/codex-tj-prl26-prelaunch-readiness
status: returned
verification:
  - production logs/read-only checks for SKU 00-07024023: passed
  - uv run --extra dev python -m pytest -s tests/test_llm_pii.py::test_mask_pii_keeps_numeric_sku_when_labeled -q: failed before fix
  - uv run --extra dev python -m pytest -s tests/test_llm_pii.py tests/test_llm_context.py tests/test_llm_engine.py -q: passed
  - uv run ruff check src/ tests/: passed
  - uv run ruff format --check src/ tests/: passed
  - uv run mypy src/: passed
changed_files:
  - src/llm/pii.py
  - tests/test_llm_pii.py
  - .codex/stages/tj-prl26/artifacts/tj-prl26.5.md
---

# Summary

Investigated and locally fixed launch blocker `tj-prl26.5`.

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

# Verification

- RED: `uv run --extra dev python -m pytest -s tests/test_llm_pii.py::test_mask_pii_keeps_numeric_sku_when_labeled -q` failed before the fix because `00-07024023` became `[PII-*]`.
- GREEN: `uv run --extra dev python -m pytest -s tests/test_llm_pii.py -q` -> `6 passed`.
- Relevant slice: `uv run --extra dev python -m pytest -s tests/test_llm_pii.py tests/test_llm_context.py tests/test_llm_engine.py -q` -> `62 passed`.
- `uv run ruff check src/ tests/` -> passed.
- `uv run ruff format --check src/ tests/` -> passed.
- `uv run mypy src/` -> passed.

# Risks / Follow-ups / Explicit Defers

- This is a local code fix only. It is not deployed yet.
- `tj-prl26.2` must stay blocked until this fix is deployed and the exact SKU synthetic E2E is rerun against production.
- No live recheck, deployment, config mutation, DB/Redis write, `verify_wazzup.py`, scheduled AI Quality Controls, broad production suite, or unsolicited media test was run for this fix.
