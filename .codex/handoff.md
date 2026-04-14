# Orchestrator Handoff

Updated: 2026-04-14
Current baseline branch: `main`

## Current truth

- Canonical host: `https://noor.starec.ai`; canonical runtime path: `/opt/noor`.
- Treejar Catalog API is the customer-facing catalog source of truth; Zoho remains the exact stock/price and order-execution truth.
- Stages `tj-6h30`, `tj-5dbj`, `tj-7k2m`, and `tj-8q1r` are closed under `.codex/stages/`.
- Latest runtime-changing verification baseline is `652e0773d7206c17dcc8df7c4bcf4af4a63e7b46`.
- `tj-7k2m` remains the latest deployed-live verification proof for `main@67be40052087fc1f478e7f60ff44c85b4d6375b9`; `tj-8q1r` remains the latest orchestration-cleanup stage.
- On this macOS host, minimal WeasyPrint/PDF generation can work, but a fresh `uv` environment still needed `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib` for full pytest collection of the PDF tests on 2026-04-14; do not assume host-level PDF verification is portable without that env.
- Stage `tj-9a4m` remains active and is currently implemented in dedicated child worktree `/Users/igor/code/treejar-tj-9a4m/.worktrees/tj-9a4m-auth-align` on branch `codex/tj-9a4m-auth-align`, based on `main@64fd98c2a7b2a5ff7abbfc761b1713654610e4a5`.
- `tj-9a4m` fixed the admin auth split by moving the session boundary to the root FastAPI app: `/admin/`, `/dashboard/`, and `/api/v1/admin/*` now share the same admin session, and the dashboard SPA itself is no longer publicly reachable without login.
- `tj-9a4m` also protected `POST /api/v1/products/sync`, replaced the admin test bypass with a real `/admin/login` flow, added SQLAdmin coverage for `ConversationSummary` and `ManagerReview`, and made generated/audit-heavy SQLAdmin views explicitly read-only.
- The admin dashboard/frontend/docs drift is resolved in the same worktree: frontend types/UI now render manager and feedback KPIs, the dashboard now includes an operator center for catalog sync, Telegram health/test, weekly reports, and manager-review queue/evaluation, `docs/metrics.md` matches the backend payload, and the admin/runtime docs reflect the current 13-model shared-session surface.
- `tj-9a4m` now also closes the main operator-workflow split: product sync, notification test/config, weekly reports, and manual manager-review evaluation are available behind the shared admin session in `/dashboard` and `/api/v1/admin/*`; referrals intentionally remain protected internal-only because the extended referral admin/reporting surface is optional in `docs/tz.md`.
- Fresh verification for the implemented slice passed on 2026-04-14: `uv run ruff check src/ tests/`, `uv run ruff format --check src/ tests/`, `uv run mypy src/`, `npm run lint`, `npm run build`, `env DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib OPENROUTER_API_KEY=test-key WAZZUP_API_KEY=fake-wazzup-key WAZZUP_API_URL=http://fake-wazzup-url LOGFIRE_IGNORE_NO_CONFIG=1 uv run pytest tests/ -v --tb=short` -> `629 passed, 19 skipped`, and `scripts/orchestration/run_process_verification.sh`.

## Next recommended

Next stage id: `tj-9a4m`
Recommended action: run a findings-first final review of `codex/tj-9a4m-auth-align`, then either merge the stage candidate or open a narrowly scoped follow-up only if referral admin/reporting needs to move from optional to required scope.

## Starter prompt for next orchestrator

Use $stage-orchestrator.
Read `AGENTS.md`, `.codex/orchestrator.toml`, `.codex/handoff.md`, and `.codex/stages/tj-9a4m/summary.md` first.
Reuse `/Users/igor/code/treejar-tj-9a4m/.worktrees/tj-9a4m-auth-align` only if it is still isolated and clean; otherwise start from clean `origin/main` and recreate the split.
Treat the following `tj-9a4m` facts as current unless disproved: shared admin session now covers `/admin/`, `/dashboard/`, and `/api/v1/admin/*`; `POST /api/v1/products/sync` now requires that session; admin integration coverage uses a real `/admin/login` flow; SQLAdmin now exposes `ConversationSummary` and `ManagerReview` with explicit read-only policies for generated/audit-heavy views; frontend manager/feedback KPI rendering is implemented; and `/dashboard` now exposes operator controls for product sync, Telegram test/config, weekly report generation, and manager-review queue/evaluation.
Referrals remain intentionally protected internal-only unless product requirements promote the optional extended referral admin/reporting surface into active scope.
Keep runtime/deploy work isolated from product logic and do not reopen already verified quotation or Telegram hypotheses without new evidence.

## Explicit defers

- Dirty root worktree state from `/Users/igor/code/treejar` must stay isolated and must not be merged into `main` without fresh review.
- Merge/deploy are still pending explicit authorization; do not ship `codex/tj-9a4m-auth-align` without a fresh review decision and user approval.
