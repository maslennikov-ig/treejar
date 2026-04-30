# Stage tj-final27: Final Delivery Completion

Updated: 2026-04-29
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

Stale review findings against old feature worktrees are resolved on current deployed `main`.

`tj-final27.11` is implemented and closed locally in branch `codex/tj-final27-11-sales-fallback`. It adds compact deterministic sales fallbacks for price objection, retention/drop-off, and known off-catalog requests without expanding the base system prompt. DeepSeek sandbox task `tj-final27.12` was deleted per user decision. Verification passed: targeted RED/GREEN tests, `tests/test_verified_answers.py tests/test_llm_engine.py` (`92 passed`), ruff, mypy, artifact validation, process verification, and full pytest with capture disabled (`826 passed`, `19 skipped`). No prod config/deploy/live WhatsApp/Wazzup/Zoho mutation was run.

Remaining final-acceptance work is `tj-final27.4` through `tj-final27.9`, with live WhatsApp/media/voice/E2E tests requiring explicit scenario approval before execution.
