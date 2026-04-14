# Orchestrator Handoff

Updated: 2026-04-14
Current baseline branch: `main`

## Current truth

- Canonical host: `https://noor.starec.ai`; canonical runtime path: `/opt/noor`.
- Treejar Catalog API is the customer-facing catalog source of truth; Zoho remains the exact stock/price and order-execution truth.
- Stages `tj-5dbj`, `tj-6h30`, `tj-7k2m`, `tj-8q1r`, and `tj-9a4m` are tracked under `.codex/stages/`.
- Latest runtime-changing verified baseline is local `main@84f016614750ad0d3dd52c8cdbe4733c3c4d88e0` (`feat(admin): align auth and operator workflows`).
- `tj-9a4m` unified the admin auth boundary so `/admin/`, `/dashboard/`, and `/api/v1/admin/*` share the same root-app session middleware, and the dashboard shell itself now fails closed without admin login.
- `tj-9a4m` protected `POST /api/v1/products/sync`, replaced the old admin auth test bypass with a real `/admin/login` flow, added SQLAdmin coverage for `ConversationSummary` and `ManagerReview`, and made generated/audit-heavy SQLAdmin views explicitly read-only.
- `tj-9a4m` aligned backend/frontend/docs for admin metrics: manager and feedback KPI fields are now rendered in the dashboard UI, typed in TypeScript, and documented in `docs/metrics.md`.
- `tj-9a4m` expanded `/dashboard` into an operator center behind the shared admin session with catalog sync, Telegram config/test, weekly report generation, pending manager-review evaluation, and recent manager-review history.
- The `main` CI test job now installs `frontend/admin` npm dependencies before `uv run pytest`, because the dashboard regression harness imports `esbuild` from that frontend workspace during Python test execution.
- Referrals intentionally remain protected internal-only; the extended referral admin/reporting surface is still optional in `docs/tz.md` and was not promoted into required scope during `tj-9a4m`.
- Fresh local verification on 2026-04-14 passed for the merged `main` candidate: `uv run ruff check src/ tests/`, `uv run ruff format --check src/ tests/`, `uv run mypy src/`, `npm run lint`, `npm run build`, `env DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib OPENROUTER_API_KEY=test-key WAZZUP_API_KEY=fake-wazzup-key WAZZUP_API_URL=http://fake-wazzup-url LOGFIRE_IGNORE_NO_CONFIG=1 uv run pytest tests/ -v --tb=short` -> `631 passed, 19 skipped`, and `scripts/orchestration/run_process_verification.sh`.

## Next recommended

Next stage id: `tbd`
Recommended action: push `main` through the canonical deploy workflow for `84f016614750ad0d3dd52c8cdbe4733c3c4d88e0`, then only open a new isolated stage if live verification finds drift or if the optional referrals/admin-reporting scope is explicitly promoted.

## Starter prompt for next orchestrator

Use $stage-orchestrator.
Read `AGENTS.md`, `.codex/orchestrator.toml`, `.codex/handoff.md`, and `.codex/stages/tj-9a4m/summary.md` first.
Start from clean `origin/main`.
Treat `84f016614750ad0d3dd52c8cdbe4733c3c4d88e0` as the latest local admin/runtime baseline that unifies admin auth, protects product sync, exposes operator actions in `/dashboard`, and aligns admin metrics/docs.
Do not reopen old quotation or Telegram hypotheses without fresh live/runtime evidence.
Keep runtime/deploy work isolated from product logic.

## Explicit defers

- Extended referrals admin/reporting remains intentionally deferred because `docs/tz.md` still treats that surface as optional and `tj-9a4m` did not uncover new evidence that promotes it into required scope.
