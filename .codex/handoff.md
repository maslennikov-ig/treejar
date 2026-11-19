# Orchestrator Handoff

Updated: 2026-11-19
Current branch: main (live runtime `tj-8e2m` / `tj-uxo1` / `tj-8mtx` / `tj-xnsc` / `tj-y79o` / `tj-cz6j` / `tj-kddn` / `tj-o4qw` / `tj-t6g7` / `tj-k4pc` / `tj-r62i.9` / `tj-32uk`)
Current stage id: tj-r62i (live pilot monitoring + Nikita shift QA audit; `tj-loge`, `tj-mi4g`, `tj-whq5`, `tj-41ra`, `tj-pf5x`, `tj-fswr`, `tj-r62i.1`..`tj-r62i.14`, `tj-32uk`, `tj-r62i.9`, `tj-k4pc`, `tj-t6g7`, `tj-o4qw`, `tj-kddn`, `tj-cz6j`, `tj-y79o`, `tj-xnsc`, `tj-8mtx`, `tj-uxo1`, `tj-8e2m` delivered)
Status: **LIVE PILOT ACTIVE (`2026-11-19 18:10 MSK`)** on `https://noor.starec.ai` (`tj-8e2m`, `anthropic/claude-sonnet-5.5` main model, `prose_guards_mode = "trust_model"`): all branches/stages merged to `main` and deployed; cross-platform Windows/Linux pilot monitor (`scripts/pilot/check_pilot.py`), Nikita shift QA collector (`scripts/pilot/collect_nikita_shift.py`), and timer/SSH installer (`scripts/pilot/setup_windows_timers.py`) shipped alongside [START-WINDOWS.md](../START-WINDOWS.md), native Windows checkout `C:\Users\masle\code\treejar`, and portable transfer bundle `C:\Users\masle\code\.treejar-tools`.

