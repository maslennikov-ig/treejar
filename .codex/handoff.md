# Orchestrator Handoff

Updated: 2026-04-26
Current baseline branch: `main`

## Current truth

- Canonical host: `https://noor.starec.ai`; canonical runtime path: `/opt/noor`.
- Treejar Catalog API is the customer-facing catalog source of truth; Zoho remains the exact stock/price and order-execution truth.
- Stages `tj-5dbj`, `tj-6h30`, `tj-7k2m`, `tj-8q1r`, and `tj-9a4m` are tracked under `.codex/stages/`.
- Latest deployed baseline is `main@d93b95480ec4ca53459f3a0bd527b1a27eb73358` (`fix(llm): preserve labeled SKUs during PII masking`), delivered by GitHub Actions run `24963241165`.
- `tj-9a4m` unified the admin auth boundary so `/admin/`, `/dashboard/`, and `/api/v1/admin/*` share the same root-app session middleware, and the dashboard shell itself now fails closed without admin login.
- `tj-9a4m` protected `POST /api/v1/products/sync`, replaced the old admin auth test bypass with a real `/admin/login` flow, added SQLAdmin coverage for `ConversationSummary` and `ManagerReview`, and made generated/audit-heavy SQLAdmin views explicitly read-only.
- `tj-9a4m` aligned backend/frontend/docs for admin metrics: manager and feedback KPI fields are now rendered in the dashboard UI, typed in TypeScript, and documented in `docs/metrics.md`.
- `tj-9a4m` expanded `/dashboard` into an operator center behind the shared admin session with catalog sync, Telegram config/test, weekly report generation, pending manager-review evaluation, and recent manager-review history.
- The `main` CI test job now installs `frontend/admin` npm dependencies before `uv run pytest`, because the dashboard regression harness imports `esbuild` from that frontend workspace during Python test execution.
- Referrals intentionally remain protected internal-only; the extended referral admin/reporting surface is still optional in `docs/tz.md` and was not promoted into required scope during `tj-9a4m`.
- Delivery closeout on 2026-04-14 finished end-to-end: `main` was pushed, GitHub Actions run `24411947429` completed `success` including `deploy`, `uv run python scripts/verify_api.py --base-url https://noor.starec.ai` passed `7/0`, anonymous `GET /dashboard/` returned `401`, and `scripts/orchestration/cleanup_stage_workspace.py --stage tj-9a4m` removed the stage worktree/branch leftovers.
- Prior local follow-ups for CI path/deploy gating, closeout-truth cleanup in `.codex/*`, and OperatorCenter review-refresh hardening are included in the delivered baseline.
- Stage `tj-ruue` is delivered from `origin/main@9ef78006a6a6055fa4786f1a856b422cb916dabb` through `main@8101b2d` for OpenRouter cost controls and AI Quality Controls. CI/deploy passed; post-deploy smoke passed (`verify_api.py` 7/0, `/dashboard/` 401, admin AI controls endpoint 401 anonymous, health ok).
- OpenRouter key rotation for E2E was applied on 2026-04-26 without storing the raw secret in repo memory. The current key is available in production `/opt/noor/.env`, GitHub Actions secret `OPENROUTER_API_KEY`, and the ignored local stage-worktree `.env`; production `app` sees fingerprint `b4118c4887cc` length `73`. Post-rotation checks passed: `alembic current` -> `2026_04_21_llm_attempts`, `llm_attempts` table exists with `0` rows, `ai_quality_controls` config is missing so disabled defaults apply, health is ok, and a production OpenRouter fast-model canary returned `OK` with `44` total tokens and cost about `$0.00000256`.
- Fresh 2026-04-26 production WhatsApp/Telegram E2E on `79262810921` produced and closed hardening stage `tj-e2e26`: order-status after approved/rejected quotation, Telegram private-reply persistence, outbound Wazzup audit/idempotency, conversation API auth/exact phone filtering, rejected quotation state, and media/caption audit visibility.
- `tj-e2e26` is delivered on `2dc356e`: CI/deploy passed, smoke passed (`verify_api.py` 7/0, `/api/v1/health` ok, `/dashboard/` 401, `/api/v1/conversations/` 403, Alembic `2026_04_26_outbound_audit`). Narrow production recheck passed for approved `Fr3141` and rejected `Fr3142` order-status copy; `tj-e2e26` pending test conversations count is `0`.
- Active stage `tj-prl26`: checklist/prompt and read-only checks are done; controlled E2E found blocker `tj-prl26.5`, then deployed/rechecked the fix. Narrow production recheck conversation `8ad66895-1caa-45df-9f03-8907cc96f21f` for SKU `00-07024023` returned stock `12` and price `685.00 AED`; pending recheck conversations count is `0`.

## Next recommended

Next stage id: `tj-prl26`
Recommended action: rerun `tj-prl26.2` from the remaining controlled acceptance branches, then close readiness with `tj-prl26.4`.

## Starter prompt for next orchestrator

Use $stage-orchestrator / $orchestrator-stage. Read `AGENTS.md`, `.codex/orchestrator.toml`, `.codex/handoff.md`, `docs/plans/2026-04-26-prelaunch-readiness.md`, and `.codex/stages/tj-prl26/summary.md` first.
Worktree: `/home/me/code/treejar/.worktrees/codex-tj-prl26-prelaunch-readiness`; branch: `codex/tj-prl26-prelaunch-readiness`; latest deployed runtime SHA: `d93b95480ec4ca53459f3a0bd527b1a27eb73358`.
Treat `tj-ruue` and `tj-e2e26` as delivered. Keep `tj-prl26` evidence-first; product bugs become separate Beads.
Do not run broad production suites, `verify_wazzup.py`, scheduled AI Quality Controls, or unsolicited media tests without explicit approval.

## Explicit defers
- Extended referrals admin/reporting remains intentionally deferred; some worktrees hit a local pytest capture tmpfile `FileNotFoundError` before collection with plain `uv run pytest ...`, while equivalent full runs with `-s` have passed.
- `tj-prl26.2` stopped after one live synthetic SKU blocker; `tj-prl26.5` is now deployed/rechecked, but quotation/manager/escalation branches remain unaccepted until the controlled E2E rerun.
