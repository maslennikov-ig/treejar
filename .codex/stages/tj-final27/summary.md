# Stage tj-final27: Final Delivery Completion

Updated: 2026-04-30
Status: active; implementation-ready integration pending main review/merge, CI, and client decisions
Branch: `codex/tj-final27-final-delivery-plan`
Integration branch: `codex/tj-final27-acceptance-integration`
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

On 2026-04-30 the remaining final-acceptance streams were executed in isolated branches and merged into integration branch `codex/tj-final27-acceptance-integration` from base `main@10e128fab6958186dcfed079fa2e360129e5d43f`:

- `tj-final27.4` (`codex/tj-final27-4-voice-audio-acceptance`, `35b84c0`) hardens voice/audio transcription with request timeout, zero SDK retries, max-token cap, usage/cost metadata, non-core safety path, deterministic oversized/unreadable fallback, persisted audio/transcription audit fields, and SQLAdmin Message visibility. Live voice E2E remains deferred pending explicit approval.
- `tj-final27.5` (`codex/tj-final27-5-6-feedback-referrals`, `93a0b51`) adds deterministic feedback request candidate selection, dedupe metadata, audited feedback sends, delivery-context guard, dashboard metrics, protected admin API, and Operator Center recent feedback readout. No live feedback branch was run.
- `tj-final27.6` (`codex/tj-final27-5-6-feedback-referrals`, `93a0b51`) keeps referrals disabled-safe because no approved business rules were found. API/LLM paths are policy-gated, Operator Center exposes `client_decision_required`, and launch remains blocked pending written client referral policy or explicit exclusion.
- `tj-final27.7` (`codex/tj-final27-7-qa-reporting`, `a23e9e8`) adds refusal, feedback, and LLM cost-control fields to report data/text plus a safe QA/reporting runbook. Scheduled AI Quality Controls remain disabled by default and were not enabled.
- `tj-final27.8` (`codex/tj-final27-8-nonfunctional-readiness`, `c44ee71`) adds bounded local/mocked load harness, admin/auth guard checks in `verify_api.py`, security/infra tests, tracked-secret evidence, and client nonfunctional readiness documentation. Stronger production load or restore drills require explicit approval.

Initial admin inventory found three admin surfaces: SQLAdmin `/admin`, React `/dashboard`, and guarded `/api/v1/admin/*` APIs. The session guard is the shared SQLAdmin session token checked by `require_admin_session`; API-key headers alone do not pass admin guards. Existing panels covered metrics, notifications, product sync, reports, manager review queue, payment reminder controls, and AI Quality Controls with disabled defaults. Acceptance gaps were voice/audio audit fields, recent feedback/operator lifecycle readout, referral policy visibility, final report fields, and nonfunctional evidence; the integration branch closes those gaps except for client decisions and live E2E defers. Parallel frontend/admin write-conflict zones were `frontend/admin/src/components/OperatorCenter.tsx`, `frontend/admin/src/api/operators.ts`, `frontend/admin/src/types/operators.ts`, `src/api/v1/admin.py`, `src/api/admin/views.py`, and shared docs/handoff/summary files.

Integration verification passed:

- Combined targeted pytest: `171 passed`.
- `uv run ruff check src/ tests/`: passed.
- `uv run ruff format --check src/ tests/`: passed.
- `uv run ruff check src/ tests/ scripts/`: passed after orchestrator fixed existing `scripts/orchestration/*` lint/format blockers without changing bootstrap semantics.
- `uv run ruff format --check src/ tests/ scripts/`: passed.
- `uv run mypy src/`: passed.
- `npm --prefix frontend/admin run lint`: passed.
- `npm --prefix frontend/admin run build`: passed after installing ignored local frontend dependencies and ignored Tailwind native optional package; npm emitted Node 18 engine warnings for packages requiring Node 20.
- Artifact validation for `tj-final27.4` through `.8`: passed.
- `git diff --check main...HEAD`: passed.

No deploy, production config mutation, `scripts/verify_wazzup.py`, broad production suite, scheduled AI Quality Controls, live voice/media/payment/referral test, or real customer conversation was run.

Formal final acceptance still requires main merge/CI, deployment approval if desired, and explicit client decision for referrals plus any requested live voice/media/final E2E or production nonfunctional drill.