## Nov 19 Pilot & Mirror Audit Fixes (`tj-8e2m`, `tj-uxo1`, `tj-8mtx`, `tj-xnsc`, `tj-y79o`, `tj-cz6j`) — deployed
- **Shipped `tj-8e2m` (`2026-11-19 18:10 MSK`)**: audited 18:00 MSK pilot check (`*6563` Turn 1 chair photo search hijacked into standing desks by `"armrests with adjustable height"` in vision commentary) and fixed the structural class across `src/llm/catalog_planning.py` and `src/llm/engine.py`: (1) assigned each `CatalogConcept` a `CatalogFamily`, required explicit desk/table/workstation/frame/sit-stand context in `height_adjustable_desk.query_re` while blocking bare `"adjustable height"`/`"height-adjustable"` fallback when seating/chair-part nouns (`chair`, `stool`, `armrest`, `headrest`, `lumbar`, `seat`) appear; (2) added `resolve_search_concepts(effective_query, user_query)` so targeted `search_products` calls keep only their own concepts and broad fallback queries inherit only family-compatible user-turn concepts without cross-family or photo-background leakage, passing `active_concepts` and `preferred_families` through `products_need_reranking` and `rank_products_for_request`, with regression tests in `tests/test_search_concept_hybrid_recall.py`.
- **Shipped `tj-uxo1` (`2026-11-19 16:15 MSK`)**: audited 16:00 MSK pilot check (`*7829` false BOQ handoff on 15 out-of-catalog signage/notice-board items, `*3210` storage cabinet search miss) and fixed both classes fundamentally: (1) excluded speculative vision-reader doc-type labels (`bill of quantities`/`boq`/`tender` inside `[The customer sent a photo/document ...]` commentary) from triggering `wholesale_or_bulk_project` below 20 units, summed multi-row `qty` prefixes in `_largest_bulk_quantity`, omitted sub-threshold `(N units)` counts from `wholesale_handoff_from_history` reasons (`src/llm/escalation_policy.py`), and added notice boards/whiteboards/signage boards to non-carried scope in `docs/faq.md` (Q26), `src/llm/prompts.py` (Rule 14), and `src/services/canonical_admin_seed.py`; (2) added `low_storage_cabinet` and `office_cabinet` `CATALOG_CONCEPTS` excluding hanging drawers and workstations, switched `rank_products_for_request` to multi-concept match counting + general stock-first demotion, and added Cyrillic `х` (`\u0445`) to `_DIMENSION_PAIR_RE` (`src/llm/catalog_planning.py`), with regression suite `tests/test_pilot_audit_nov19_1600.py`.
- **Shipped `tj-8mtx` (`2026-11-19 14:15 MSK`)**: audited 14:00 MSK pilot check (`*3918` height-adjustable desk search miss) and fixed hybrid concept/attribute recall, ranking, and specs formatting across `src/llm/catalog_planning.py` (`CATALOG_CONCEPTS`, `requested_catalog_concepts`, `product_matches_concept`, `extract_product_specifications_summary`, concept+in-stock tiering in `rank_products_for_request`/`products_need_reranking`), `src/rag/made_to_order_fallback.py` (`augment_results_with_concept_candidates` SQL lexical/JSON-attributes supplement preserving `PINNED_RETRIEVAL_CONTRACT_SHA`), `src/llm/engine.py` (`Category:` + `Specifications:` output and concept augmentation in `search_products`), and `src/llm/verified_answers.py` (`_NEARBY_EQUIVALENTS` for sit-stand/height-adjustable terminology), with regression suite `tests/test_search_concept_hybrid_recall.py`.
- **Shipped `tj-xnsc` (`2026-11-19 10:55 MSK`)**: wired Julia's (`@youpyoupp`, `msg 882` / event `897`, `docs/client-answers/noor-pilot-final-check-2026-11/custom-moq-and-marketplaces-2026-11-19.md`) approved custom-made MOQ / no-1-prototype and marketplace routing policies across `docs/faq.md` (Q7), `src/services/canonical_admin_seed.py`, `src/llm/prompts.py` (Rule 13 & Escalation Guidelines), `src/llm/escalation_policy.py` (`_SINGLE_UNIT_PROTOTYPE_RE` / `is_single_unit_prototype_request` + marketplace order/invoice detection routing to Ali), and `src/dialogue/decision_state.py` (binding `[DECISION STATE]` directive for single-unit/prototype requests so Noor clearly declines 1-prototype fabrication and offers ready-stock catalog alternatives), plus dispatched combined follow-up (requesting Ali's Telegram `chat_id` + OpenRouter `$6.92/$20.00` top-up reminder) to `AiDevTeam/Виктор` (`msg 883`, wait `0521d59c`).
- **Shipped `tj-y79o` (`2026-11-19 10:10 MSK`)**: audited Nikita Nov 18 even-day shift (17 `EVEN_SCHEDULED` chats, 120 client msgs, 84 echo msgs) + 7 Nov 17 `ODD_LEAKED_ROUTER_BLACKOUT` chats and closed 4 mirror gaps before QA report: (1) surfaced `non_sales_notice` across turns in `decision_state_directives` (`src/dialogue/decision_state.py`), suppressed `permitted_asks` on flagged non-sales threads (`src/llm/message_processor.py`), and added factory catalog PDF/sample pitch guidance in Rule 16 (`src/llm/prompts.py`, `*5256`); (2) added Jebel Ali mainland / outside-JAFZA-Freezone warehouse policy (`docs/faq.md` Q8, `src/llm/communication_policy.py`, `src/services/canonical_admin_seed.py`) and `freezone`/`jafza`/`warehouse location` triggers (`src/llm/verified_answers.py`, `src/llm/company_faq.py`, `*2482`); (3) escalated failed phone call attempts (`trying to call`, `nobody answering`, `can't reach by phone`) as `HUMAN_REQUESTED` (`src/llm/escalation_policy.py`) and generalized GCC export destination phrasing in B2B handoff (`src/llm/escalation_tools.py`, `*3939`); (4) clarified general office supplies/stationery consumables and residential villa/home furniture boundaries in FAQ Q26, Rule 14, and canonical seed (`*0234`, `*2203`), with regression suite `tests/test_mirror_audit_nov19.py`.
- **Shipped `tj-cz6j` (`2026-11-19 08:10 MSK`)**: audited morning Nov 19 live dialogues (`*5949`, `*1201`, `*9005`) and fixed two structural defects: (1) surfaced prior non-pausing team notifications (`manager_sourcing_leads_notified`, `team_followup_notice`, `team_followup_quote_notice`) in `decision_state_directives` (`src/dialogue/decision_state.py`) and `check_order_status` (`src/llm/engine.py`) so Noor never retracts or denies an already-sent `external_order_support` / team notification on subsequent turns (`*1201`); (2) expanded `_CUSTOM_MADE_TO_ORDER_RE` (`src/llm/escalation_policy.py`) to match custom seating (`chair(s)`, `stool(s)`, `sofa(s)`, `seating`, `bench(es)`, `pod(s)`, `booth(s)`, Arabic `تفصيل كرسي/كراسي/كنب/مقاعد`) and custom `prototype` requests while keeping `"custom colour"` autonomous (`*9005`), plus sent policy clarification questions to `AiDevTeam/Виктор` on 1-piece custom prototypes and Amazon.ae order/invoice handling (waiting reply via `client-communications`).

