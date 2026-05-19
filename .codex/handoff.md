# Orchestrator Handoff

Updated: 2026-05-19
Current branch: `codex/tj-gh18-open-issues-hardening`

## Current Truth

- Canonical host: `https://noor.starec.ai`; canonical runtime path: `/opt/noor`.
- Production release remains `3d24007713d5a2ca5068aeacc9c8719f101fe8d1`; no deploy or production mutation was performed in `tj-gh18`.
- Stage `tj-gh17` is delivered, deployed, live E2E verified, and GitHub #38 is closed.
- Stage `tj-gh18` is local-implementation verified for GitHub #39/#35 on branch `codex/tj-gh18-open-issues-hardening`.
- `tj-gh18.1` / #39 now parses `I need 6 CH 616`, `CH-616`, and `CH616` as product selection, stores `pending_quote_selection`, and avoids verified-policy manager handoff.
- `tj-gh18.2` / #35 now has explicit regressions proving deferred product media sends with `caption=None`, no caption CRM id, and only hidden non-customer-visible caption audit context.
- Verification passed for `tj-gh18`: targeted suites `246 passed`; full pytest `1056 passed, 19 skipped`; ruff, format-check, mypy, and process verification passed.
- Stage summary: `.codex/stages/tj-gh18/summary.md`; artifact: `.codex/stages/tj-gh18/artifacts/tj-gh18.1-2.md`.
- Orchestration baseline is `balanced-v2.7`; use repo-local commands in `.codex/orchestrator.toml`.

## Next recommended

Next stage id: `tj-gh18.3`.

Recommended action: deliver `codex/tj-gh18-open-issues-hardening` through the approved path, run the comprehensive deployed E2E matrix from `.codex/stages/tj-gh18/summary.md`, then comment and close GitHub #39/#35 only after passing evidence.

## Starter prompt for next orchestrator

Use $orchestrator-stage for `tj-gh18.3`: merge/deploy branch `codex/tj-gh18-open-issues-hardening`, run production synthetic/live E2E for SKU variants and product media captions, verify no manager handoff/no customer-visible caption leak, then close GitHub #39/#35 with evidence. Do not touch GitHub #11 until Lilia answers the pending questions.

## Explicit defers

- `tj-gh18.3` tracks delivery, deployed E2E, production/live evidence, comments, and GitHub closure for #39/#35.
- `tj-b4n` / GitHub #24 remains provider-blocked pending an official Wazzup typing endpoint.
- GitHub #11 remains pending Lilia's answers.
