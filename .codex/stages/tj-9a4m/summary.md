# Stage Summary

Stage ID: `tj-9a4m`
Status: `closed`
Updated: 2026-04-15
Baseline: `main@64fd98c2a7b2a5ff7abbfc761b1713654610e4a5`
Implementation worktree: `/Users/igor/code/treejar-tj-9a4m` (child worktree removed after merge)
Implementation branch: `codex/tj-9a4m-audit-admin`

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
- Updated the GitHub Actions `test` job to install `frontend/admin` npm dependencies before `pytest`, so the dashboard regression harness can import `esbuild` in CI as well as locally.

## Fresh verification

- `uv run ruff check src/ tests/`
- `uv run ruff format --check src/ tests/`
- `uv run mypy src/`
- `npm run lint`
- `npm run build`
- `env DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib uv run pytest tests/ -v --tb=short` -> `633 passed, 19 skipped`
- `scripts/orchestration/run_process_verification.sh`

## Delivery state

- Integrated into `main`, with the product slice merged via `84f016614750ad0d3dd52c8cdbe4733c3c4d88e0` and the final closeout/CI-delivery baseline recorded at `main@fa47ec01424af79fe02ca8685e0b3d7573f4c561`.
- GitHub Actions run `24411947429` completed successfully on `main@fa47ec01424af79fe02ca8685e0b3d7573f4c561`, including the `deploy` job to `https://noor.starec.ai`.
- Live smoke verification passed after delivery: `/api/v1/health` returned `200`, `uv run python scripts/verify_api.py --base-url https://noor.starec.ai` passed `7/0`, and anonymous `/dashboard/` plus `/api/v1/admin/dashboard/metrics/` now fail closed with `401`.
- Stage worktree `/Users/igor/code/treejar-tj-9a4m` and branch `codex/tj-9a4m-audit-admin` were removed during closeout.

## Explicit defer

- Keep referrals as internal-only unless the optional extended admin/reporting requirement is explicitly promoted into scope.