## Windows Native Cutover & Nov 16/17 Pilot Hardening (`tj-kddn`, `tj-o4qw`) — deployed
- **Windows Native & Laptop Cutover (`2026-11-18`)**: audited WSL repo state (0 unmerged branches, 0 open PRs, 0 stashes; `.worktrees/model-bakeoff-20261109` evaluation artifacts preserved; 1.9 GB local caches/venv cleaned), added cross-platform `scripts/pilot/{check_pilot.py,collect_nikita_shift.py,setup_windows_timers.py}` + `START-WINDOWS.md`, provisioned `C:\Users\masle\code\treejar` + `C:\Users\masle\code\.treejar-tools` + `C:\Users\masle\.ssh\treejar_vps` + Codex automations (`treejar-noor-pilot-monitor`, `treejar-nikita-shift-report`).
- **Shipped `tj-kddn` (`2026-11-17 21:50 MSK`)**: audited Nikita Nov 16 even-day shift (20 dialogues, 74 client msgs, 60 echo msgs) and Nov 15/17 leaked router-blackout chats (26 dialogues + sticky `*2157`), resolving 5 mirror gaps before QA report: (1) refined `_follows_a_model_name` (`src/llm/escalation_policy.py`) so explicit piece-count units (`pcs?`, `pieces`, `units`, `nos`) and uppercase customer verbs/nouns (`"I NEED 100 PCS"`, `"WE NEED 50 CHAIRS"`, `"exact model 100pcs"` in `*2280`) are never suppressed as catalog model series names while preserving `NOVO 2400 tables` / `RAYA 1600 desk` protection; (2) added singular `pc` (`pcs?`) to `_BULK_ITEM_EN` (`*2482` `"Around 40 pc"`); (3) expanded `_WHOLESALE_PRICING_RE` for `whole sell`, `whole seller`, and `whole sale` (`*2482`, `*6508`); (4) expanded `_CUSTOM_MADE_TO_ORDER_RE` to cover custom shape/modifier descriptors (`*3375` `"custom triangle table"`); (5) updated FAQ Q26 (`docs/faq.md`), Rule 14 (`src/llm/prompts.py`), and `_POLICY_ARTICLES` (`src/services/canonical_admin_seed.py`) to clarify that Treejar does not supply residential beds / double beds / bedroom furniture (`*2039`), with regression suite `tests/test_mirror_audit_nov16.py`.
- **Shipped `tj-o4qw` (`2026-11-17 18:10 MSK`)**: audited Nov 17 `16:29–17:08 MSK` resumed router dialogues (`*5268`, `*9443`) and resolved two root-cause `search_products` ranking defects: (1) updated `request_wants_components` (`src/llm/catalog_planning.py`) to ignore descriptive prepositional frame/base/leg modifiers (`with ... frame/base/legs`) and top+desk pairings (`white top desk ... sled frame`) and added a `limit=30` fallback in `search_products` (`src/llm/engine.py`) when all top-9 candidates are frame-only kits (`*9443`); (2) added qualitative budget detection (`wants_economical_options`), colour-sibling deduplication (`_product_diversity_key`), wider candidate fetch (`limit=15+`) for economical requests without `max_price`, and distinct budget-tier guidance in `STAGE_RULES["solution"]` (`src/llm/prompts.py`) so economical requests (`*5268`) lead with distinct affordable models (`CH 620`, `CH 616 NEW`, `CH 500 M`) instead of two colours of an AED 1,440–1,600 luxury chair (`CH 970`).

## Nov 17 Router Window Audit & `*8054` Structural Fixes (`tj-t6g7`) — deployed
- **Shipped `tj-t6g7` (`2026-11-17 15:30 MSK`)**: audited today's temporary router return (`11:21:03`–`13:27:48 MSK`, `93` HTTP 200 webhooks, chats `*2874`, `*3857`, `*4876`, `*8054`) and resolved 3 structural issues uncovered in `*8054` (`Joan / Peace City Contracting`): (1) added `<item>: <count>` table quantity support (`_ITEM_COLON_QUANTITY_RE` + `benches`/`stools`), model-recorded `recorded_wholesale_quantity(conversation_metadata)` from `dialogue_state.slots.selected_items` (`src/llm/escalation_policy.py`, `src/llm/message_processor.py`), and a `20+` unit wholesale stop in `_create_quotation` (`src/llm/engine.py`) so bulk/table tenders route immediately to a B2B sales manager without entering retail PDF creation; (2) bridged `Product.zoho_item_id` -> live Zoho SKU via `_resolve_zoho_sku_map_by_item_id` (`src/llm/catalog_planning.py`, `src/llm/engine.py`) so warehouse-renamed SKUs (`STEL SSC - 10/15/20`, `STEL SSP - 25` -> `STEL SSL-*`) resolve cleanly in both `search_products` and `create_quotation` instead of raising `InventoryReadUnavailable`; (3) updated `retry_pending_quotation` (`src/services/quotation_retry.py`), `manual_takeover` (`src/services/chat.py`), and `notify_manager_escalation` (`src/integrations/notifications/escalation.py`) to clear `pending_quotation` and stop background retries whenever `should_pause_bot_for_escalation` is active, plus cleared stale `pending_quotation` on prod conversation `a2a045ff-9ae3-49c9-b27b-8d8e0dada63a`.

