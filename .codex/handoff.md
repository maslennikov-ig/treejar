# Orchestrator Handoff

Updated: 2026-04-02
Current baseline branch: `main`

## Current repo state

- Repo-local orchestration is intentionally minimal here: tracked contract files live in `.codex/`, while delegated agent reports are local-only under `.codex/agent-reports/`.
- `.gitignore` tracks the repo-local contract files and keeps delegated agent reports under `.codex/agent-reports/` local-only.
- Existing local `.codex/config.toml` in the primary worktree was reviewed for this setup and left untouched.
- The repository now operates in a main-only workflow: promote finished work directly into `main` instead of treating `develop` as a required intermediate branch.
- Prefer dedicated worktrees for orchestration work when the primary worktree contains unrelated local-only changes.
- Use `bd ready --json` for the current queue and `bd show <id>` for targeted task context.

## Open follow-ups / nearest ready tasks

- `tj-19ol` — P1 stage: canonical live testing re-entry on `https://noor.starec.ai`
- `tj-19ol.3` — P2 task: blocker-driven triage for canonical live-testing findings
- `tj-19ol.3.8` — P1 bug: investigate `LLM timeout after 120s` on canonical smoke path
- `tj-19ol.2` — P1 task: controlled live smoke for the escalation refactor (blocked by `tj-19ol.3.8`)
- `tj-5ypi` — P1 bug: align prod VPS deploy contract (`/opt/treejar-prod` + docker access for `noor-dev`)
- `tj-19ol.3.5` — P2 bug: canonical deploy/runtime drift after repo-side CI port fix
- `tj-27v` — P1 bug: Wazzup cannot fetch Zoho OAuth-protected image URLs from `search_products`
- `tj-12a` — P1 feature: wire `search_knowledge()` into the LLM pipeline
- `tj-15m` — P1 task: reduce response latency via parallel tool execution and caching

## Rules for the next orchestrator

- Read `AGENTS.md`, `README.md`, and `.codex/orchestrator.toml` first; read `.codex/config.toml` too if it exists locally.
- Keep simple process-only tasks local; switch to orchestration when scope becomes multi-file, docs-sensitive, schema-sensitive, route-expanding, or parallel.
- Use dedicated worktrees with strict write zones and avoid unrelated local changes in the primary worktree.
- For delegated work, require a markdown report file and a short completion line with: task ID, report path, commit hash, git status clean yes/no.
- Keep reviews findings-first and do not treat a stage as closed until fresh local verification is done.
- Follow the session-completion rule from `AGENTS.md`: `git pull --rebase`, `bd sync`, then `git push`.
- Keep operator-facing runtime assumptions aligned with the current production host `https://noor.starec.ai`.
- Use the review artifact at `docs/reports/code-reviews/2026-04/CR-2026-04-02-main-only-workflow-review.md` as the latest completed cleanup baseline for the main-only transition.
- The current active execution stage remains `tj-19ol.3`, but the truth changed materially on 2026-04-02:
  - repo-side auth fail-open fix from `tj-19ol.3.1` is done and verified
  - canonical env fixes for `tj-19ol.3.2` and `tj-19ol.3.4` were applied locally, hot-applied to `/opt/noor`, and verified on `https://noor.starec.ai`
  - `tj-19ol.3.7` is closed: `notify_manager_escalation()` now persists an `Escalation` row, local tests are green, and direct in-container verification on canonical env confirmed `escalation_count=1` with `pending` status
  - current nearest blocker is `tj-19ol.3.8`: the live webhook path reaches `process_incoming_batch`, persists the user message, then stalls on the LLM call and aborts with `LLM timeout after 120s for chat_id=+971000000001`; the transaction rolls back and the conversation stays `escalation_status=none`
  - `tj-19ol.2` is therefore blocked again until `tj-19ol.3.8` is triaged
- Operational truth for canonical host:
  - live runtime is under `/opt/noor`, not `/opt/treejar-prod`
  - `noor-dev` now has enough access for direct hotfix work in `/opt/noor` and Docker-based inspection/rebuilds
  - repo-side CI/deploy contract drift (`tj-5ypi`, `tj-19ol.3.5`) still exists, but it is no longer the immediate blocker for runtime debugging because direct `/opt/noor` access is sufficient for canonical triage
