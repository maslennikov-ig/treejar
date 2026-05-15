# Orchestrator Handoff

Updated: 2026-05-15
Current branch: `codex/tj-gh15-name-escalation-hardening`

## Current Truth

- Canonical host: `https://noor.starec.ai`; canonical runtime path: `/opt/noor`.
- Production state before `tj-gh15` delivery is `7075be5831dd0e09e29a319d842003f24c6dcf0f`.
- Stage `tj-gh15` is in progress for reopened GitHub #36/#37 hardening after Lili's production conversation `94343a3d-dce0-4fb0-ab05-8b9c00f80b9f`.
- Local branch/worktree: `codex/tj-gh15-name-escalation-hardening` at `/home/me/code/treejar/.worktrees/codex-tj-gh15-name-escalation-hardening`, based on `origin/main@3f539f5cd4e404eaab7fc776945d367e6afa07bb`.
- Implemented locally: bare-name replies such as `Lili` are accepted only when a pending name-gate request exists, stored in customer/quote metadata, and resume the stored original request.
- Implemented locally: verified-answer product classification recognizes catalog brand/family/product terms such as Skyland, Novo, XTEN, Trend, Imago, drawers, pedestals, cabinets, storage, and work stations; quantity plus likely catalog item stays on product/catalog path.
- Lili's real WhatsApp thread was used only for read-only root-cause analysis; it has not been mutated.
- Verification passed: new targeted regression suite `13 passed`, modified LLM policy suites `183 passed`, full `ruff check`, `ruff format --check`, `mypy`, full pytest `1033 passed, 19 skipped`, and process verification.
- First full pytest in this clean worktree failed only because frontend admin `node_modules` were absent; `npm ci` in `frontend/admin` installed the lockfile dependencies and the full suite then passed.
- Stage summary: `.codex/stages/tj-gh15/summary.md`; artifact: `.codex/stages/tj-gh15/artifacts/tj-gh15.1-2.md`.
- Local Beads: `tj-gh15` epic plus `tj-gh15.1` (#36), `tj-gh15.2` (#37), and `tj-gh15.3` production cleanup/live E2E.
- No GitHub issue mutation, deployment, or production DB mutation has been performed yet for `tj-gh15`.
- Live E2E and production DB cleanup for `79262810921%` are explicitly approved by the user for this task after merge/deploy.
- Orchestration baseline is `balanced-v2.7`; use repo-local commands in `.codex/orchestrator.toml`.

## Next recommended

Next stage id: `tj-gh15.3`

Recommended action: Commit and push `codex/tj-gh15-name-escalation-hardening`, fast-forward `main`, push `origin/main`, wait for GitHub Actions deploy, verify release/API health, clean production DB state for `79262810921%` in one audited transaction, run live E2E on `+79262810921`, then comment on and close GitHub #36/#37 with evidence.

Use $orchestrator-stage for delivery, production cleanup, live E2E, and GitHub issue closure because these are externally visible follow-through steps for stage `tj-gh15`.

## Starter prompt for next orchestrator

Continue stage `tj-gh15` delivery from branch `codex/tj-gh15-name-escalation-hardening`. Do not touch Lili's real thread. Use approved test number `+79262810921` only after deploy and audited cleanup.

## Explicit defers

- `tj-gh15.3` remains pending until merge, deploy, production cleanup, live E2E, and GitHub #36/#37 closure.
- `tj-b4n` / GitHub #24 remains provider-blocked pending an official Wazzup typing endpoint.
