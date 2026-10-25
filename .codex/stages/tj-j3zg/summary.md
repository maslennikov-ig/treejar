# Stage tj-j3zg — Redirect unauthenticated `/dashboard` navigation to `/admin/login`

- Branch `codex/tj-j3zg-dashboard-auth`, worktree `.worktrees/tj-j3zg-dashboard-auth`,
  base `main` `8ae7ce8` (owner-authorized push, merge to `main`, and production deploy `2026-10-25`).
- Pinned RAG files (`src/models/product.py`, `src/rag/embeddings.py`,
  `src/rag/pipeline.py`, `src/schemas/product.py`) unchanged vs `main`.

## Delivered
- **Safe Admin Login Redirect & Deep-Link Preservation (`src/api/admin/auth.py`, `src/api/admin/dashboard_redirect_admin.py`, `src/main.py`)**:
  - Replaced the raw `401 {"detail": "Admin authentication required"}` JSON error on `/dashboard/{full_path:path}` with `302` redirect to `/admin/login` (matching `/admin/` behavior), while keeping `/api/v1/admin/*` and `/api/v1/products/sync` strictly `401` JSON.
  - Added `/dashboard` and `/admin` root routes (without trailing slash) so they redirect cleanly instead of falling through to the landing-page SPA.
  - Added `sanitize_admin_next_path`, `remember_admin_login_next`, and `pop_admin_login_next` to preserve deep-linked dashboard destinations (e.g., `/dashboard/?tour=1`, `/dashboard/?view=guide`) across both password login (`POST /admin/login`) and Telegram one-time link login (`GET /dashboard/telegram-login?token=...`), while rejecting external, protocol-relative, control-char, or loop URLs.
  - Updated `/dashboard/telegram-login` so expired/invalid links redirect `303` to `/admin/login?reason=expired_link` with a friendly Russian banner in `templates/sqladmin/login.html` instead of raw JSON `401`/`422`, and repeat clicks when an admin session is already active redirect cleanly to `/dashboard/`.
- **Frontend Expired-Session Redirect (`frontend/admin/src/api/sessionGuard.ts`, `crm.ts`, `metrics.ts`, `operators.ts`)**:
  - Added deduplicated `redirectOnAdminUnauthorized` so an expired admin session inside an already-open `/dashboard/` tab redirects to `/admin/login?next=...&reason=session_expired` without affecting public `/client-self-test` routes.
- **Verification Script & Regression Tests**:
  - Updated `scripts/verify_api.py` and `tests/test_scripts_verify_api.py` for `302` `/dashboard/` auth guard.
  - Added backend and frontend regression coverage in `tests/test_api_admin.py`, `tests/test_security_extended.py`, `tests/test_telegram_admin_login.py`, and `frontend/admin/tests/session_guard_regression.mjs`.

## Verification
- `npm --prefix frontend/admin run lint`, `npm --prefix frontend/admin test` (15/15), and `npm --prefix frontend/admin run build`: passed.
- `uv run ruff check`, `uv run ruff format --check`, `uv run mypy src/`, and `uv run pytest`: passed.
- Headless Chromium visual verification of unauthenticated `/dashboard/` -> `/admin/login`, expired-link notice banner, and post-login deep-link landing (`/dashboard/?tour=1`): passed.
- `docs-reviewed: updated - added stage summary and updated handoff; re-pinned traceability manifest`.
- `graph-reviewed: no-change-needed - bounded FastAPI auth redirect and SPA API session guard; ordinary code navigation used`.
