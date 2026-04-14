# Stage Summary

Stage ID: `tj-9a4m`
Status: `in_progress`
Updated: 2026-04-14
Baseline: `main@64fd98c2a7b2a5ff7abbfc761b1713654610e4a5`
Implementation worktree: `/Users/igor/code/treejar-tj-9a4m/.worktrees/tj-9a4m-auth-align`
Implementation branch: `codex/tj-9a4m-auth-align`

## Implemented in this slice

- Unified the admin auth boundary so the root FastAPI app owns the session middleware and `/admin/`, `/dashboard/`, and `/api/v1/admin/*` all use the same admin session.
- Locked down the dashboard shell itself: anonymous `GET /dashboard/` now fails closed instead of serving the SPA without data access.
- Protected `POST /api/v1/products/sync` behind `require_admin_session`.
- Replaced the old admin test bypass with a real `/admin/login` flow in `tests/conftest.py` and added integration coverage proving one login reaches `/admin/`, `/dashboard/`, and `/api/v1/admin/dashboard/metrics/`.
- Added SQLAdmin coverage for `ConversationSummary` and `ManagerReview`.
- Made generated or audit-heavy SQLAdmin views explicit read-only surfaces with `can_create/can_edit/can_delete = False`, while keeping configuration-oriented surfaces writable.
- Aligned the admin dashboard frontend and docs with the backend metrics payload by adding manager/feedback KPI types and UI, refreshing `docs/metrics.md`, and updating `docs/admin-guide.md`.
- Added shared-session operator endpoints under `/api/v1/admin/*` for notification config/test, protected product sync, weekly report generation, recent manager reviews, pending manager-review queue, and manual manager-review evaluation.
- Expanded `/dashboard` into an operator center with actionable panels for catalog sync, Telegram health checks, weekly operations report preview, and manager-review queue/recent reviews.
- Documented the policy split that referrals remain protected internal-only for now because the extended referral admin/reporting surface is optional in `docs/tz.md`.

## Fresh verification

- `uv run ruff check src/ tests/`
- `uv run ruff format --check src/ tests/`
- `uv run mypy src/`
- `npm run lint`
- `npm run build`
- `env DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib OPENROUTER_API_KEY=test-key WAZZUP_API_KEY=fake-wazzup-key WAZZUP_API_URL=http://fake-wazzup-url LOGFIRE_IGNORE_NO_CONFIG=1 uv run pytest tests/ -v --tb=short` -> `629 passed, 19 skipped`
- `scripts/orchestration/run_process_verification.sh`

## Remaining scope before close

- Run a final findings-first review on `codex/tj-9a4m-auth-align`.
- Merge only with explicit authorization.
- Keep referrals as internal-only unless the optional extended admin/reporting requirement is explicitly promoted into scope.
