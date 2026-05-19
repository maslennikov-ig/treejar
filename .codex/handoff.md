# Orchestrator Handoff

Updated: 2026-05-19
Current branch: `codex/tj-gh19-quote-context-hardening`

## Current Truth

- Canonical host: `https://noor.starec.ai`; canonical runtime path: `/opt/noor`.
- Production release is `af39abc4a1f299eb2c37af916c14d476ea2ab1b7`; GitHub Actions run `26087478319` succeeded; `/opt/noor/.release-sha` matches.
- Stage `tj-gh18` is delivered, deployed, live E2E verified, and GitHub #39/#35 are closed.
- Stage `tj-gh19` is in local implementation on branch `codex/tj-gh19-quote-context-hardening`; no merge/deploy/GitHub #40 closure yet.
- `tj-gh19.1` / #40 context fix preserves pending quote context for terse details like `Lil, 1 dubay`, stores name/address, keeps `pending_quote_selection`, and asks only for missing company-or-individual when address is specific.
- `tj-gh19.2` / #40 quantity fix prevents model numbers such as `SKYLAND NOVO 2400` from becoming quantities for `CH 616`; prior SKU variants including Cyrillic homoglyph `СН 616` remain covered.
- Local verification passed for `tj-gh19`: targeted LLM/verified-answer suites `212 passed`; ruff, format-check, mypy, git diff check, full pytest `1063 passed, 19 skipped`, process verification, and stage closeout.
- Stage summary: `.codex/stages/tj-gh19/summary.md`; artifact: `.codex/stages/tj-gh19/artifacts/tj-gh19.1-2.md`.
- Orchestration baseline is `balanced-v2.7`; use repo-local commands in `.codex/orchestrator.toml`.

## Next recommended

Next stage id: `tj-gh19.3` after delivery authorization.

Recommended action: commit the local implementation. Merge/deploy/live E2E/GitHub #40 closure require explicit current authorization.

## Starter prompt for next orchestrator

Use $orchestrator-stage for `tj-gh19.3` delivery only after explicit merge/deploy/production authorization. Current delivered production release is `af39abc4a1f299eb2c37af916c14d476ea2ab1b7`; `tj-gh19` local implementation is on `codex/tj-gh19-quote-context-hardening`. Do not touch GitHub #11 until Lilia answers the pending questions.

## Explicit defers

- `tj-gh19.3` tracks merge/deploy/production E2E/GitHub #40 closure.
- `tj-b4n` / GitHub #24 remains provider-blocked pending an official Wazzup typing endpoint.
- GitHub #11 remains pending Lilia's answers.