## Stale `manual_takeover` Follow-up Alert & Rule 19 Un-Hardcoding (`tj-k4pc`) + Nov 14 Mirror Hardening (`tj-r62i.9`) — deployed
- **Shipped `tj-k4pc` (`2026-11-15 11:25 MSK`)**: cross-checked every historical Nikita & pilot report (`Oct 22`, `Nov 1`, `Nov 9–14`) against live deployed code and closed the final two gaps from the Nov 14 shift report: (1) added `_notify_stale_manual_takeover_followup` in `src/services/chat.py` (plus `stale_manual_takeover_unanswered_gt_4h` in `check_pilot.sh` `[3B]`) so when a customer writes back in a `manual_takeover` chat after `>= 2h` without a manager message (scenario `*0247` `"Good Evening / No one came back to me"`), Noor stays 100% silent in WhatsApp while dispatching a rate-limited (30m cooldown) Telegram alert to sales managers; (2) replaced hardcoded `CH 300 beige` stock in Rule 19 (`src/llm/prompts.py`) with live `search_products`/`get_stock` verification and added photo visible-colour + budget/mid/premium tier matching in `CUSTOMER ATTACHMENTS` (`*9860`), plus synced all 32/32 canonical KB rows (`customized=0`) on prod.
- **Shipped `tj-r62i.9` (`2026-11-15 10:20 MSK`)**: audited Nikita Nov 14 WhatsApp shift (16 dialogues, 58 client msgs, 56 echo msgs) and Nov 13/15 odd router blackout dialogues, resolved 3 mirror gaps before QA report: (1) added FAQ Q28 (`docs/faq.md`) clarifying Treejar supplies commercial task, executive, and visitor chairs but does not stock classroom/training chairs with attached flip-up writing tablet arms in ready stock (suggesting visitor chairs + training tables, or manager quote for 20+ bulk project orders); (2) added Rule 19 to `BASE_SYSTEM_PROMPT` (`src/llm/prompts.py`) covering 3D/4D chair ergonomic adjustment terminology (armrest height/depth/pivot, lumbar) vs video confusion, upholstery 0-ready-stock grounding, and tablet-arm guidance; (3) updated canonical KB seed test in `tests/test_admin_canonical_seed.py` (28 FAQ questions in docs/faq.md, 25 active) and added regression suite `tests/test_mirror_audit_nov14.py`.

## Monitoring Watchdog, Startup KB/Prompt Sync & Nov 13–15 Mirror Hardening (`tj-32uk`) — deployed
- **Shipped `tj-32uk` (`2026-11-15 08:40 MSK`)**: full production, monitoring, and Nov 11–15 live shadow traffic audit uncovered external odd-day router blackout on `audit.treejartrading.ae` since `2026-11-11 16:00:27 UTC` (leaking 23 odd-day chats on Nov 13 + sticky Noor chat `*2157` + morning Nov 15 chats `*6288`/`*4333` to Nikita while `check_pilot.sh` emitted silent green ticks) plus 4 unsynced canonical FAQ articles in prod `knowledge_base`: (1) added automatic `sync_canonical_knowledge_base(db, embedding_engine, mode="safe")` on ARQ worker startup (`src/worker.py`) and replaced literal default caching in `get_system_prompt_component` (`src/llm/prompts.py`) with `_PROMPT_CODE_DEFAULT_SENTINEL` so code prompt & FAQ updates take effect immediately on deploy without 1-hour Redis cache staleness or manual sync steps; (2) added FAQ Q27 (`docs/faq.md`, no short-term/event furniture rental), expanded FAQ Q26 & Rule 14 (`src/llm/prompts.py`, paper shredders/office electronics & plastic dining chairs), added Rule 18 (Skyland China/selected European origin accuracy & manufacturer TDS PDF datasheet guidance), and fixed `_POLICY_ARTICLES` `"Product categories Treejar supplies"` (`src/services/canonical_admin_seed.py`, steel lockers `STEL SSL-1`–`STEL SSL-4`, no safes or rental); (3) upgraded `check_pilot.sh`, `collect_nikita_shift.sh`, and both sidecars with `[1B]` canonical KB drift check, `[2B]` odd-day router blackout & sticky-lead bypass watchdogs, `EVEN_SCHEDULED` vs `ODD_LEAKED_ROUTER_BLACKOUT` shift buckets, and graceful `aidevteam.ru` `egress_quota_exceeded` fallback.

