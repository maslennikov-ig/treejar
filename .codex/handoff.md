# Orchestrator Handoff

Updated: 2026-04-04
Current baseline branch: `main`

## Current repo state

- Repo-local orchestration is intentionally minimal here: tracked contract files live in `.codex/`, while delegated agent reports are local-only under `.codex/agent-reports/`.
- `.gitignore` tracks the repo-local contract files and keeps delegated agent reports under `.codex/agent-reports/` local-only.
- Existing local `.codex/config.toml` in the primary worktree was reviewed for this setup and left untouched.
- `tj-hd0n` is now closed on `main` as a reporting-quality cleanup:
  - Telegram `Daily Summary` no longer reuses the broad dashboard payload and no longer shows `LLM Cost`
  - daily summary now uses a dedicated calculator with honest `N/A` rendering for missing `Avg Quality` / `Conversion Rate (7d)` basis
  - `Conversion Rate (7d)` is now defined as delivered deals over conversations with assistant activity in the last 7 days
  - rolling quality evaluation is no longer tied only to `Conversation.status == "closed"`; worker now runs `evaluate_recent_conversations_quality()` and `save_review()` updates existing `quality_reviews` rows instead of insert-only behavior
- The repository now operates in a main-only workflow: promote finished work directly into `main` instead of treating `develop` as a required intermediate branch.
- Prefer dedicated worktrees for orchestration work when the primary worktree contains unrelated local-only changes.
- Use `bd ready --json` for the current queue and `bd show <id>` for targeted task context.
- `tj-15m.4` is now merged into `main` and hot-applied on canonical runtime `/opt/noor`: it adds persistent `ConversationSummary` storage + migration, an async ARQ refresh job on the fast model path, a shared hybrid context builder (`summary + raw recent tail`) for main/follow-up paths, and post-reply enqueue after assistant commit.
- Two additional live-fix slices were merged into `main` on 2026-04-03 and verified locally:
  - `0794240` `fix(prompt): harden concrete order escalation contract`
  - `b913444` `fix: enforce product search loop cap`
  - `c64d84c` `fix(prompt): preserve consultative bulk discovery`
- Review follow-up fixes are also in `main`: raw tail no longer overlaps already-covered summary turns, and runtime message creation now stamps deterministic `created_at` values instead of relying on `server_default(now())` for batched ordering.
- A late production blocker was fixed locally on 2026-04-03: Alembic revision `2026_04_03_conversation_summaries` exceeded the production `alembic_version.version_num varchar(32)` limit. It was shortened to `2026_04_03_conv_summary_001`, and `tests/test_migrations.py` now guards all Alembic revision lengths.

## Open follow-ups / nearest ready tasks

- `tj-19ol` — P1 stage: canonical live testing re-entry on `https://noor.starec.ai`
- `tj-19ol.3` — P2 task: blocker-driven triage for canonical live-testing findings
- `tj-5ypi` — P1 bug: align prod VPS deploy contract (`/opt/treejar-prod` + docker access for `noor-dev`)
- `tj-19ol.3.5` — P2 bug: canonical deploy/runtime drift after repo-side CI port fix
- `tj-27v` — P1 bug: Wazzup cannot fetch Zoho OAuth-protected image URLs from `search_products`
- `tj-12a` — P1 feature: wire `search_knowledge()` into the LLM pipeline
- `tj-15m` — P1 task: reduce response latency via parallel tool execution and caching
- `tj-15m.5` — P1 bug: quantify remaining latency after hybrid summary apply
- `tj-19ol.3.11` — P1 bug: prompt slice is merged, but canonical retest showed the live first-turn concrete-order regression still persists; see `tj-19ol.3.13`
- `tj-15m.5.2` — P1 bug: improve product-answer quality on product-heavy consultative paths after the verified search cap

## Rules for the next orchestrator

