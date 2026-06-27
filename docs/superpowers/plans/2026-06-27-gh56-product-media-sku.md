# GH56 Product Media SKU Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent product media from showing images that are not grounded to the exact product/SKU presented to the customer.

**Architecture:** Keep the fix in the product-search/media boundary. First prove that `search_products` can queue media for unrelated weak results, then add the smallest guard so media is sent only when the result set is reliably product-grounded.

**Tech Stack:** Python 3.13, pytest, Pydantic models, existing `SalesDeps` and `ProductMediaPayload`.

## Global Constraints

- Beads task: `tj-jyig`, external ref `gh-56`.
- Worktree: `/home/me/code/treejar/.worktrees/tj-gh56-product-media-sku`.
- No live WhatsApp sends, deploys, production mutations, or catalog data writes.
- TDD: write a failing test before changing runtime code.

---

### Task 1: Reproduce Unsafe Product Media Queueing

**Files:**
- Modify: `tests/test_product_images.py`
- Read: `src/llm/engine.py`

**Interfaces:**
- Consumes: `search_products(run_context, query)` and `SalesDeps.pending_product_media`.
- Produces: a regression that fails while weak/nearby product results still queue media.

- [ ] **Step 1: Write the failing test**

Add a test that returns one exact convertible sleeper product and one weak normal-chair product from `rag_search_products`, enables `defer_product_media`, calls `search_products(run_context, "Convertible chairs")`, and asserts only the exact sleeper image is queued.

- [ ] **Step 2: Run test to verify it fails**

Run: `OPENROUTER_API_KEY=dummy uv run pytest tests/test_product_images.py::test_search_products_defers_media_only_for_exact_grounded_matches -q`

Expected: FAIL because both product images are queued.

- [ ] **Step 3: Implement minimal guard**

Modify `src/llm/engine.py` so weak/nearby catalog matches do not queue media that the final assistant text might not mention. Keep customer-facing text intact.

- [ ] **Step 4: Run targeted tests**

Run: `OPENROUTER_API_KEY=dummy uv run pytest tests/test_product_images.py -q`

Expected: PASS.

### Task 2: Verify Integration Boundary

**Files:**
- Read/modify if needed: `tests/test_services_chat_batch.py`
- Read: `src/services/chat.py`

**Interfaces:**
- Consumes: `LLMResponse.deferred_product_media` and `_send_deferred_product_media`.
- Produces: confidence that deferred media still sends after text for safe product media.

- [ ] **Step 1: Run existing deferred media test**

Run: `OPENROUTER_API_KEY=dummy uv run pytest tests/test_services_chat_batch.py::test_process_incoming_batch_sends_deferred_product_media_after_bot_reply -q`

Expected: PASS.

- [ ] **Step 2: Add or adjust only if Task 1 changes the contract**

If deferred media payload shape changes, update this test to assert the new safe contract. If the payload shape does not change, leave it untouched.

### Task 3: Closeout Checks

**Files:**
- Read/modify if current truth changes: `.codex/handoff.md`, `.codex/stages/tj-gh56-product-media-sku/summary.md`

**Interfaces:**
- Consumes: code/test results and subagent findings.
- Produces: stage evidence and docs/graph review status.

- [ ] **Step 1: Run focused gates**

Run:
`OPENROUTER_API_KEY=dummy uv run pytest tests/test_product_images.py tests/test_services_chat_batch.py::test_process_incoming_batch_sends_deferred_product_media_after_bot_reply -q`

- [ ] **Step 2: Run repo quality checks as risk requires**

Run:
`uv run ruff check src/ tests/`
`uv run ruff format --check src/ tests/`
`uv run mypy src/`

- [ ] **Step 3: Record closeout**

Update Beads and stage summary with verification evidence. Report `docs-reviewed: no-change-needed` if no public API/operator docs changed. Report `graph-reviewed: no-change-needed` because Graphify is not configured.