## Earlier Nov 10–13 Mirror Audit & Pilot Hardening (`tj-r62i.5`..`tj-r62i.14`, `tj-dqdv`, `tj-x8d8`, `tj-97kt`, `tj-fswr`, `tj-whq5`, `tj-41ra`, `tj-pf5x`) — deployed
- **Shipped `tj-r62i.14` / `tj-dqdv` (`2026-11-13`) & `tj-r62i.11`..`tj-r62i.13` / `tj-x8d8` (`2026-11-11`)**: added FAQ Q24–Q26 and Rules 14/17 (`CH 240 V`/`CH 420 V` chairs without wheels, petty cash boxes/safes/stationery exclusion, competitor price comparison in `STAGE_RULES["solution"]`, Hindi/Urdu/EN/AR `_VOICE_OR_ACCESSIBILITY_RE` human escalation); added `apply_made_to_order_catalog_fallback` (`src/rag/made_to_order_fallback.py`, preserving `PINNED_RETRIEVAL_CONTRACT_SHA`), stdlib `.xlsx`/`.docx`/`.csv` extraction (`extract_local_document_text` in `src/integrations/vision/media_reader.py`), `_reply_may_be_superseded` escalation guard, per-conversation `escalation_repeat:{conv.id}` suppression, and `_COMPOUND_SET_QUANTITY_RE` + `or`/`/` alternative quantity handling.
- **Shipped `tj-r62i.3`..`tj-r62i.9` (`2026-11-09..11`) & `tj-fswr`/`tj-whq5`/`tj-41ra`/`tj-pf5x`**: switched `system_configs.openrouter_model_main` to `"anthropic/claude-sonnet-5.5"` with `prose_guards_mode = "trust_model"` (`ReplyPolicyState.trust_model_prose`), static system `cache_control` breakpoints, and semantic `report_non_sales_inquiry` tool + FAQ Q21/Q22; enforced Dubai working hours (`Mon–Sat 09:00–18:00 Asia/Dubai`) for 3-min Turn-1 manager grace + `_manager_takeover_active()` mid-turn `isEcho` abort + Wazzup `missing_call` auto-reply filter; wired Julia's Jebel Ali showroom/warehouse address, map pin, free self-pickup, and delivery/assembly tariffs (`FAQ Q8–Q10`), Zoho CRM Contact + `New Lead` Deal auto-sync on `create_quotation`, and `shadow_webhook_events` passive observer.

## Epic tj-loge & Follow-up `tj-mi4g` (2026-11-07..08) & Live Pilot Fixes (`dfdf534`, `7055094`, `c31bd3e`) — deployed
- Live pilot enabled 2026-11-05 (`tj-r62i`, Treejar WhatsApp `+971523209235`, odd Moscow dates -> Noor via client router `audit.treejartrading.ae`). Shipped `dfdf534` (CI `42056978288`: deterministic 20+ unit handoff incl. `Qty.350Nos`, cross-turn bulk carry, manager `isEcho` delivered/read takeover, paused-chat follow-up guard), `tj-loge` (`7055094`, CI `42399667366`: `anthropic/claude-haiku-5.5` vision/PDF reader, `15s` sliding quiet window, recruitment/supplier alert, opening search guard + frame-only demotion), and `tj-mi4g` (`c31bd3e`, CI `42455766189`: `_product_model_reference` + per-price-bucket sibling disambiguation, `exact_media_product_keys` follow-up query, CRM `Name`/`Full_Name` lookup, standalone spare hardware guard).
- Recurring 2h monitor (`08:00–22:00` MSK odd dates, `~/.gemini/config/sidecars/treejar-noor-pilot-monitor/`) checks nginx router traffic, Postgres activity, `[3B]` 5-way stuck/hanging conversation watchdog + `[3C]` Redis inbound queue/quarantine watchdog, full dialogue QA, app/worker logs, health, and OpenRouter credit (`$11.2751 / $20.00` remaining). Standing Owner Authority (2026-11-08 & 2026-11-09): (1) fix all defects **fundamentally** from durable workflow/conversation state and deploy via `main` CI; (2) **zero-hang prod remediation** — immediately push/escalate to managers, sync missing Zoho CRM Contact/Deal, or update Postgres/queue state; (3) **autonomous team clarification questions** in `AiDevTeam/Виктор` with dual-runtime `codex`/`antigravity` reply wait, while formal reports (10:00 MSK Nikita QA report) and commercial commitments still require Igor's explicit confirmation.

