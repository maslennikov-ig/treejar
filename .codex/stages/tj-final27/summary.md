# Stage tj-final27: Final Delivery Completion

Updated: 2026-05-26
Status: active; `.4`-`.8` are merged to `main@000798e` and deployed
Branch: `main`
Source integration branch: deleted after selective port from `origin/codex/tj-final27-acceptance-integration`
Plan: `docs/plans/2026-04-27-final-delivery-completion.md`

## Goal

Bring Treejar/Noor from launch-ready to final client-acceptance readiness by closing the remaining gaps between the technical specification, the commercial offer, and production E2E evidence.

## Scope

- Commercial catalog/Zoho truth reconciliation.
- CRM completeness: UTM/source attribution, deal-state consistency, returning-customer context.
- Payment reminder and follow-up policy.
- Voice/audio production hardening.
- Post-delivery feedback acceptance.
- Referral launch or explicit client exclusion.
- QA/reporting final acceptance.
- Nonfunctional readiness: load, security, backups, SLA.
- Final acceptance pack and controlled E2E.

## Execution Guardrails

- Keep implementation streams isolated by branch/worktree.
- Use Beads as the source of truth.
- Do not deploy, mutate production config, run broad production suites, run `scripts/verify_wazzup.py`, enable scheduled AI Quality Controls, or send unsolicited media/voice tests without explicit approval.
- Use production only for approved controlled E2E; otherwise use local tests, mocked integrations, and read-only checks.

## Current State

`tj-final27.1`, `tj-final27.2`, and `tj-final27.3` have been implemented, reviewed, merged, and delivered through `main@090e318d06662eb4a4c4f2247eb01bd1ed317b94`.

Delivered evidence:

- Catalog price is the customer-facing source of truth; `salePrice` is raw-only, missing/invalid catalog price fails closed, discovery does not show `0.00`, exact quote/order creates manager escalation, and metadata markers are JSON-safe.
- CRM/source attribution keeps original/latest source locally, keeps Zoho outbound custom-field mapping explicit-only, and bounds returning-customer context.
- Payment reminders remain disabled by default; manual/scheduled controls are guarded, deterministic candidate scanning has a hard cap, and locally created Wazzup providers are closed.
- CI/deploy run `25115695746` passed on `main@090e318`; production smoke passed (`verify_api.py` 7/0, health 200).

The `tj-final27.9` final acceptance pack and controlled E2E runbook are now tracked in repo from the 2026-04-29 approved final E2E work. The task remains blocked for formal acceptance until `tj-final27.4` through `tj-final27.8` are closed with evidence or explicitly excluded by client decision.

`tj-final27.11` is deployed on `main@ab897878e2f0ee339bd7626b63d5c6f3a9497042`. It adds compact deterministic sales fallbacks for price objection, retention/drop-off, and known off-catalog requests without expanding the base system prompt. DeepSeek sandbox task `tj-final27.12` was deleted per user decision. Verification passed: targeted RED/GREEN tests, `tests/test_verified_answers.py tests/test_llm_engine.py` (`94 passed` after hotfix), ruff, mypy, artifact validation, process verification, and full pytest with capture disabled (`828 passed`, `19 skipped`). CI/deploy passed in GitHub Actions run `25150153084` with deploy job `73718851402`; production runtime `.release-sha` matches, prod smoke passed (`verify_api.py` 7/0, health 200), and controlled live WhatsApp text E2E on `79262810921` passed for price objection, retention, and off-catalog with `z-ai/glm-5|sales-fallback`, `escalation_status=none`, and `0` pending conversations.

`tj-final27.13` is deployed on `main@354015280c8f8d39b538bbaba769e70d29d1c6b2`. It preserves the existing payment-reminder scan loop and hard-cap warning while reusing one `WazzupProvider` per reminder run after non-empty candidate rows are found. GitHub Actions run `25156910086` and deploy job `73741233988` passed; runtime `.release-sha` matches, health is OK, Redis is OK, and production payment reminder controls still resolve to disabled defaults.

Commercial offer/proposal escalation routing fix `tj-jy5i` is also deployed on `main@1cce2aa4bdbc82b9a11ce2f7ce117103e6a3e6f0`. Controlled text-only E2E on `79262810921` passed for proposal clarification and high-risk payment terms routing, and the synthetic test data was cleaned from production.

On 2026-05-26, the useful `tj-final27.4` through `tj-final27.8` work was selectively ported from stale source branch `origin/codex/tj-final27-acceptance-integration` onto current `main@50a1b52`, merged as `main@000798e`, and deployed by GitHub Actions run `26447020048`. Old handoff/orchestration-script drift from the source branch was intentionally not ported; the stale source branch was deleted after merge.

Ported evidence:

- `tj-final27.4`: voice/audio transcription hardening, bounded non-core transcription policy, usage/cost metadata, deterministic fallback for oversized/unreadable audio, SQLAdmin message visibility, and local voice/audio tests.
- `tj-final27.5`: deterministic post-delivery feedback candidate/dedupe metadata, audited feedback request sends, delivery-context guard, dashboard metrics/API, Operator Center recent feedback readout, and local feedback tests.
- `tj-final27.6`: referral API and LLM tools are policy-gated behind disabled-safe `client_decision_required` defaults; Operator Center exposes referral policy state. Launch remains blocked pending written client referral policy or explicit exclusion.
- `tj-final27.7`: final report fields for refusal, feedback, and LLM cost-control visibility plus QA/reporting runbook and report tests.
- `tj-final27.8`: bounded local/mock load harness, admin/auth guard checks in `verify_api.py`, security/infra tests, tracked-secret evidence, and nonfunctional readiness documentation.

Port verification:

- Voice/audio targeted suite: `50 passed`.
- Feedback/referrals targeted suite: `55 passed`.
- Reports targeted suite: `7 passed`.
- Nonfunctional/security/script targeted suite: `15 passed`.
- Combined targeted suite: `127 passed`.
- Backend static checks: `uv run ruff check src/ tests/ scripts/`, `uv run ruff format --check src/ tests/ scripts/`, and `uv run mypy src/` passed.
- Frontend admin checks: `npm --prefix frontend/admin ci`, `npm --prefix frontend/admin run lint`, and `npm --prefix frontend/admin run build` passed. `npm ci` warned that local Node `v24.15.0` is outside the package engine range `>=22.12.0 <23`.
- Full test suite: `1177 passed, 19 skipped`.
- Process verification: `scripts/orchestration/run_process_verification.sh` passed.
- Merge verification: merge tree `main@000798e` matched the verified port branch tree, and post-merge `scripts/orchestration/run_process_verification.sh` passed.
- CI/deploy: GitHub Actions run `26447020048` passed changes, lint, test, type-check, and deploy.
- Read-only production smoke: `/api/v1/health` OK with Redis OK, products `200`, conversations auth guard `403`, quality auth guard `403`, dashboard auth guard `401`, admin metrics auth guard `401`, webhook empty payload `200`, admin `200`. Public `/.release-sha` returned `404`, so SHA readback was unavailable via that path.
- Stage-scoped artifact normalization: legacy `tj-final27` artifacts were updated to the current orchestration artifact schema on branch `codex/tj-final27-artifact-normalization`; accepted delivered artifacts now carry explicit delivery/cleanup/risk fields, `tj-final27.11.md` uses `status: merged`, and blocked work remains blocked with explicit defers.
- Stage readiness after normalization: `python3 scripts/orchestration/validate_artifact.py .codex/stages/tj-final27/artifacts/*.md` and `scripts/orchestration/check_stage_ready.py tj-final27` passed.

Referral search refresh, 2026-05-26: no client-approved referral mechanics were found in client docs, stage artifacts, handoff notes, or Beads. The durable client-facing materials only define referral scope and request the missing parameters: new-customer discount, referrer bonus, and activation conditions. Internal implementation defaults are not approval. Keep `tj-final27.6` blocked until the client approves rules or explicitly excludes referrals.

E2E posture: final controlled E2E is appropriate to run, but the current runbook requires fresh explicit approval for exact phone/channel/suffix/scenarios before live WhatsApp messages. Referral/feedback/payment-send/voice/media branches need separate approval; until referral rules are approved, referral E2E can only assert disabled-safe/client-decision behavior.

Remaining: explicit client decision for referrals, exact approval for final live E2E scenario scope, and approval for any live voice/media/payment/referral/feedback branch or production nonfunctional drill.

Telegram private admin login and CRM admin production-regression fixes are delivered through `main@3bad8cd` and verified in production. Authenticated CRM admin E2E run `20260511154258` passed guards, Telegram session consume, all dashboard nav sections, conversations 3-panel layout, KB editor/preview/save/reindex/soft-delete, Auto-FAQ approve/reject, bot rules preview/save/reindex/archive, catalog/report/settings/quality/queues read-only smoke, Support, and Audit evidence for `admin_login.telegram` / `telegram:166848328`.

Controlled pre-launch production E2E `tj-s4j9` on approved WhatsApp number `+79262810921` found and closed one launch-blocking defect: RAG search included soft-deleted KB entries, causing one payment-terms response to leak a disposable admin-regression sentinel. Hotfix `main@e6be616ab99943540e24f562f426fa5258fcc4a0` excludes `KnowledgeBase.deleted_at` rows from RAG search and adds a regression test. Local verification passed ruff, format-check, mypy, targeted RAG/payment/verified-answer tests, process verification, and full pytest (`954 passed, 19 skipped`). GitHub Actions run `25689301476` passed lint/test/type-check/deploy, runtime `.release-sha` matches, production smoke passed (`verify_api.py` `7/0`, dashboard guard `401`, bad Telegram token `401`, health `200`), and post-fix live retest passed for net30/discount manager handoff, product discovery, exact SKU `00-07024023`, quotation `Fr3238`, Arabic, and off-catalog handling. Production DB readback showed `14` `tj-s4j9` conversations, `0` non-final escalations, `0` post-fix sentinel mentions, and outbound audit rows for bot replies, manager replies, quotation/media sends.
