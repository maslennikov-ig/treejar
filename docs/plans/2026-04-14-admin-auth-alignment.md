# Admin Auth Alignment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** unify admin auth across `/admin`, `/dashboard`, and `/api/v1/admin/*`, and protect manual product sync with real integration coverage.

**Architecture:** move the session boundary to the root FastAPI app so one admin session cookie can be read by both SQLAdmin and the custom dashboard/API routes. Keep SQLAdmin login as the credential gate, then extend that same session to dashboard serving and selected operator actions.

**Tech Stack:** FastAPI, Starlette `SessionMiddleware`, SQLAdmin 0.23.0, httpx ASGI integration tests, pytest

---

### Task 1: Add regression tests for the real admin login flow

**Files:**
- Modify: `tests/test_api_admin.py`
- Modify: `tests/conftest.py`

**Step 1: Write the failing tests**

- Add a test that uses a plain `client` (not `admin_client`) to verify:
  - anonymous `GET /dashboard/` is not `200`
  - anonymous `GET /api/v1/admin/dashboard/metrics/` is `401`
  - `POST /admin/login` succeeds
  - the same client can then reach `/admin/`, `/dashboard/`, and `/api/v1/admin/dashboard/metrics/`
- Add a focused test for `POST /api/v1/products/sync` proving anonymous access is rejected.

**Step 2: Run the targeted tests to verify RED**

Run:
`env OPENROUTER_API_KEY=test-key WAZZUP_API_KEY=fake-wazzup-key WAZZUP_API_URL=http://fake-wazzup-url LOGFIRE_IGNORE_NO_CONFIG=1 uv run pytest tests/test_api_admin.py -q`

Expected:
- The new real-flow auth test fails because `/dashboard/` is still open and/or the logged-in client still gets `401` from the admin API.
- The new product sync protection test fails because the route is currently open.

### Task 2: Move the session boundary to the root app

**Files:**
- Modify: `src/main.py`
- Modify: `src/api/admin/auth.py`
- Modify: `src/api/v1/admin.py`

**Step 1: Implement root-level session middleware**

- Add `SessionMiddleware` to the root FastAPI app in `create_app()`.
- Make sure the admin auth backend does not reintroduce an isolated second session boundary for `/admin`.

**Step 2: Protect dashboard routes**

- Apply `require_admin_session` to dashboard entry/client-side routes.
- Keep static asset serving intact for authenticated use.

**Step 3: Verify GREEN on targeted auth tests**

Run:
`env OPENROUTER_API_KEY=test-key WAZZUP_API_KEY=fake-wazzup-key WAZZUP_API_URL=http://fake-wazzup-url LOGFIRE_IGNORE_NO_CONFIG=1 uv run pytest tests/test_api_admin.py tests/test_api_admin_auth.py -q`

Expected:
- The real login-flow test passes.
- Existing auth unit tests still pass.

### Task 3: Protect manual product sync

**Files:**
- Modify: `src/api/v1/products.py`
- Modify: `tests/test_api_products.py`
- Optionally modify: `src/api/v1/router.py`

**Step 1: Implement the minimal protection**

- Guard only the manual sync route with `require_admin_session`.
- Do not change public product listing/search behavior.

**Step 2: Add/update tests**

- Keep existing public product tests for read/search behavior.
- Add/update sync tests so anonymous sync is rejected and an authenticated admin session can enqueue the job.

**Step 3: Run the targeted tests**

Run:
`env OPENROUTER_API_KEY=test-key WAZZUP_API_KEY=fake-wazzup-key WAZZUP_API_URL=http://fake-wazzup-url LOGFIRE_IGNORE_NO_CONFIG=1 uv run pytest tests/test_api_admin.py tests/test_api_products.py -q`

Expected:
- Sync protection behaves as intended.
- Public product reads/search remain green.

### Task 4: Remove false confidence from auth-bypassed integration coverage

**Files:**
- Modify: `tests/conftest.py`
- Modify: `tests/test_api_admin.py`

**Step 1: Narrow the bypass fixture**

- Keep an auth-bypass fixture only where a unit-style shortcut is explicitly needed.
- Do not use it for tests claiming end-to-end admin integration.

**Step 2: Verify targeted test coverage**

Run:
`env OPENROUTER_API_KEY=test-key WAZZUP_API_KEY=fake-wazzup-key WAZZUP_API_URL=http://fake-wazzup-url LOGFIRE_IGNORE_NO_CONFIG=1 uv run pytest tests/test_api_admin.py tests/test_api_admin_auth.py tests/test_api_internal_auth.py tests/test_api_products.py -q`

Expected:
- Real auth coverage remains green without relying on the bypass path for the core regression.

### Task 5: Full verification for this slice

**Files:**
- No intentional new files beyond code/tests for this slice

**Step 1: Run repo verification commands**

Run:
- `uv run ruff check src/ tests/`
- `uv run ruff format --check src/ tests/`
- `uv run mypy src/`
- `env OPENROUTER_API_KEY=test-key WAZZUP_API_KEY=fake-wazzup-key WAZZUP_API_URL=http://fake-wazzup-url LOGFIRE_IGNORE_NO_CONFIG=1 uv run pytest tests/ -v --tb=short`
- `env OPENROUTER_API_KEY=test-key WAZZUP_API_KEY=fake-wazzup-key WAZZUP_API_URL=http://fake-wazzup-url LOGFIRE_IGNORE_NO_CONFIG=1 scripts/orchestration/run_process_verification.sh`

**Step 2: Update stage truth**

- Record what was fixed and what remains for the next admin-surface/docs slice.
- Do not close `tj-9a4m` unless the full verification set is green and the remaining findings are either resolved or explicitly split.