## Epic tj-id6m (2026-11-01..02) & Admin Stages `tj-fsfx`, `tj-myx7`, `tj-p82s`, `tj-4kba`, `tj-j3zg`, `tj-lk87`, `tj-ierv`, `tj-i2b1` — deployed
- Full audit + 17 closed remediation slices (`tj-id6m.1`..`tj-id6m.16`, `tj-id6m.18`) merged to `main` (`d7eb8ea`, `93013c9`, `580116a`, `e5fb835`) and deployed to `https://noor.starec.ai` (`docs/reports/audit-2026-11-01/README.md`); permanent `ZOHO_CRM_REFRESH_TOKEN` reissued (`tj-tjum` closed) and VPS `OPENROUTER_API_KEY` cap raised to `$20.00` (`tj-8awv` closed).
- Admin controls/onboarding/portal guide v3 (`f2d040d`, `.codex/stages/tj-fsfx/summary.md`, `.codex/stages/tj-myx7/summary.md`, `.codex/stages/tj-p82s/summary.md`) and earlier Admin/tester stages (`.codex/stages/tj-4kba/summary.md`, `.codex/stages/tj-j3zg/summary.md`, `.codex/stages/tj-lk87/summary.md`, `.codex/stages/tj-ierv/summary.md`, `tj-i2b1`) live on `main`.
- Wazzup webhook protection (`tj-vqcc`, `docs/ops/wazzup-webhook-guard.md`, `docs/reports/2026-10-13-wazzup-webhook-guard-delivery.md`) deployed and active; `tj-zc6k` provider-side writer action documented in `docs/ops/wazzup-callback-owner-action-20261014.md`.

Updated: 2026-10-04
Current branch: codex/tj-uvld-stock-sync
Current stage id: tj-uvld-stock-sync
Status: full release verified;4458 passed,20 gated skips; Ruff/mypy/process passed.
Delivery: owner authorized Push, Merge, Deploy2026-10-03; delivery completed, CI37130777663 passed.

## Current work

- tj-199k delivered: helpers Luna, repair/QA Terra; live 0f17419 / CI 41232988824 (4862 passed,27 skipped + pgvector1). Main chat subsequently upgraded from `openai/gpt-6.1-sol` to `anthropic/claude-sonnet-5.5` in `tj-r62i.4` (`3336667`, CI `42626065502`) with static system `cache_control` breakpoints; voice/search, disabled/channel/audit gates, FAST ENV, and 3 QA model fields preserved. Report/rollback: docs/reports/2026-10-31-noor-helper-model-migration.md.
- tj-3jcn historical baseline: DB-backed chat ran openai/gpt-6.1-sol / medium (6df11eb, CI 41229254700) until `tj-r62i.4` switched `system_configs.openrouter_model_main` to `"anthropic/claude-sonnet-5.5"` on 2026-11-09 13:34:51 UTC. Evidence: docs/reports/2026-10-31-noor-pilot-and-model-readiness.md.
- Client pilot choices v2 (`docs/client-answers/noor-nikita-pilot-2026-10/responses-2026-11-02.{json,md}`), final confirmations (`docs/client-answers/noor-pilot-final-check-2026-11/responses-2026-11-03.{json,md}`, `docs/client-answers/2026-11-02-nikita-noor-routing-spec/responses-2026-11-03.{json,md}`), and Julia's delivery/assembly tariff sheet (`docs/client-answers/noor-pilot-final-check-2026-11/delivery-assembly-tariffs-2026-11-04.md`) wired (`tj-z3hw`, `tj-r62i`): odd/even days (`Europe/Moscow` `UTC+3`, Nikita = even, Noor = odd, sticky per dialogue), new clients only, 14 days, `crm_write_scope` = Contact + Deal (`New Lead`) + Draft Quote, and `ops/live-pilot-worker.enabled` preservation in `scripts/vps-deploy.sh`.
- Beads tj-uvld owns AC01–AC12 and remains in_progress until provider coverage,
  delta activation and real 24h optimized measurement are accepted.
- Worktree: /home/me/code/treejar/.worktrees/tj-uvld-stock-sync.
- Base: main 36c86137a51d2e6485db92c28ec057fe26f03339; prepared docs and
  tj-4kot cooldown07591b8 reused by cherry-pick. Primary dirty work preserved.
