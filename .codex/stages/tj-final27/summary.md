# Stage tj-final27: Final Delivery Completion

Updated: 2026-04-30
Status: active
Branch: `codex/tj-final27-final-delivery-plan`
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

Remaining final-acceptance work is `tj-final27.4` through `tj-final27.8`, with live WhatsApp/media/voice/E2E tests requiring explicit scenario approval before execution.
