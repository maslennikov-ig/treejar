# Stage tj-gh15: Name-Gate Memory and Escalation Hardening

Updated: 2026-05-15
Status: delivered, deployed, live E2E verified, and GitHub issues closed
Branch: `codex/tj-gh15-name-escalation-hardening`
Base: `origin/main@3f539f5cd4e404eaab7fc776945d367e6afa07bb`

## Goal

Fix the reopened GitHub #36/#37 regressions observed in Lili's production
conversation without mutating her real WhatsApp thread.

## Scope

- `tj-gh15.1` / #36: bare-name reply after first-turn name gate must store the
  name, consume `name_gate_pending_request`, and resume the stored substantive
  request.
- `tj-gh15.2` / #37: product/brand plus quantity must stay on product/catalog
  handling and must not route to verified-policy manager handoff.
- `tj-gh15.3`: after deploy, clean approved production test number
  `+79262810921`, run live E2E, then comment on and close GitHub #36/#37.

## Root Cause

Production conversation `94343a3d-dce0-4fb0-ab05-8b9c00f80b9f` showed that
bare `Lili` was not parsed as a customer name, leaving `customer_name` null and
`name_gate_pending_request` in metadata. Later `2 Skyland Novo and 2xten` was
classified as missing-support `service_low_risk`, which triggered verified-policy
handoff because catalog brand/family terms were not product signals.

## Implementation

- Added deterministic bare-name detection for pending name-gate conversations.
  It accepts short Unicode names and rejects affirmations, quantities, product
  words, service/action words, and catalog brand/family terms.
- Persisted bare-name details through the same quote/customer metadata path used
  by natural name extraction, then reused the existing pending-request resume
  directive.
- Preserved the name-gate continuation directive when later mixed product/service
  or service-policy routing adds its own runtime directives.
- Extended verified-answer product classification with Treejar catalog terms and
  quantity-plus-product selection detection.

## Verification

- RED tests added and observed for bare `Lili` resume and brand+quantity product
  classification.
- New targeted regression suite: 13 passed.
- Modified LLM policy suites: 183 passed.
- Full gates passed:
  - `uv run ruff check src/ tests/`
  - `uv run ruff format --check src/ tests/`
  - `uv run mypy src/`
  - `env DYLD_FALLBACK_LIBRARY_PATH="${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}" uv run pytest tests/ -v --tb=short` -> 1033 passed, 19 skipped.
  - `scripts/orchestration/run_process_verification.sh`
  - `scripts/orchestration/run_stage_closeout.py --stage tj-gh15`

## Delivery And Live E2E

- Pushed `origin/codex/tj-gh15-name-escalation-hardening` and fast-forwarded
  `origin/main` to `cf966f0e2345da0154c8f11f57c0c60340ff451e`.
- GitHub Actions run `25910228955` completed successfully.
- Production release marker `/opt/noor/.release-sha` matches
  `cf966f0e2345da0154c8f11f57c0c60340ff451e`; `/opt/noor/.release-run-id`
  is `25910228955`.
- Production API smoke passed: `7 passed, 0 failed`.
- Approved cleanup prefix `79262810921%` was deleted in one transaction:
  before cleanup there were 72 conversations, 284 messages, 250 outbound audit
  rows, 41 escalations, and 7 quality reviews; after cleanup all matching counts
  were 0.
- Live conversation `5e587327-0092-4699-a4ee-df6e23edf0ca` passed:
  `name-gate` first reply, bare `Lili` resumed the stored request, final
  `customer_name=Lili`, `name_gate_pending_request` absent,
  `escalation_status=none`, pending escalations `0`, and the product/quantity
  message stayed on product clarification with no manager handoff text.
- Independent read-only verifier subagent returned PASS on production release,
  runtime health, DB state, transcript, metadata, and no escalation text.
- GitHub #36 and #37 were commented with fix and verification evidence and
  closed as completed:
  - #36: https://github.com/maslennikov-ig/treejar/issues/36#issuecomment-4459034706
  - #37: https://github.com/maslennikov-ig/treejar/issues/37#issuecomment-4459034949

## Boundaries

- Lili's real WhatsApp conversation was not mutated.
- No `tj-gh15` defers remain.