- Installed: gated 600s delta + daily03:17UTC full, owned lock/CAS generations,
  48h retention with1h customer ceiling, selected-SKU fresh quotation checks,
  shared HTTP counters and read concurrency/cooldown.
- Owner decision: stock2 vs agreed5 stops quotation, states only2 available,
  and awaits a new customer decision. Consent becomes deferred; unchanged
  shortage state cannot trigger another automatic/background creation.
- Source observation and successful dataset coverage are distinct. Multi-page
  delta requires two identical complete reads; changed pages abort publication.
  This safeguard does not establish provider paging/operation completeness.
- Stock source unchanged in live app+workera72da15 after authorized tester
  delivery. Stock-stage4451/27CI and4458/20local are historical; current full
  canonicalCI4712/27passed. Delta gate remains off.
- .env/safety fingerprints unchanged; DB/Redis/nginx containers retained.
- New v2/legacy:2557 rows,48h TTL. UTC[14:50:52,14:53:10):
 13GET/13HTTP200,1successful full cycle; not optimized24h evidence.
- Delivery receipt:docs/reports/2026-10-03-zoho-stock-sync-delivery.md.
- Latest report: docs/reports/2026-10-04-zoho-stock-sync-optimization.md.
- Implementation report: docs/reports/2026-10-03-zoho-stock-sync-optimization.md.
- Stage: .codex/stages/tj-uvld-stock-sync/summary.md.

## Provider evidence and eligibility

- Owner2026-10-04: working organization only, no warehouse mutations.
- Fresh live readback24checks passed, runtime25a8c080 unchanged.
  UTC[03Oct14:50:52,04Oct06:00:00):2019 attempts,2015HTTP200,4HTTP429/minute,
 155successful full cycles/4failed/23local cooldown skips;15h9m8s, not optimized24h.
- Read-only history probe04Oct:5GET,4HTTP200+1HTTP401 at inventoryadjustments;
 stopped without OAuth refresh/retry/access changes.9 returned item timestamps
 precede last24h query boundary; filter/field semantics unproved, no causal
 missed-operation inference. Coverage gate stays closed. Receipts:
 docs/research/2026-10-04-zoho-stock/.

- Access follow-up10:06UTC: one cached-token GET returned401/code57
  (not_authorized); stopped, no refresh/retry. Scope history suggests missing
  history READ grants; role/grant distinction is not proven by cached TTL.
- Read-only access resolved without owner console action: existing EU Self
  Client client_credentials produced <=1h tokens for six exact READ scopes;
  no refresh tokens, production token replacement, env/Redis or warehouse write.
  10:59/11:03/11:19UTC:3OAuthPOST200 +17InventoryGET200, no retries.
  Validated adjustment/receive/return/transfer history samples available.
  Packages response shape remains unverified, not inferred empty.
  Executed source hashes and safe receipts: research README above.
- Applied quantity adjustment04Oct06:12UTC contains selected line +10;
  matched current item stock24, item timestamp16Sep12:46UTC. No observed
  old quantity or complete delta membership; this does not certify coverage.
  Current docs do not guarantee stock-only changes advance item timestamps.
 21offline Self Client guards passed; old17grant/6audit checks retained.
  Archived localhost server-based helper is not a client/Viktor instruction.
- Bounded natural quantity observer started04Oct11:48:19UTC, deadline05Oct
 11:48:19UTC (14:48MSK). Initial full11:46UTC:2397 numeric-stock rows;
 unknown quantities are excluded, never zero. Snapshot Redis GET only until
 first quantity change; then <=16 cached-token InventoryGET, no OAuth/retry/
 writes. Stops after one comparison or24h. Startup/source-bound receipt and
13offline observer guards: research snapshot-watch-* files. Local SSHPID71170;
 private runtime directory is in snapshot-watch-launch.json. Observer output
 still needs root reading; no automatic chat callback or delta activation.

- 2026-10-03 read-only probes, bulk/paging limits and catalog mapping:
  docs/research/2026-10-03-zoho-stock/ (delta activation stays off).

## Operating boundary

- Livea72da15, TEST_CHANNEL_RESTORE_MODE=true; protected app/worker safety
  fingerprints equal predeploy. Approved0665 sender/allowlist and Telegram
  phone isolation unchanged. Owner-authorized Wazzup guard flag is now true;
  guard repeatedly restores callback; provider subscription flags unchanged.
- Current owner authority covers tj-uvld push/merge/deploy with delta gate off.
- Warehouse mutations are explicitly excluded by current owner instruction.
  Requested diagnostic access uses existing EU Self Client, six exact READ
  scopes, <=1h access tokens only in app memory. Existing shared Inventory/
  CRM client configuration, refresh/cached tokens and production env preserved.
  Permanent reauthorization/revocation, permissions changes and real messages
  still require separate approval.
  Stock investigation used no paid model reader/calls.
