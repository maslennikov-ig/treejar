# Orchestrator Handoff

Updated: 2026-05-09
Current baseline branch: `main`

## Current truth

- Canonical host: `https://noor.starec.ai`; canonical runtime path: `/opt/noor`.
- Treejar Catalog API is the customer-facing catalog source of truth; Zoho remains the exact stock/price and order-execution truth.
- Stages `tj-5dbj`, `tj-6h30`, `tj-7k2m`, `tj-8q1r`, and `tj-9a4m` are tracked under `.codex/stages/`.
- Latest deployed baseline is `main@867b9330ee51427e0f533f919f6f7df9b1c0a53e` (CRM admin + bot behavior rules + API fallback and admin CSP/font hotfixes), delivered by GitHub Actions run `25597247650`; deploy job `75145254122` passed, runtime `.release-sha` and `.release-run-id` match, `/api/v1/health` is OK, Redis is OK, `alembic current` is `2026_05_08_bot_behavior_rules`, `verify_api.py --base-url https://noor.starec.ai` passed `7/0`, anonymous `/dashboard/` is `401`, unknown `/api/*` routes return JSON `404` instead of landing SPA HTML, and authenticated production browser smoke passed for all CRM admin sections with no unexpected console/network/page errors.
- `tj-9a4m` delivered the shared admin auth boundary, protected product sync, SQLAdmin coverage/read-only audit views, admin metrics docs/UI, and the expanded operator dashboard.
- The `main` CI test job now installs `frontend/admin` npm dependencies before `uv run pytest`, because the dashboard regression harness imports `esbuild` from that frontend workspace during Python test execution.
- Earlier delivery closeout and CI/deploy-gating follow-ups are included in the delivered baseline; referrals stayed protected internal-only unless promoted by later client decision.
- Stage `tj-ruue` is delivered from `origin/main@9ef78006a6a6055fa4786f1a856b422cb916dabb` through `main@8101b2d` for OpenRouter cost controls and AI Quality Controls. CI/deploy passed; post-deploy smoke passed (`verify_api.py` 7/0, `/dashboard/` 401, admin AI controls endpoint 401 anonymous, health ok).
- OpenRouter key rotation for E2E was applied on 2026-04-26 without storing the raw secret in repo memory. The current key is available in production `/opt/noor/.env`, GitHub Actions secret `OPENROUTER_API_KEY`, and the ignored local stage-worktree `.env`; production `app` sees fingerprint `b4118c4887cc` length `73`. Post-rotation checks passed: `alembic current` -> `2026_04_21_llm_attempts`, `llm_attempts` table exists with `0` rows, `ai_quality_controls` config is missing so disabled defaults apply, health is ok, and a production OpenRouter fast-model canary returned `OK` with `44` total tokens and cost about `$0.00000256`.
- Fresh 2026-04-26 production WhatsApp/Telegram E2E on `79262810921` produced and closed hardening stage `tj-e2e26`: order-status after approved/rejected quotation, Telegram private-reply persistence, outbound Wazzup audit/idempotency, conversation API auth/exact phone filtering, rejected quotation state, and media/caption audit visibility.
- `tj-e2e26` is delivered on `2dc356e`: CI/deploy passed, smoke passed (`verify_api.py` 7/0, `/api/v1/health` ok, `/dashboard/` 401, `/api/v1/conversations/` 403, Alembic `2026_04_26_outbound_audit`). Narrow production recheck passed for approved `Fr3141` and rejected `Fr3142` order-status copy; `tj-e2e26` pending test conversations count is `0`.
- Stage `tj-prl26` is launch-ready with explicit defer after controlled pre-launch E2E. `tj-prl26.5` fixed/deployed/rechecked SKU masking; full rerun `20260426181300` passed customer chat/product/stock, quotation approve/reject (`Fr3143`/`Fr3144`), Telegram private manager reply, active escalation fallback, outbound audit readback, and pending count (`5` rerun conversations, `0` pending). Stage closeout passed with full local pytest `774 passed, 19 skipped`.
- Stage `tj-final27` is active in `docs/plans/2026-04-27-final-delivery-completion.md` to close the remaining gap between the technical specification, commercial offer, and final client acceptance. Delivered items: `tj-final27.1` catalog/Zoho truth plus strict catalog price fail-closed follow-up, `tj-final27.2` CRM/source attribution completeness, `tj-final27.3` guarded payment reminders with disabled defaults, and `tj-final27.9` acceptance pack/runbook evidence now tracked in repo. Stale review findings against old worktrees are resolved on deployed `main`: `tj-final27.11` sales fallback is deployed, `tj-final27.13` payment-reminder run-level provider reuse is deployed, and `tj-jy5i` commercial-offer/proposal escalation routing is deployed. DeepSeek sandbox task `tj-final27.12` was deleted per user decision.
- Stage `tj-40n0` and Bead `tj-jp06` are delivered on `main`: `/dashboard/` is now the Noor CRM admin workspace, `/admin/` remains the SQLAdmin fallback, admin CRM/knowledge-base/bot-rules APIs are deployed, audit logging and migrations are applied, DB-backed Bot Behavior Rules/Playbooks are injected separately as `[BOT OPERATING RULES]`, applied rule IDs are visible in conversation detail, Stitch design references are tracked under `docs/design/stitch/noor-ai-crm-dashboard/`, and the admin frontend toolchain is Node 22/Vite 8/Tailwind 4.2.4 with clean npm audit. Pre-merge local verification passed ruff, format-check, mypy, frontend regression scripts, frontend lint/build, full pytest (`926 passed, 16 skipped`), process verification, and local browser smoke for anonymous protection, login, all dashboard sections, 3-panel conversations, KB editor, bot rules, reports, audit, and absence of WhatsApp compose/broadcast affordances. Post-deploy hotfix `tj-xw6k` fixed the SPA fallback for unknown API paths; post-deploy hotfix `tj-gdxt` removed blocked external Google Fonts from the admin dashboard; authenticated production browser smoke screenshots and result JSON are under `.tmp/current/playwright/noor-admin-prod-smoke-20260509/`.

