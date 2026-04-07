# Inbound Channel Phone Gating Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Persist the true inbound WhatsApp number per conversation and allow Telegram escalation-related alerts only for the configured test inbound number.

**Architecture:** Keep `channelId` as the transport identifier from Wazzup, resolve it to `plainId` through the Wazzup channels API, and persist both values in `Conversation.metadata`. Centralize normalization and alert gating so escalation and manager-review paths use the same rule.

**Tech Stack:** FastAPI, SQLAlchemy ORM, Pydantic Settings, httpx, pytest.

---

### Task 1: Add failing tests for inbound channel phone resolution

**Files:**
- Modify: `tests/test_messaging_wazzup.py`

**Step 1: Write the failing test**

- Add a test for a new Wazzup provider method that resolves a phone number from `channelId`.
- Verify it reads `plainId` from the channels API response and normalizes the number.

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_messaging_wazzup.py -k inbound -v`

**Step 3: Write minimal implementation**

- Add a channels API call on `WazzupProvider`.
- Add phone normalization helper.

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_messaging_wazzup.py -k inbound -v`

### Task 2: Add failing tests for conversation metadata persistence

**Files:**
- Modify: `tests/test_services_chat_batch.py`

**Step 1: Write the failing test**

- Add a batch-processing test that ensures `Conversation.metadata_` gets `inbound_channel_id` and `inbound_channel_phone`.

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_services_chat_batch.py -k inbound_channel -v`

**Step 3: Write minimal implementation**

- Resolve inbound phone during batch processing.
- Persist metadata with reassignment so SQLAlchemy tracks the JSON update.

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_services_chat_batch.py -k inbound_channel -v`

### Task 3: Add failing tests for Telegram alert gating

**Files:**
- Modify: `tests/test_order_review_flow.py`
- Modify: `tests/test_manager_job.py`

**Step 1: Write the failing test**

- Add an escalation test showing Telegram is skipped when inbound phone is not allowed.
- Add a manager-job test showing low-score alerts are skipped when inbound phone is not allowed.

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_order_review_flow.py tests/test_manager_job.py -k inbound -v`

**Step 3: Write minimal implementation**

- Add the new setting for allowed inbound alert phone.
- Centralize alert gating helpers.
- Use the helper in escalation and manager job paths.

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_order_review_flow.py tests/test_manager_job.py -k inbound -v`

### Task 4: Run focused then repo-level verification

**Files:**
- Modify: `src/core/config.py`
- Modify: `src/integrations/messaging/wazzup.py`
- Modify: `src/services/chat.py`
- Modify: `src/integrations/notifications/escalation.py`
- Modify: `src/quality/manager_job.py`

**Step 1: Run focused tests**

Run: `uv run pytest tests/test_messaging_wazzup.py tests/test_services_chat_batch.py tests/test_order_review_flow.py tests/test_manager_job.py -v --tb=short`

**Step 2: Run repo verification**

Run:
- `uv run ruff check src/ tests/`
- `uv run ruff format --check src/ tests/`
- `uv run mypy src/`
- `uv run pytest tests/ -v --tb=short`

**Step 3: Update Beads task**

- Record implementation and verification outcome in `tj-8cs3`.
