# Orchestrator Handoff

Updated: 2026-04-15
Current baseline branch: `main`

## Current truth

- Canonical host: `https://noor.starec.ai`; canonical runtime path: `/opt/noor`.
- Treejar Catalog API is the customer-facing catalog source of truth; Zoho remains the exact stock/price and order-execution truth.
- Stages `tj-5dbj`, `tj-6h30`, `tj-7k2m`, `tj-8q1r`, and `tj-9a4m` are tracked under `.codex/stages/`.
- Latest deployed baseline is `main@fa47ec01424af79fe02ca8685e0b3d7573f4c561` (`fix(ci): install admin frontend deps for pytest`); the latest runtime-changing product slice within that baseline remains `84f016614750ad0d3dd52c8cdbe4733c3c4d88e0` (`feat(admin): align auth and operator workflows`).
- `tj-9a4m` unified the admin auth boundary so `/admin/`, `/dashboard/`, and `/api/v1/admin/*` share the same root-app session middleware, and the dashboard shell itself now fails closed without admin login.
- `tj-9a4m` protected `POST /api/v1/products/sync`, replaced the old admin auth test bypass with a real `/admin/login` flow, added SQLAdmin coverage for `ConversationSummary` and `ManagerReview`, and made generated/audit-heavy SQLAdmin views explicitly read-only.
- `tj-9a4m` aligned backend/frontend/docs for admin metrics: manager and feedback KPI fields are now rendered in the dashboard UI, typed in TypeScript, and documented in `docs/metrics.md`.
- `tj-9a4m` expanded `/dashboard` into an operator center behind the shared admin session with catalog sync, Telegram config/test, weekly report generation, pending manager-review evaluation, and recent manager-review history.
- The `main` CI test job now installs `frontend/admin` npm dependencies before `uv run pytest`, because the dashboard regression harness imports `esbuild` from that frontend workspace during Python test execution.
- Referrals intentionally remain protected internal-only; the extended referral admin/reporting surface is still optional in `docs/tz.md` and was not promoted into required scope during `tj-9a4m`.
- Fresh local verification on 2026-04-15 passed for the merged `main` candidate: `uv run ruff check src/ tests/`, `uv run ruff format --check src/ tests/`, `uv run mypy src/`, `env DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib uv run pytest tests/ -v --tb=short` -> `633 passed, 19 skipped`, and `scripts/orchestration/run_process_verification.sh`.
- Delivery closeout on 2026-04-14 finished end-to-end: `main` was pushed, GitHub Actions run `24411947429` completed `success` including `deploy`, `uv run python scripts/verify_api.py --base-url https://noor.starec.ai` passed `7/0`, anonymous `GET /dashboard/` returned `401`, and `scripts/orchestration/cleanup_stage_workspace.py --stage tj-9a4m` removed the stage worktree/branch leftovers.
- Local `main` currently has unpushed follow-up changes that are not yet part of the deployed baseline: CI workflow path/deploy gating for docs/orchestration-only changes, closeout-truth cleanup in `.codex/*`, and OperatorCenter hardening so a saved manager review degrades to an informational refresh warning instead of a false failure state.

## Next recommended

Next stage id: `tbd`
Recommended action: either push the current local `main` follow-up commit to deliver the pending CI/closeout/OperatorCenter hardening, or explicitly defer/discard that local delta before opening any new stage. After that, leave the queue idle unless fresh live/runtime evidence appears or the optional referrals/admin-reporting scope is explicitly promoted.

## Starter prompt for next orchestrator

Use $stage-orchestrator.
Read `AGENTS.md`, `.codex/orchestrator.toml`, `.codex/handoff.md`, and `.codex/stages/tj-9a4m/summary.md` first.
Start from clean `origin/main`.
Treat `fa47ec01424af79fe02ca8685e0b3d7573f4c561` as the latest deployed baseline. Before starting a new stage from `origin/main`, check whether the local `main` follow-up commit with CI path gating, closeout-truth cleanup, and OperatorCenter review-refresh hardening still needs to be pushed or intentionally deferred.
Do not reopen old quotation or Telegram hypotheses without fresh live/runtime evidence.
Keep runtime/deploy work isolated from product logic.

## Explicit defers

- Extended referrals admin/reporting remains intentionally deferred because `docs/tz.md` still treats that surface as optional and `tj-9a4m` did not uncover new evidence that promotes it into required scope.
