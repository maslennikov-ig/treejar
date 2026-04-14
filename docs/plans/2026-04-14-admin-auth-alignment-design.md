# Admin Auth Alignment Design

Date: 2026-04-14
Stage: `tj-9a4m`
Branch: `codex/tj-9a4m-auth-align`

## Problem

The admin surface is split across two authentication boundaries:

- `/admin/*` runs inside the mounted SQLAdmin Starlette app, which gets `SessionMiddleware` from `sqladmin.AuthenticationBackend`.
- `/dashboard/*` and `/api/v1/admin/*` run on the root FastAPI app, which currently has no session middleware.

This produces a broken operator flow: SQLAdmin login succeeds and issues a cookie, but the dashboard API still returns `401`.

The same slice also contains a separate security gap: `POST /api/v1/products/sync` is exposed without admin auth or `require_api_key`, even though it is an operator action that enqueues background sync jobs.

## Scope

This design intentionally covers only the first fix slice:

1. Align admin session auth across `/admin`, `/dashboard`, and `/api/v1/admin/*`.
2. Protect manual product sync behind the admin session boundary.
3. Replace auth-bypassed admin integration coverage with a real login-flow test.

It does not yet redesign the broader SQLAdmin surface, add missing model views, or align dashboard KPI rendering/docs.

## Approaches Considered

### Option A: Root-level session middleware and shared admin-session dependency

Add `SessionMiddleware` to the root FastAPI app and stop relying on SQLAdmin's private mounted-only middleware for cross-surface auth. Keep SQLAdmin login as the canonical credential check, but make the issued session visible to `/dashboard/*` and `/api/v1/admin/*`.

Pros:
- One operator login flow.
- Minimal architectural change.
- Matches the existing dashboard frontend, which already uses `/api/v1/admin/*`.

Cons:
- Requires care to avoid double session middleware on `/admin`.
- The root app will now parse the session cookie on every request.

### Option B: Separate dashboard token/auth mechanism

Keep SQLAdmin session scoped to `/admin`, and introduce a second auth path for dashboard/API routes.

Pros:
- Avoids touching root middleware.

Cons:
- Adds a second operator auth model with no current product need.
- Requires frontend login/logout work.
- Keeps the admin surface conceptually split.

### Option C: Move dashboard under the mounted `/admin` sub-app

Serve the SPA and dashboard API from inside the SQLAdmin mount so they inherit its existing session stack.

Pros:
- Keeps auth local to one sub-app.

Cons:
- More invasive route/layout refactor.
- Couples custom dashboard serving to SQLAdmin's app structure.
- Harder to reason about than fixing the root app boundary directly.

## Decision

Choose Option A.

The product already behaves as though there is one admin area. The cleanest correction is to make that true in code: one admin session cookie, one dependency for protected admin routes, one operator login flow.

## Proposed Design

### Auth boundary

- Add root-level `SessionMiddleware` to the main FastAPI app.
- Change SQLAdmin auth setup so it no longer relies on its own private session middleware for correctness across app boundaries.
- Keep `AdminAuth` as the canonical place for credential validation and session-token semantics.
- Reuse the same `require_admin_session` guard for:
  - `/api/v1/admin/*`
  - `/dashboard/*`
  - operator actions that should be session-protected

### Dashboard protection

- Require an authenticated admin session before serving the dashboard SPA entrypoint and client-side routes.
- Preserve static asset serving for already-authenticated users.
- Keep the frontend API base unchanged (`/api/v1/admin`).

### Manual product sync protection

- Protect `POST /api/v1/products/sync` with admin session auth.
- Leave read/search product routes unchanged.
- This keeps manual sync as an operator action while preserving public/catalog-facing product reads.

### Tests

- Add a real login integration test that proves:
  1. anonymous `/dashboard/` is rejected or redirected into the intended admin flow,
  2. anonymous `/api/v1/admin/dashboard/metrics/` is rejected,
  3. `POST /admin/login` succeeds,
  4. the same logged-in client can access both `/admin/` and the intended protected dashboard/API routes.
- Stop using the auth-bypassed `admin_client` fixture for tests that claim to verify admin integration.
- Keep unit tests for `AdminAuth`, but make real-flow integration the regression guard.

## Risks

- SQLAdmin may still append its own middleware if left unchanged, so the implementation must avoid ending up with two unrelated session stacks for `/admin`.
- Protecting `/dashboard/assets` too aggressively could break the SPA shell; route-level behavior needs to keep asset delivery working for logged-in sessions.
- Existing tests that assumed open `/dashboard/` or open `/products/sync` will need deliberate updates rather than silent behavior drift.