- Read `AGENTS.md`, `README.md`, and `.codex/orchestrator.toml` first; read `.codex/config.toml` too if it exists locally.
- Keep simple process-only tasks local; switch to orchestration when scope becomes multi-file, docs-sensitive, schema-sensitive, route-expanding, or parallel.
- Use dedicated worktrees with strict write zones and avoid unrelated local changes in the primary worktree.
- For delegated work, require a markdown report file and a short completion line with: task ID, report path, commit hash, git status clean yes/no.
- Keep reviews findings-first and do not treat a stage as closed until fresh local verification is done.
- Follow the session-completion rule from `AGENTS.md`: `git pull --rebase`, then apply the Beads 1.0.0 maintenance steps as needed (`bd bootstrap --yes`, `bd import`, `bd hooks install`, `bd export -o .beads/issues.jsonl`), then `git push`.
- Keep operator-facing runtime assumptions aligned with the current production host `https://noor.starec.ai`.
- Use the review artifact at `docs/reports/code-reviews/2026-04/CR-2026-04-02-main-only-workflow-review.md` as the latest completed cleanup baseline for the main-only transition.
- The current active execution stage remains `tj-19ol.3`, but the truth changed materially on 2026-04-03:
  - repo-side auth fail-open fix from `tj-19ol.3.1` is done and verified
  - canonical env fixes for `tj-19ol.3.2` and `tj-19ol.3.4` were applied locally, hot-applied to `/opt/noor`, and verified on `https://noor.starec.ai`
  - `tj-19ol.3.7` is closed: `notify_manager_escalation()` now persists an `Escalation` row, local tests are green, and direct in-container verification on canonical env confirmed `escalation_count=1` with `pending` status
  - `tj-19ol.3.8` is closed as transient/non-reproducible: after canonical recheck, direct `process_message()` replay, webhook canary, and live smoke no longer hit the 120s timeout
  - `tj-19ol.2` should no longer be treated as fully green: the earlier broad smoke passed except for the first-turn concrete-order case, and the targeted retest on 2026-04-03 confirmed that this regression still exists on the real-recipient runtime path
  - `tj-19ol.3.12` is closed as an execution task: merged fixes were hot-applied to `/opt/noor`, `app` + `worker` were rebuilt, and the targeted retest completed on real recipient `+79262810921`
  - targeted live retest truth after hot-apply:
    - concrete order still FAILS: `I need 200 chairs delivered to Dubai Marina by next week` on conversation `4425381e-3ebc-4f78-8a1c-e6b120b5b0c9` produced a qualifying assistant reply in `16.02s`, `tokens_in=2020`, `escalation_status=none`, `escalations=0`; prompt-only hardening is insufficient on the hosted model/runtime path
    - consultative bulk guard PASSES: `We need 20 chairs for next week, what options do you have?` on conversation `76e78300-3df5-47a3-ade1-59dfa5bb26ab` stayed non-escalation, returned useful chair options in `10.11s`, and executed exactly one real `search_products` call
    - acoustic pods remains PARTIAL: `Tell me about your acoustic pods` on conversation `63d6283a-3672-40a4-89cb-9c966b930905` stayed non-escalation, took `34.03s`, used `tokens_in=9429`, executed exactly two real `search_products` calls, then removed `search_products` from the available toolset as intended, but the final answer quality was weak and `tmpfiles.org` image uploads still failed with repeated `422`
  - `tj-19ol.3.13` is now merged into `main`, hot-applied to `/opt/noor`, and validated on canonical runtime:
    - merge commit on `main`: `5cf6d30` (`fix: merge order handoff guard`)
    - targeted live retest on real recipient `+79262810921` for `"I need 200 chairs delivered to Dubai Marina by next week"` now PASSES
    - conversation `080af0e3-e27d-4f81-8805-ba1bc2d67c2d` was created on the exact phone, triggered `escalate_to_manager(order_confirmation)`, persisted an `Escalation` row, set `escalation_status=pending`, stored a handoff-style assistant reply, and sent via Wazzup with `POST /v3/message -> 201 Created`
    - runtime duration for that fixed case was `19.66s`; stored assistant message had `tokens_in=1268`, `tokens_out=370`
  - consultative routing was rechecked on the same runtime and did not over-tighten:
    - `"We need 20 chairs for next week, what options do you have?"` on conversation `30dae35f-f838-42ac-ac92-bad379377265` stayed non-escalated with `escalation_count=0`
    - however, answer quality remained weak: the model asked qualifying questions instead of surfacing concrete options, despite normal `search_products('chairs')` and subsequent `get_stock(...)` calls
    - runtime duration for that consultative case was `38.24s`; stored assistant message had `tokens_in=9792`, `tokens_out=711`
  - next realistic blockers are therefore narrower and evidence-based:
    - `tj-15m.5.2` for product-heavy consultative answer quality after search/tool work
    - `tj-27v` still matters because media/upload failures are adding noise and hurting product replies
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
  - full live smoke was rerun on `+79262810921` before the latest hot-apply:
    - PASS: MOQ no escalation
    - FAIL before new fixes: first-turn concrete order did not escalate as `order_confirmation`
    - PASS: explicit manager request -> `human_requested`
    - PASS with latency issue: acoustic pods -> no escalation, but about 31s and three live `search_products` calls
    - PASS: complaint -> `general`
    - PASS: wholesale pricing -> no escalation
    - PASS: refund -> `general`
  - targeted post-hot-apply retest is now complete in two rounds:
    - round 1 hot-applied `0794240`, `b913444`, and `c64d84c` to `/opt/noor`, rebuilt `app` + `worker`, and proved that consultative bulk behavior stayed healthy while the first-turn concrete-order bug still persisted
    - round 2 hot-applied the merged `tj-19ol.3.13` engine/order-handoff guard, rebuilt `app` + `worker`, and proved that the concrete-order bug is fixed on canonical runtime without introducing false-positive escalation on the consultative bulk guard-case
  - next realistic step is:
    - take `tj-15m.5.2`
    - then `tj-27v` if media/upload noise still materially drags product replies
