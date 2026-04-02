# Orchestrator Handoff

Updated: 2026-04-02
Current baseline branch: `main`

## Current repo state

- Repo-local orchestration is intentionally minimal here: `.codex/orchestrator.toml` plus this handoff file only.
- `.gitignore` already allows those two files to be tracked; no broader `.codex/` ignore change was needed.
- Existing local `.codex/config.toml` in the primary worktree was reviewed for this setup and left untouched.
- The repository now operates in a main-only workflow: promote finished work directly into `main` instead of treating `develop` as a required intermediate branch.
- Prefer dedicated worktrees for orchestration work when the primary worktree contains unrelated local-only changes.
- Use `bd ready --json` for the current queue and `bd show <id>` for targeted task context.

## Open follow-ups / nearest ready tasks

- `tj-19ol` — P1 stage: canonical live testing re-entry on `https://noor.starec.ai`
- `tj-19ol.1` — P1 task: runtime sanity and access validation before smoke
- `tj-19ol.2` — P1 task: controlled live smoke for the escalation refactor
- `tj-19ol.3` — P2 task: triage live-testing findings into fixes or closures
- `tj-27v` — P1 bug: Wazzup cannot fetch Zoho OAuth-protected image URLs from `search_products`
- `tj-12a` — P1 feature: wire `search_knowledge()` into the LLM pipeline
- `tj-15m` — P1 task: reduce response latency via parallel tool execution and caching

## Rules for the next orchestrator

- Read `AGENTS.md`, `README.md`, and `.codex/orchestrator.toml` first; read `.codex/config.toml` too if it exists locally.
- Keep simple process-only tasks local; switch to orchestration when scope becomes multi-file, docs-sensitive, schema-sensitive, route-expanding, or parallel.
- Use dedicated worktrees with strict write zones and avoid unrelated local changes in the primary worktree.
- Keep reviews findings-first and do not treat a stage as closed until fresh local verification is done.
- Follow the session-completion rule from `AGENTS.md`: `git pull --rebase`, `bd sync`, then `git push`.
- Keep operator-facing runtime assumptions aligned with the current production host `https://noor.starec.ai`.
- Use the review artifact at `docs/reports/code-reviews/2026-04/CR-2026-04-02-main-only-workflow-review.md` as the latest completed cleanup baseline for the main-only transition.
- The next realistic execution stage is `tj-19ol`: re-enter controlled canonical live testing on `https://noor.starec.ai` before taking on broader backlog items.
