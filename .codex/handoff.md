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
- `tj-15m.4` is now merged into `main` and hot-applied on canonical runtime `/opt/noor`: it adds persistent `ConversationSummary` storage + migration, an async ARQ refresh job on the fast model path, a shared hybrid context builder (`summary + raw recent tail`) for main/follow-up paths, and post-reply enqueue after assistant commit.
- Two additional live-fix slices were merged into `main` on 2026-04-03 and verified locally:
  - `0794240` `fix(prompt): harden concrete order escalation contract`
  - `b913444` `fix: enforce product search loop cap`
- Review follow-up fixes are also in `main`: raw tail no longer overlaps already-covered summary turns, and runtime message creation now stamps deterministic `created_at` values instead of relying on `server_default(now())` for batched ordering.
- A late production blocker was fixed locally on 2026-04-03: Alembic revision `2026_04_03_conversation_summaries` exceeded the production `alembic_version.version_num varchar(32)` limit. It was shortened to `2026_04_03_conv_summary_001`, and `tests/test_migrations.py` now guards all Alembic revision lengths.

## Open follow-ups / nearest ready tasks

- `tj-19ol` — P1 stage: canonical live testing re-entry on `https://noor.starec.ai`
- `tj-19ol.3` — P2 task: blocker-driven triage for canonical live-testing findings
- `tj-19ol.3.12` — P1 task: hot-apply merged live fixes to canonical runtime and rerun targeted live retest
- `tj-5ypi` — P1 bug: align prod VPS deploy contract (`/opt/treejar-prod` + docker access for `noor-dev`)
- `tj-19ol.3.5` — P2 bug: canonical deploy/runtime drift after repo-side CI port fix
- `tj-27v` — P1 bug: Wazzup cannot fetch Zoho OAuth-protected image URLs from `search_products`
- `tj-12a` — P1 feature: wire `search_knowledge()` into the LLM pipeline
- `tj-15m` — P1 task: reduce response latency via parallel tool execution and caching
- `tj-15m.5` — P1 bug: quantify remaining latency after hybrid summary apply
- `tj-19ol.3.11` — P1 bug: live first-turn concrete order regression is fixed in repo, pending canonical retest
- `tj-15m.5.1` — P1 bug: live product-search loop overflow is fixed in repo, pending canonical retest

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
  - `tj-15m.4` is closed after canonical deploy/retest:
    - `/opt/noor` was updated and rebuilt successfully
    - worker logs confirm `refresh_conversation_summary` executed successfully and created/updated a `conversation_summaries` row for `+971000000001`
    - controlled webhook retest on canonical env after deploy showed:
      - warmup_1 `24.55s`, `tokens_in=2427`
      - warmup_2 `17.48s`, `tokens_in=6527`
      - warmup_3 `36.13s`, `tokens_in=6536`
      - target `"Tell me about your acoustic pods"` `35.84s`, `tokens_in=10396`
      - follow-up `"Do they work for 4-person meetings and private calls?"` `16.70s`, `tokens_in=3153`
      - wholesale guard `20.11s`, `tokens_in=2972`
      - `escalation_status` stayed `none` throughout
    - summary persistence is therefore no longer the blocker; residual latency moved to `tj-15m.5`
  - `tj-27v` remains relevant: product image upload via `tmpfiles.org` currently returns HTTP `422`, so image delivery still fails and adds latency noise
  - next realistic latency slices are narrower than a broad refactor:
    - product-search/tool-context work under `tj-15m.5`
    - `tj-27v` media upload repair for `search_products`
- Operational truth for canonical host:
  - live runtime is under `/opt/noor`, not `/opt/treejar-prod`
  - `noor-dev` now has enough access for direct hotfix work in `/opt/noor` and Docker-based inspection/rebuilds
  - repo-side CI/deploy contract drift (`tj-5ypi`, `tj-19ol.3.5`) still exists, but it is no longer the immediate blocker for runtime debugging because direct `/opt/noor` access is sufficient for canonical triage
  - canonical live-delivery test recipient changed on 2026-04-03: use `+79262810921` for future WhatsApp smoke and delivery verification
  - previous `+971000000001` should now be treated only as a synthetic/non-deliverable runtime artifact for DB/log-path checks, not as a real delivery target
  - full live smoke was rerun on `+79262810921`:
    - PASS: MOQ no escalation
    - FAIL before new fixes: first-turn concrete order did not escalate as `order_confirmation`
    - PASS: explicit manager request -> `human_requested`
    - PASS with latency issue: acoustic pods -> no escalation, but about 31s and three live `search_products` calls
    - PASS: complaint -> `general`
    - PASS: wholesale pricing -> no escalation
    - PASS: refund -> `general`
  - next realistic step is now `tj-19ol.3.12`, not a new code slice:
    - hot-apply `0794240` and `b913444` to `/opt/noor`
    - rebuild `app` + `worker`
    - rerun targeted live checks on `+79262810921`:
      - `I need 200 chairs delivered to Dubai Marina by next week`
      - `Tell me about your acoustic pods`
    - if both pass, close `tj-19ol.3.11` and `tj-15m.5.1`; if not, branch the next bug from fresh evidence
