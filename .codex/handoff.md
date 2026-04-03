# Orchestrator Handoff

Updated: 2026-04-03
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
- `tj-5ypi` — P1 bug: align prod VPS deploy contract (`/opt/treejar-prod` + docker access for `noor-dev`)
- `tj-19ol.3.5` — P2 bug: canonical deploy/runtime drift after repo-side CI port fix
- `tj-27v` — P1 bug: Wazzup cannot fetch Zoho OAuth-protected image URLs from `search_products`
- `tj-12a` — P1 feature: wire `search_knowledge()` into the LLM pipeline
- `tj-15m` — P1 task: reduce response latency via parallel tool execution and caching
- `tj-19ol.3.10` — P1 bug: duplicate conversations on inbound chat lookup

## Rules for the next orchestrator

- Read `AGENTS.md`, `README.md`, and `.codex/orchestrator.toml` first; read `.codex/config.toml` too if it exists locally.
- Keep simple process-only tasks local; switch to orchestration when scope becomes multi-file, docs-sensitive, schema-sensitive, route-expanding, or parallel.
- Use dedicated worktrees with strict write zones and avoid unrelated local changes in the primary worktree.
- For delegated work, require a markdown report file and a short completion line with: task ID, report path, commit hash, git status clean yes/no.
- Keep reviews findings-first and do not treat a stage as closed until fresh local verification is done.
- Follow the session-completion rule from `AGENTS.md`: `git pull --rebase`, `bd sync`, then `git push`.
- Keep operator-facing runtime assumptions aligned with the current production host `https://noor.starec.ai`.
- Use the review artifact at `docs/reports/code-reviews/2026-04/CR-2026-04-02-main-only-workflow-review.md` as the latest completed cleanup baseline for the main-only transition.
- The current active execution stage remains `tj-19ol.3`, but the truth changed materially on 2026-04-03:
  - repo-side auth fail-open fix from `tj-19ol.3.1` is done and verified
  - canonical env fixes for `tj-19ol.3.2` and `tj-19ol.3.4` were applied locally, hot-applied to `/opt/noor`, and verified on `https://noor.starec.ai`
  - `tj-19ol.3.7` is closed: `notify_manager_escalation()` now persists an `Escalation` row, local tests are green, and direct in-container verification on canonical env confirmed `escalation_count=1` with `pending` status
  - `tj-19ol.3.8` is closed as transient/non-reproducible: after canonical recheck, direct `process_message()` replay, webhook canary, and live smoke no longer hit the 120s timeout
  - `tj-19ol.2` is closed: canonical escalation smoke is green by evidence
  - the only logic regression found in smoke was `tj-19ol.3.9` (concrete bulk order missing `order_confirmation` escalation on first turn); it is fixed via prompt contract update in `src/llm/prompts.py`, hot-applied to `/opt/noor`, rebuilt, and revalidated live
  - live evidence for the fix:
    - `I need 200 chairs delivered to Dubai Marina by next week` now yields `escalation_status=pending`, `escalation_count=1` in 22s on conversation `aee66c17-60e9-4de4-b4ff-235d02fa6b47`
    - `What are the wholesale prices for bulk orders?` still yields no escalation in 16s on conversation `029f43b4-add3-411a-92d3-2c14352cb74c`
  - next realistic blockers are no longer in the escalation flow itself; they are ops/runtime alignment (`tj-5ypi`, `tj-19ol.3.5`) and broader product work like latency (`tj-15m`) and FAQ/RAG quality (`tj-12a`)
  - additional canonical truth from the 2026-04-03 latency pass:
    - `tj-15m` is still active after a real profiling round
    - worker startup now warms `EmbeddingEngine`, which removes the first-message cold model load from the worker path
    - the acoustic-pods product path had an unbounded `search_products` retry loop; repo and canonical env now cap real product searches to 2 per customer message
    - direct isolated replay for `"Tell me about your acoustic pods"` dropped to about `15.25s` after the loop cap
    - canonical webhook canary no longer crashes on duplicate conversations for `+971000000001`; `src/services/chat.py` now chooses the most recent non-empty conversation instead of crashing on `MultipleResultsFound`
    - canonical webhook canary for the same acoustic-pods query still took `42.19s`, with logs showing remaining tail dominated by multiple OpenRouter turns, large accumulated context (`tokens_in=10353` on that run), and failing product-image uploads
    - `tj-27v` remains relevant: product image upload via `tmpfiles.org` currently returns HTTP `422`, so image delivery still fails and adds latency noise
  - next realistic latency slices are narrower than a broad refactor:
    - context/token-control work under `tj-15m`
    - `tj-27v` media upload repair for `search_products`
- Operational truth for canonical host:
  - live runtime is under `/opt/noor`, not `/opt/treejar-prod`
  - `noor-dev` now has enough access for direct hotfix work in `/opt/noor` and Docker-based inspection/rebuilds
  - repo-side CI/deploy contract drift (`tj-5ypi`, `tj-19ol.3.5`) still exists, but it is no longer the immediate blocker for runtime debugging because direct `/opt/noor` access is sufficient for canonical triage
