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
- Stage `tj-gh20` is locally implemented in branch/worktree `codex/tj-gh20-dialogue-state-kernel` at `/home/me/code/treejar/.worktrees/codex-tj-gh20-dialogue-state-kernel`, not merged or deployed.
- `tj-gh20` adds a LangGraph Dialogue State Kernel with default `legacy`, side-effect-free `shadow`, and allowlisted `enforce`; exact SKU+quantity turns are recognized but delegated to legacy in v1 until kernel-owned quote side effects are implemented.
- `tj-gh20` artifacts: `.codex/stages/tj-gh20/summary.md`, `.codex/stages/tj-gh20/artifacts/tj-gh20.1-docs-fixtures.md`, `.codex/stages/tj-gh20/artifacts/tj-gh20.2-6-runtime-kernel.md`, `.codex/stages/tj-gh20/artifacts/tj-gh20.6-readonly-review.md`.
- Orchestration baseline is `balanced-v2.7`; use repo-local commands in `.codex/orchestrator.toml`.

## Next recommended

Next stage id: `tj-gh20.7` delivery/shadow E2E if explicitly authorized, otherwise no production action.

Recommended action: finish local `tj-gh20` gates and stage closeout, then ask before any merge, deploy, production shadow config, synthetic/live E2E, or GitHub mutation. Keep #11 pending until Lilia answers the already-posted questions.

## Starter prompt for next orchestrator

Use $orchestrator-stage for the next medium/complex issue batch. Current delivered production release is `b05422e1fb6647ffda7a10c337eef9c7c922273d`; `tj-gh19` / GitHub #40 is closed with production E2E evidence in conversation `640d0cfb-0460-4033-b6f0-7de84eadcc2a`. Local `tj-gh20` work lives in `/home/me/code/treejar/.worktrees/codex-tj-gh20-dialogue-state-kernel` and must not be described as deployed. Do not touch GitHub #11 until Lilia answers the pending questions.

## Explicit defers

- `tj-b4n` / GitHub #24 remains provider-blocked pending an official Wazzup typing endpoint.
- GitHub #11 remains pending Lilia's answers.
