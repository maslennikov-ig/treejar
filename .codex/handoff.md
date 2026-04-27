# Orchestrator Handoff

Updated: 2026-04-27
Current baseline branch: `main`

## Current truth

- Canonical host: `https://noor.starec.ai`; canonical runtime path: `/opt/noor`.
- Treejar Catalog API is the customer-facing catalog source of truth; Zoho remains the exact stock/price and order-execution truth.
- Stages `tj-5dbj`, `tj-6h30`, `tj-7k2m`, `tj-8q1r`, and `tj-9a4m` are tracked under `.codex/stages/`.
- Latest deployed baseline is `main@d93b95480ec4ca53459f3a0bd527b1a27eb73358` (`fix(llm): preserve labeled SKUs during PII masking`), delivered by GitHub Actions run `24963241165`.
- `tj-9a4m` delivered the shared admin auth boundary, protected product sync, SQLAdmin coverage/read-only audit views, admin metrics docs/UI, and the expanded operator dashboard.
- The `main` CI test job now installs `frontend/admin` npm dependencies before `uv run pytest`, because the dashboard regression harness imports `esbuild` from that frontend workspace during Python test execution.
- Earlier delivery closeout and CI/deploy-gating follow-ups are included in the delivered baseline; referrals stayed protected internal-only unless promoted by later client decision.
- Stage `tj-ruue` is delivered from `origin/main@9ef78006a6a6055fa4786f1a856b422cb916dabb` through `main@8101b2d` for OpenRouter cost controls and AI Quality Controls. CI/deploy passed; post-deploy smoke passed (`verify_api.py` 7/0, `/dashboard/` 401, admin AI controls endpoint 401 anonymous, health ok).
- OpenRouter key rotation for E2E was applied on 2026-04-26 without storing the raw secret in repo memory. The current key is available in production `/opt/noor/.env`, GitHub Actions secret `OPENROUTER_API_KEY`, and the ignored local stage-worktree `.env`; production `app` sees fingerprint `b4118c4887cc` length `73`. Post-rotation checks passed: `alembic current` -> `2026_04_21_llm_attempts`, `llm_attempts` table exists with `0` rows, `ai_quality_controls` config is missing so disabled defaults apply, health is ok, and a production OpenRouter fast-model canary returned `OK` with `44` total tokens and cost about `$0.00000256`.
- Fresh 2026-04-26 production WhatsApp/Telegram E2E on `79262810921` produced and closed hardening stage `tj-e2e26`: order-status after approved/rejected quotation, Telegram private-reply persistence, outbound Wazzup audit/idempotency, conversation API auth/exact phone filtering, rejected quotation state, and media/caption audit visibility.
- `tj-e2e26` is delivered on `2dc356e`: CI/deploy passed, smoke passed (`verify_api.py` 7/0, `/api/v1/health` ok, `/dashboard/` 401, `/api/v1/conversations/` 403, Alembic `2026_04_26_outbound_audit`). Narrow production recheck passed for approved `Fr3141` and rejected `Fr3142` order-status copy; `tj-e2e26` pending test conversations count is `0`.
- Stage `tj-prl26` is launch-ready with explicit defer after controlled pre-launch E2E. `tj-prl26.5` fixed/deployed/rechecked SKU masking; full rerun `20260426181300` passed customer chat/product/stock, quotation approve/reject (`Fr3143`/`Fr3144`), Telegram private manager reply, active escalation fallback, outbound audit readback, and pending count (`5` rerun conversations, `0` pending). Stage closeout passed with full local pytest `774 passed, 19 skipped`.
- Stage `tj-final27` is planned in `docs/plans/2026-04-27-final-delivery-completion.md` to close the remaining gap between the technical specification, commercial offer, and final client acceptance. This planning pass created Beads for commercial catalog/Zoho truth, CRM completeness, payment reminders, voice/audio, post-delivery feedback, referrals, QA/reporting, nonfunctional readiness, and final controlled E2E.

## Next recommended

Next stage id: `tj-final27`
Recommended action: execute `tj-final27.1` first, because commercial catalog/Zoho truth reconciliation is the highest-risk remaining client-facing gap. Keep client-dependent policy work as explicit blocked/decision items instead of guessing business rules.

## Starter prompt for next orchestrator

Use $stage-orchestrator / $orchestrator-stage. Read `AGENTS.md`, `.codex/orchestrator.toml`, `.codex/handoff.md`, `docs/plans/2026-04-27-final-delivery-completion.md`, and `.codex/stages/tj-final27/summary.md` first.
Worktree: `/home/me/code/treejar/.worktrees/codex-tj-prl26-prelaunch-readiness`; branch: `codex/tj-final27-final-delivery-plan`; latest deployed runtime SHA remains `d93b95480ec4ca53459f3a0bd527b1a27eb73358` unless newer deployment evidence is recorded.
Treat `tj-ruue`, `tj-e2e26`, and `tj-prl26` as delivered/launch-ready unless new evidence appears. Execute `tj-final27` as final-acceptance hardening, not as a broad rewrite.
Do not deploy, mutate production config, run broad production suites, run `scripts/verify_wazzup.py`, enable scheduled AI Quality Controls, or send unsolicited media/voice tests without explicit approval.

## Explicit defers
- Extended referrals admin/reporting remains intentionally deferred; some worktrees hit a local pytest capture tmpfile `FileNotFoundError` before collection with plain `uv run pytest ...`, while equivalent full runs with `-s` have passed.
- Product price source difference remains visible: catalog discovery can show catalog price `264 AED` for SKU `00-07024023`, while exact stock/price returns Zoho rate `685.00 AED`. Current source-of-truth rule says Zoho is exact stock/price truth, so this is not a launch blocker, but it is a commercial-content risk to watch or reconcile.
- Final acceptance still needs client decisions for price wording, UTM/source mapping, payment reminder policy, referral rules, and live E2E permissions.