- Website products.is_active, catalog prices and embeddings remain owned by
  their existing sync; stock state never writes those fields.

## Recovery

- Disable ZOHO_STOCK_INCREMENTAL_ENABLED and clear the coverage evidence in
  app+worker environment, recreate only app+worker under approved delivery.
  Proven five-minute full mode remains available; this restores higher API use.
- Keep v2 state and the last-full v1 snapshot; do not flush Redis/ARQ/customer
  data. Previous binary reads original v1 as_of with its one-hour ceiling.
- Rollback/deployment commands and measurement packet are in the current report.
- Preserve unrelated environment, live DB, queued/held messages and test0665.

## Explicit defers

- tj-id6m.17 (deferred by owner 2026-11-02 on closing `tj-id6m`): 10 optional product/ops choices parked unless requested (`docs/reports/audit-2026-11-01/README.md`: LLM reasoning effort/retries, in-flight supersession cancel, duplicate current-turn prompt message, CRM `paused`/`closed` reply behavior, manual `escalation_status` editing, `bot_enabled` fail-open vs fail-closed default + UI kill-switch, payment reminder UI/`manual` mode, public `/client-self-test/submit` retirement/rate-limit, KB `language` filter & `target_only` definition, one-off GitHub workflows).
- tj-r62i / tj-z3hw: Live pilot active across odd Moscow dates since `2026-11-05` (`dfdf534`, `7055094`, `c31bd3e`, `da3248b`, `8e47d3a` live; `tj-loge`, `tj-mi4g`, `tj-whq5`, `tj-41ra` closed); client router (`audit.treejartrading.ae`) resumed odd-date forwarding + manager `isEcho` events on `2026-11-09 02:55 UTC` (`14` days pilot window ongoing).

- tj-i2b1: earlier527fe1f saved budget/hold but failed mixed matching/selection.
  Corrected a72da15live/CI4712passed; fresh2/3unit retained/held proof pending.
- tj-zc6k: stop recurring writer via account owner/provider; no audit SSH or
  Wazzup admin access available. Enabled guard recovers but cannot revoke keys.
- tj-uvld: AC02 provider stock/lifecycle coverage and paging stability need
  read-only causal before/after observations and complete delta membership.
  History access is now available; no owner console step is pending. Owner
  forbids warehouse mutations and no test organization is available.
- tj-uvld: provider-gated delta activation and real24h optimized counters are
  still pending; code delivered, no claim of optimized production savings yet.
- tj-4kot: outside account consumer (~50requests/min) incident remains open;
  cooldown fix delivered in25a8c08; external load resolution remains unproved.
- tj-535gclosed: liveREADONLYcollector07:15UTC returns45stale escalations,
  0dependency failures. Monitoring remains disabled; no old records changed.
- Zoho quotation live E2E remains unverified; no real messages were sent here.
- tj-1baw latency remains separate; tj-bgwu fixed in `codex/project-consistency-20261013`.
- Paid second reader stays off; reader-gap drift tracked in tj-4q79.
- tj-ierv: KB lacks owner facts for returns window, warranty term, and payment methods; articles defer them to the manager (delivery/assembly tariffs resolved 2026-11-04 in `tj-z3hw`; showroom address, working hours, map pin, and free Jebel Ali warehouse self-pickup resolved 2026-11-09 in `tj-r62i.3`).

## Next recommended

Next stage id: tj-uvld-stock-sync
Recommended action: continue the same boundary after approved provider evidence.

Code delivery completed. Owner requires working-org read-only continuation.
History access live-verified through temporary read-only Self Client grants.
Next needs sufficient redacted before/after operation observations and complete
delta membership, without introducing warehouse test operations.
Read-only access alone does not establish otherwise unobserved coverage. Resolve
modified-since/filter timestamp semantics, prove AC02, then authorize delta
activation and collect24h UTC[start,end) counters. Do not close tj-uvld early.

## Starter prompt for next orchestrator

Use $orchestrator-stage for the same authorized tj-uvld boundary.
Read docs/prompts/2026-10-03-zoho-stock-sync-optimization.md and the current
report/Beads notes to continue. Primary root checkout is clean on `main`.

docs-reviewed: updated - audit reports (`docs/reports/audit-2026-11-01/`) and handoff updated; documentation-decision: dependency-lockfile upgrades preserve public contracts while internal PydanticAI/FastAPI adaptations are covered by strict mypy and full suite.
graph-reviewed: no-change-needed - no enabled task-owned graph; ordinary code navigation used.
