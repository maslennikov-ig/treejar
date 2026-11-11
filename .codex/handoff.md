# Orchestrator Handoff

Updated: 2026-11-11
Current branch: main (live runtime `tj-r62i.7` + handoff sync)
Current stage id: tj-r62i (live pilot monitoring + Nikita shift QA audit; `tj-loge`, `tj-mi4g`, `tj-whq5`, `tj-41ra`, `tj-pf5x`, `tj-fswr`, `tj-r62i.1`..`tj-r62i.7` delivered)
Status: **LIVE PILOT ACTIVE (`2026-11-11 08:40 MSK`)** on `https://noor.starec.ai` (`tj-r62i.7`, `anthropic/claude-sonnet-5.5` main model): client router (`audit.treejartrading.ae`, `"node"`) automatically resumed odd-day webhook forwarding after `00:00 UTC` (`03:00 MSK`), and `tj-r62i.7` fixes the 2 opening/supplier-pitch guard edge cases observed in the first overnight chats (`*4285` and `*4919`). Antigravity wait `96183f22-a956-58fb-8e7a-3bd861dd8177` remains `partial` awaiting Q1 (payment methods) & Q3 (`B2C-...` pickup readiness).

## Pre-Flight Audit & Morning Shift Hardening (`tj-r62i.6`..`tj-r62i.7`), Smart Working-Hours Manager Grace (`tj-r62i.5`), Model Upgrade (`tj-r62i.4`), & Bugfixes (`tj-whq5`, `tj-41ra`, `tj-pf5x`, `tj-fswr`, `tj-r62i.1`..`tj-r62i.3`) — deployed
- **Shipped `tj-r62i.7` & Morning Check Remediations (`2026-11-11 08:45 MSK`)**: audited first overnight odd-day chats (`*4285`, `*4919`) on `2026-11-11`: (1) extended `_strip_generic_english_opening()` in `src/llm/opening_guard.py` to strip `Hello and welcome! 🌷` completely so `and welcome!` never remains as an orphan fragment after the canonical opening (`*4285`); (2) expanded `_SUPPLIER_PITCH_RE` in `src/llm/non_sales_intent.py` (`we are a <1-3 words> manufacturer...`, `considering a new supplier`, `purchasing manager`), suppressed sales asks (`permitted_asks = frozenset()`) in `src/llm/message_processor.py` on non-sales turns, exempted supplier/recruitment boundary replies from `guard_premature_quote_detail_collection` in `src/llm/response_policy.py`, added `Best regards,\n<Name>` extraction to `NATURAL_NAME_PATTERNS` in `src/llm/engine.py`, and dispatched the non-sales escalation notice for `*4919` on prod.
- **Shipped `tj-r62i.6` & Pre-Flight Remediations (`2026-11-10 21:20 MSK`)**: audited all live `shadow_webhook_events` and production state ahead of `2026-11-11 00:00 MSK`: (1) filtered Wazzup's built-in `missing_call` event and auto-reply (`"Please note that you can only send messages in this chat..."`, `is_wazzup_system_auto_reply` in `src/services/inbound_batch.py`, `src/api/v1/webhook.py`, `src/services/chat.py`) so missed WhatsApp calls never falsely trigger `manual_takeover`; (2) extended `_manager_takeover_active()` in `src/services/chat.py` to cross-check `ShadowWebhookEvent` for any non-Noor `is_echo=True` message (`status IN ('sent', 'delivered', 'read')`), preventing Noor from ever speaking in chats where a manager or Nikita replied during an off-window or before `"node"` forwarded the echo; (3) expanded `_SUPPLIER_PITCH_RE` in `src/llm/non_sales_intent.py` (`furniture supply from...`); (4) remediated sticky odd-day chat `*0068` (`b452a388-1eea-4811-857b-1ec352135864`, taken over by manager on `2026-11-10`) to `manual_takeover` and deleted orphaned Redis key `wazzup_msgs:ib1_5eeb27eba1a193e9c64acdec`.
- **Shipped `tj-r62i.5` (`9908be7`) & Re-enabled Noor (`2026-11-10 20:30 MSK`)**: following our forensic audit of `2026-11-09` (where sales managers `Sreeja` & `Sweeton` manually claimed 14 of 18 leads within 20–90s while Wazzup delayed `isEcho=True` webhooks by 15–55s) and Julia's confirmation (`@youpyoupp`, `msg 428`: `"давайте этот вариант"` in reply to `msg 390` Option 1) + Igor's authorization: (1) enforced Treejar Dubai working hours (`Mon–Sat 09:00–18:00 Asia/Dubai`, `is_treejar_working_hours` in `src/services/inbound_batch.py`) for `first_turn_manager_grace_seconds = 180` (`3 min` Turn-1 grace during working hours; fast `5s` defer + `15s` quiet window in evenings `18:00–09:00 GST` and all day Sunday); (2) added `_manager_takeover_active()` in `src/services/chat.py` checking both Redis `inbound_queue_key` (`has_queued_manager_message`) and DB `Conversation.escalation_status` before LLM generation, on LLM timeout, right before persisting/sending the bot reply, and before deferred product media so any delayed manager `isEcho` arriving mid-generation aborts outbound sends immediately; (3) restored `/opt/noor/ops/live-pilot-worker.enabled` and `system_configs.bot_enabled = true`.
- Shipped `tj-r62i.4` (`3336667`, CI `42626065502`): after a blind 3-model `$2/$10` sales & empathy bake-off (`anthropic/claude-sonnet-5.5` `#1` at `9.0/10` quality & `13.0s` mean turn latency vs `openai/gpt-6.1-sol` `8.1/10` & `23.77s` and `google/gemini-4-argon` `8.25/10` & `15.72s`), split Anthropic OpenRouter `role="system"` prompts in `OpenRouterTelemetryChatModel` (`src/llm/safety.py`) into static `cache_control: {"type": "ephemeral"}` prefix blocks before dynamic `[HISTORICAL WORKFLOW DATA]`, restored PydanticAI 1.x `RequestUsage.cache_read_tokens` / `cache_write_tokens` extraction, and switched `system_configs.openrouter_model_main` to `"anthropic/claude-sonnet-5.5"`.
- Shipped `tj-r62i.3` (`7f0dfa6` + `20fc0fb`, CI `42625196256`): expanded `response_asks_customer_name()` in `src/llm/closed_question_guard.py` so modal/natural phrasings never trigger duplicate `, and how should I address you?` appends in `apply_opening_guard`; wired Julia's (`msg 383`, `docs/client-answers/noor-pilot-final-check-2026-11/showroom-pickup-2026-11-09.md`) approved showroom/warehouse policy (`Storall Building, St. 58, Community 599, Jebel Ali Industrial Area 2, Dubai`, `Mon–Sat 9:00–18:00`, `Sun closed`, Google Maps pin rule, and free Jebel Ali warehouse self-pickup with no minimum order amount) across `docs/faq.md` (Q8 & Q9), `src/llm/company_faq.py`, `src/llm/verified_answers.py`, `src/llm/communication_policy.py`, and `src/services/canonical_admin_seed.py` (+ synced prod `knowledge_base` rows).
- Shipped `tj-fswr` (`7baa2a0`), `tj-r62i.1` (`a81c150`), & `tj-r62i.2` (`985808e`): drove multi-turn delivery/assembly FAQ & tariff grounding (`AED 400` Abu Dhabi) from full `recent_history` + durable `quote_workflow` state (`has_quote_delivery_context` in `company_faq.py`), added EN/AR direct team-outreach + dedicated `ORDER_CONFIRMATION` `quotation_followup` alert whenever `create_quotation` runs with open/unconfirmed closing terms (`message_processor.py`), auto-synced Zoho CRM Contact + `New Lead` Deal on `create_quotation` (`engine.py`), and remediated pre-fix prod chats `*6551` and `*6040`.
- Shipped `tj-whq5` (`da3248b`, CI `42573039511`: `has_manager_message` transitions `pending`/`in_progress` chats to `manual_takeover`), `tj-41ra` (`8e47d3a`, CI `42573735618`: non-pausing manager Escalation + Telegram alert on external website orders `B2C-...` and deferred team-check promises, corporate off-topic guard, `"habibi"`/`"حبيبي"` stripping), and `tj-pf5x` (`5f39786`, CI `42580021221`: passive observe-only `shadow_webhook_events` collector for `WAZZUP_SHADOW_AUDIT_IPS=46.225.136.202` + `POST /api/v1/webhook/wazzup/observe` and `10:00 MSK` odd-day `Treejar Nikita Shift Report` sidecar).

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
