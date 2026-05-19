# Orchestrator Handoff

Updated: 2026-05-19
Current branch: `main`

## Current Truth

- Canonical host: `https://noor.starec.ai`; canonical runtime path: `/opt/noor`.
- Production release is `b05422e1fb6647ffda7a10c337eef9c7c922273d`; GitHub Actions run `26094670599` succeeded; `/opt/noor/.release-sha` matches.
- Stage `tj-gh18` is delivered, deployed, live E2E verified, and GitHub #39/#35 are closed.
- Stage `tj-gh19` is delivered, deployed, live E2E verified, Beads closed, and GitHub #40 is closed.
- `tj-gh19.1` / #40 context fix preserves pending quote context for terse details like `Lil, 1 dubay`, stores name/address, keeps `pending_quote_selection`, and asks only for missing company-or-individual when address is specific.
- `tj-gh19.2` / #40 quantity fix prevents model numbers such as `SKYLAND NOVO 2400` from becoming quantities for `CH 616`; prior SKU variants including Cyrillic homoglyph `СН 616` remain covered.
- Final `tj-gh19` verification passed: targeted LLM/verified-answer suites `215 passed`; ruff, format-check, mypy, git diff check, full pytest `1066 passed, 19 skipped`, process verification, and stage closeout.
- Production smoke passed: `scripts/verify_api.py --base-url https://noor.starec.ai` -> `7 passed, 0 failed`.
- Final live E2E conversation `640d0cfb-0460-4033-b6f0-7de84eadcc2a` verified name-gate resume, exact product reference quantity clarification, `NOVO 2400` non-quantity behavior, `CH 616` variant selection, `Lil, 1 dubay` quote-context preservation, company-or-individual gate, and no escalation.
- Stage summary: `.codex/stages/tj-gh19/summary.md`; artifacts: `.codex/stages/tj-gh19/artifacts/tj-gh19.1-2.md`, `.codex/stages/tj-gh19/artifacts/tj-gh19.3-live-e2e.md`.
- Orchestration baseline is `balanced-v2.7`; use repo-local commands in `.codex/orchestrator.toml`.

## Next recommended

Next stage id: `tj-gh20` if new GitHub issues appear, otherwise no active delivery stage.

Recommended action: no action for #40; keep #11 pending until Lilia answers the already-posted questions.

## Starter prompt for next orchestrator

Use $orchestrator-stage for the next medium/complex issue batch. Current delivered production release is `b05422e1fb6647ffda7a10c337eef9c7c922273d`; `tj-gh19` / GitHub #40 is closed with production E2E evidence in conversation `640d0cfb-0460-4033-b6f0-7de84eadcc2a`. Do not touch GitHub #11 until Lilia answers the pending questions.

## Explicit defers

- `tj-b4n` / GitHub #24 remains provider-blocked pending an official Wazzup typing endpoint.
- GitHub #11 remains pending Lilia's answers.
