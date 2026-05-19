# Orchestrator Handoff

Updated: 2026-05-19
Current branch: `main`

## Current Truth

- Canonical host: `https://noor.starec.ai`; canonical runtime path: `/opt/noor`.
- Production release is `af39abc4a1f299eb2c37af916c14d476ea2ab1b7`; GitHub Actions run `26087478319` succeeded; `/opt/noor/.release-sha` matches.
- Stage `tj-gh17` is delivered, deployed, live E2E verified, and GitHub #38 is closed.
- Stage `tj-gh18` is delivered, deployed, live E2E verified, and GitHub #39/#35 are closed.
- `tj-gh18.1` / #39 parses `CH 616`, `CH-616`, `CH616`, lowercase, Cyrillic homoglyph `СН 616`, and repeated spaces `CH   616` as product selection, stores `pending_quote_selection`, and avoids verified-policy manager handoff.
- `tj-gh18.2` / #35 is live-verified: product media rows have provider ids, hidden caption audit rows have `provider_message_id=NULL` and `customer_visible=false`, with no separate customer-visible caption text.
- Final live evidence: #39 conversation `e3b12221-7206-4be8-8e59-d70d0732d446`; #35 media conversation `d331625b-84be-442e-9b6a-f92ce6139101`; production API smoke `7 passed, 0 failed`.
- Verification passed for `tj-gh18`: final full pytest `1057 passed, 19 skipped`; ruff, format-check, mypy, process verification, stage closeout, final deploy, production SKU matrix, and live E2E passed.
- Stage summary: `.codex/stages/tj-gh18/summary.md`; artifacts: `.codex/stages/tj-gh18/artifacts/tj-gh18.1-2.md`, `.codex/stages/tj-gh18/artifacts/tj-gh18.3-live-e2e.md`.
- Orchestration baseline is `balanced-v2.7`; use repo-local commands in `.codex/orchestrator.toml`.

## Next recommended

Next stage id: none.

Recommended action: monitor normal production behavior; no remaining `tj-gh18` delivery action.

## Starter prompt for next orchestrator

Use $orchestrator-stage for the next distinct production issue. Current delivered production release is `af39abc4a1f299eb2c37af916c14d476ea2ab1b7`; `tj-gh18` is closed after live E2E. Do not touch GitHub #11 until Lilia answers the pending questions.

## Explicit defers

- none for `tj-gh18`.
- `tj-b4n` / GitHub #24 remains provider-blocked pending an official Wazzup typing endpoint.
- GitHub #11 remains pending Lilia's answers.