## Next recommended

Next stage id: `tj-final27`
Recommended action: continue final acceptance work with `tj-final27.4` through `tj-final27.8` or record explicit client exclusions before formal final acceptance. Do not send new live WhatsApp/media/voice tests until the exact scenario set is approved.

## Starter prompt for next orchestrator

Use $orchestrator-stage / $stage-orchestrator. Read `AGENTS.md`, `.codex/orchestrator.toml`, `.codex/handoff.md`, `docs/plans/2026-04-27-final-delivery-completion.md`, and `.codex/stages/tj-final27/summary.md` first.
Worktree: create a fresh isolated worktree from current `origin/main` for the next task.
Treat `tj-ruue`, `tj-e2e26`, `tj-prl26`, `tj-final27.1-.3`, `tj-final27.9`, `tj-final27.11`, `tj-final27.13`, and `tj-jy5i` as delivered unless new evidence appears. Execute remaining `tj-final27` work as final-acceptance hardening, not as a broad rewrite.
Do not deploy, mutate production config, run broad production suites, run `scripts/verify_wazzup.py`, enable scheduled AI Quality Controls, or send unsolicited WhatsApp/media/voice tests without explicit approval.

## Explicit defers
- Extended referrals admin/reporting remains intentionally deferred.
- `salePrice` remains raw-only until a separate approved sale policy exists; missing/invalid catalog `price` now fails closed with manager escalation instead of using Zoho rate as customer-facing fallback.
- DeepSeek V4 Pro is intentionally not being pursued as a production model switch after A/B; the sandbox Bead was deleted.
- Final acceptance still needs client decisions for UTM/source outbound Zoho field mapping, payment reminder templates/policy before enabling sends, referral rules or written exclusion, voice/media E2E permission, and final live E2E scenario approval.
