# Orchestrator Handoff

Updated: 2026-04-26
Current baseline branch: `main`

## Current truth

- Canonical host: `https://noor.starec.ai`; canonical runtime path: `/opt/noor`.
- Treejar Catalog API is the customer-facing catalog source of truth; Zoho remains the exact stock/price and order-execution truth.
- Stages `tj-5dbj`, `tj-6h30`, `tj-7k2m`, `tj-8q1r`, and `tj-9a4m` are tracked under `.codex/stages/`.
- Latest deployed baseline is `main@8101b2dfbc736d32e660538959c1e7f4d1bfbf6b` (`docs(orchestration): close tj-ruue stage locally`), delivered by GitHub Actions run `24876930080`.
- `tj-9a4m` unified the admin auth boundary so `/admin/`, `/dashboard/`, and `/api/v1/admin/*` share the same root-app session middleware, and the dashboard shell itself now fails closed without admin login.
- `tj-9a4m` protected `POST /api/v1/products/sync`, replaced the old admin auth test bypass with a real `/admin/login` flow, added SQLAdmin coverage for `ConversationSummary` and `ManagerReview`, and made generated/audit-heavy SQLAdmin views explicitly read-only.
- `tj-9a4m` aligned backend/frontend/docs for admin metrics: manager and feedback KPI fields are now rendered in the dashboard UI, typed in TypeScript, and documented in `docs/metrics.md`.
- `tj-9a4m` expanded `/dashboard` into an operator center behind the shared admin session with catalog sync, Telegram config/test, weekly report generation, pending manager-review evaluation, and recent manager-review history.
- The `main` CI test job now installs `frontend/admin` npm dependencies before `uv run pytest`, because the dashboard regression harness imports `esbuild` from that frontend workspace during Python test execution.
- Referrals intentionally remain protected internal-only; the extended referral admin/reporting surface is still optional in `docs/tz.md` and was not promoted into required scope during `tj-9a4m`.
- Delivery closeout on 2026-04-14 finished end-to-end: `main` was pushed, GitHub Actions run `24411947429` completed `success` including `deploy`, `uv run python scripts/verify_api.py --base-url https://noor.starec.ai` passed `7/0`, anonymous `GET /dashboard/` returned `401`, and `scripts/orchestration/cleanup_stage_workspace.py --stage tj-9a4m` removed the stage worktree/branch leftovers.
- Local `main` currently has unpushed follow-up changes that are not yet part of the deployed baseline: CI workflow path/deploy gating for docs/orchestration-only changes, closeout-truth cleanup in `.codex/*`, and OperatorCenter hardening so a saved manager review degrades to an informational refresh warning instead of a false failure state.
- Stage `tj-ruue` is delivered from `origin/main@9ef78006a6a6055fa4786f1a856b422cb916dabb` through `main@8101b2d` for OpenRouter cost controls and AI Quality Controls. CI/deploy passed; post-deploy smoke passed (`verify_api.py` 7/0, `/dashboard/` 401, admin AI controls endpoint 401 anonymous, health ok).
- OpenRouter key rotation for E2E was applied on 2026-04-26 without storing the raw secret in repo memory. The current key is available in production `/opt/noor/.env`, GitHub Actions secret `OPENROUTER_API_KEY`, and the ignored local stage-worktree `.env`; production `app` sees fingerprint `b4118c4887cc` length `73`. Post-rotation checks passed: `alembic current` -> `2026_04_21_llm_attempts`, `llm_attempts` table exists with `0` rows, `ai_quality_controls` config is missing so disabled defaults apply, health is ok, and a production OpenRouter fast-model canary returned `OK` with `44` total tokens and cost about `$0.00000256`.
- Fresh 2026-04-26 production WhatsApp/Telegram E2E on `79262810921` passed core flows but produced follow-up hardening stage `tj-e2e26`: order-status after approved quotation, Telegram private-reply persistence, outbound Wazzup audit/idempotency, conversation API auth/exact phone filtering, rejected quotation state, and media/caption audit visibility.
- `tj-e2e26` implementation tasks `tj-e2e26.1` through `tj-e2e26.6` are integrated locally on `codex/live-triage-20260417` and closed in Beads. Local verification passed: 146 targeted tests, full local pytest `770 passed, 19 skipped`, ruff/format/mypy, artifact validation, single Alembic head `2026_04_26_outbound_audit`, process verification, and `git diff --check`. No deploy/prod mutation was performed.

## Next recommended

Next stage id: `tj-e2e26`
Recommended action: review the integrated `tj-e2e26` diff, decide whether to stage/commit/push, then deploy only with explicit approval. After the new build is live, run Beads `tj-e2e26.7` as a scoped post-fix E2E regression with explicit approval for production WhatsApp/Telegram mutations.

## Starter prompt for next orchestrator

Use $stage-orchestrator / $orchestrator-stage. Read `AGENTS.md`, `.codex/orchestrator.toml`, `.codex/handoff.md`, `.codex/stages/tj-ruue/summary.md`, and `.codex/stages/tj-e2e26/summary.md` first.
Start from the current `tj-ruue` orchestration branch `codex/live-triage-20260417` unless explicitly rebasing the stage.
Treat `fa47ec01424af79fe02ca8685e0b3d7573f4c561` as the latest deployed baseline. Before starting a new stage from `origin/main`, check whether the local `main` follow-up commit with CI path gating, closeout-truth cleanup, and OperatorCenter review-refresh hardening still needs to be pushed or intentionally deferred.
Treat `tj-ruue` as delivered; `tj-e2e26.1` through `tj-e2e26.6` are locally integrated and verified, while `tj-e2e26.7` remains open until deploy/production-regression approval. Keep runtime/deploy work isolated from product logic.
Do not run broad production suites, `verify_wazzup.py`, scheduled AI Quality Controls, or unsolicited media tests without explicit approval.

## Explicit defers
- Extended referrals admin/reporting remains intentionally deferred; some worktrees hit a local pytest capture tmpfile `FileNotFoundError` before collection with plain `uv run pytest ...`, while equivalent full runs with `-s` have passed.
- `tj-e2e26.7` post-fix E2E is intentionally deferred until this exact build is deployed to the intended runtime and production WhatsApp/Telegram mutations are explicitly approved.
