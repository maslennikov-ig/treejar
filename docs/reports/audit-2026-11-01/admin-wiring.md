# Treejar admin dashboard wiring audit — origin/main @712a905 (read-only worktree tj-audit-20261101)

Paths: FE = frontend/admin/src, BE = src. All admin routers (admin.py:123, admin_crm.py:44, admin_knowledge_base.py:45, admin_bot_rules.py:40) carry `Depends(require_admin_session)`; `/products/sync` has it per-route (products.py:92). No unauthenticated /api/v1/admin route found.

## 1. Inventory per view

### Shell (App.tsx, Sidebar.tsx)
| Control | Call → BE | Status | Evidence |
|---|---|---|---|
| Period selector (Overview only) | GET /dashboard/metrics/?period, /dashboard/timeseries/?period | OK | FE api/metrics.ts:6-22 → BE admin.py:237,252 |
| Header search | client-side filter; only Conversations sends `search` to server | PARTIAL (Queues/Audit filter only the loaded page) | App.tsx:86-100,557; QueuesQualityView.tsx:206-224; AuditSystemView.tsx:186-200 |
| Header refresh | refetch metrics + bump refreshSignal | BROKEN in Queues (infinite loop, see AD-02) | App.tsx:268-271 |
| Account menu / session | GET /session | OK | App.tsx:197 → admin.py:128 |
| SQLAdmin link, Logout | /admin/, /admin/logout (SQLAdmin) | OK | App.tsx:503-523 |
| Sidebar badges | metrics.escalation_count (period-scoped Escalation rows), queue/KB counts only after visiting those views, capped | PARTIAL / misleading | App.tsx:228-243; QueuesQualityView.tsx:133,139-142; KnowledgeBaseView.tsx:142,162 |
| Metrics loaded on every view | useMetrics(period) at App level | PERF | App.tsx:187 |

### Overview (OverviewView.tsx)
| Control | Call → BE | Status | Evidence |
|---|---|---|---|
| KPI cards / charts | metrics + timeseries | OK | OverviewView.tsx:176-320; services/dashboard_metrics.py |
| Attention chips (escalations, pending reviews, Zoho) | metrics, GET /manager-reviews/pending?limit=20, GET /catalog/status | PARTIAL: count capped at 20; errors swallowed → shows 0/"missing" as truth | OverviewView.tsx:70-77 |
| Drill-downs (deals/target/stage/lang/escalation) | navigate → Conversations filters | PARTIAL: no date_from → counts ≠ period KPI; list groups by phone, KPI counts conversations; escalation-reason category discarded | OverviewView.tsx:203-217,270-316; BE supports date_from admin_crm.py:62-63; metrics filter by created_at dashboard_metrics.py:144-150 |
| Metrics computed but never shown | by_segment, manager_leaderboard, feedback_count, recommend_rate, recent_feedback, avg_manager_response_time_seconds, manager_deal_conversion_rate | ORPHAN fields | schemas/admin.py:56-105 vs grep of FE |

### Conversations (ConversationsView.tsx)
| Control | Call → BE | Status | Evidence |
|---|---|---|---|
| List, 300ms search, quick tabs, status/stage/lang/escalation filters, pagination, route filters | GET /crm/customers | OK functionally; PERF: loads ALL conversations, paginates in Python, N+1 `_message_summary` per row | FE :170-220 → BE admin_crm.py:49; services/admin_crm.py:361-407 |
| "target" filter | target_only → status IN ('active','completed') | PARTIAL: 'completed' is not a ConversationStatus | services/admin_crm.py:250-253; schemas/common.py:35-39; dashboard_metrics.py:160 |
| Detail/timeline | GET /crm/conversations/{id} | OK; `feedback`, `outbound_audits` fetched but never rendered | schemas/admin.py:402-409 |
| Close escalation | POST /crm/escalations/{id}/close | OK | :326-347 → admin_crm.py:191; services 642-678 |
| Bot QA | POST /crm/conversations/{id}/quality/bot | OK (gate + quota + model/transcript/criteria passed) | :349-363 → services/admin_crm.py:822-869 |
| Reset preview/execute (typed RESET) | POST …/reset/preview, …/reset/execute | OK | :284-324 → admin_crm.py:206-235 |
| CRM drawer save | PATCH /crm/conversations/{id} | BROKEN-ish: always sends all 5 fields (stale overwrite race); escalation_status edited freely without touching Escalation rows; no server enum validation | :263-282; services/admin_crm.py:566-598; schemas/admin.py:412-418 |
| Drawer "status" = paused/closed | Conversation.status | DEAD-SWITCH for replies: reply pipeline never reads Conversation.status (only follow-ups/reports) | :810-832; chat.py (no status check; only bot_enabled 1350 & escalation_status 1447-1584) |
| Deal status free text "pending / won / delivered" | deal_status | PARTIAL: DealStatus enum is pending/in_progress/delivered/cancelled; engine writes "New Lead" | :876-883; schemas/common.py:26-32; llm/engine.py:10203 |
| (no UI) language edit, create escalation, manager QA per conversation, conversations list | PATCH language / POST …/escalations / POST …/quality/manager / GET /crm/conversations | ORPHAN | schemas/admin.py:418; admin_crm.py:84,152,254 |

### Queues & Quality (QueuesQualityView.tsx)
| Control | Call → BE | Status | Evidence |
|---|---|---|---|
| Escalation status filter Open/Resolved/All | GET /crm/escalations?status=… | BROKEN for "All": backend does `Escalation.status == 'all'` → empty | FE :107,129,332-334 → services/admin_crm.py:692-698 |
| Close escalation | POST /crm/escalations/{id}/close | OK | :160-180 |
| Manager deals: pending list + Evaluate | GET /manager-reviews/pending?limit=25; POST /manager-reviews/{id}/evaluate | OK (gate, quota, kwargs) ; NOT audited | :133,182-204 → admin.py:635,688-711 |
| Recent reviews table + drawer | GET /manager-reviews/?page_size=20 | PARTIAL: drawer has no criteria/summary (no detail endpoint) | :134,673-710 |
| "AI rubric" drawer (15 criteria) | hard-coded | MOCK, does not match evaluator rules | :57-73 vs quality/evaluator.py:151-165 |
| Contours cards | GET /ai-quality-controls | OK | :589-640 |
| refresh effect | deps include non-memoized hook object | BROKEN: infinite refetch loop once refreshSignal>0 | :154-158; hooks/useAIQualityControlBlock.ts:155-163 |

### Knowledge Base (KnowledgeBaseView.tsx)
| Control | Call → BE | Status | Evidence |
|---|---|---|---|
| List/search/category filter | GET /knowledge-base/entries?page_size=50 | PARTIAL: no pagination >50, no debounce, refetch on every selection (load depends on `selected`) | :135-183 → admin_knowledge_base.py:50 |
| Create/update/preview/soft delete/reindex | POST/PATCH/DELETE entries, POST entries/preview, POST entries/{id}/reindex | OK (embeds + audit) | services/admin_knowledge_base.py:233-379 |
| Candidates drawer approve/reject | GET/POST candidates… | OK; badge capped at page 20 | :142,162 |
| Canonical sync modal (safe/full_reset) | GET sync-canonical/preview, POST sync-canonical | OK | CanonicalSyncButton.tsx |
| Auto-seed on empty list | POST sync-canonical silently on view load | PARTIAL (mutation without confirmation, errors swallowed) | :145-158 |
| Category select | hard-coded 8 values | PARTIAL: canonical seed uses 'products' (not offered) | :62-71 vs canonical_admin_seed.py:200 |
| Language select | stored | DEAD for retrieval: search_knowledge ignores language | rag/pipeline.py:154-172 |
| (no UI) GET entries/{id}, POST /reindex (all), POST /candidates, /seed-defaults, /sync-canonical/status, include_deleted/restore | | ORPHAN | admin_knowledge_base.py:73,139,166,225,245 |

### Bot Rules (BotRulesView.tsx)
| Control | Call → BE | Status | Evidence |
|---|---|---|---|
| List/search/status filter | GET /bot-rules/rules | OK | :141-171 → admin_bot_rules.py:45 |
| Create/update/archive/reindex | POST/PATCH/DELETE rules, POST rules/{id}/reindex | OK (re-embed + audit) | services/admin_bot_rules.py:216-325 |
| type, priority, stage, language, segment, instruction, trigger_examples | read by runtime | OK | services/bot_behavior_rules.py:77-176 |
| scope (global/stage/language/segment/conversation) | stored only | DEAD-SWITCH: runtime ignores scope; "conversation" (no target id field) or empty-condition scopes act GLOBAL | :206-221; bot_behavior_rules.py:135-176; schemas/admin.py:202,238-248 |
| Stage options | greeting…closing | PARTIAL: missing company_details, feedback | BotRulesView.tsx (options block ~L552-561) vs schemas/common.py:15-23 |
| Sandbox "test" | POST /bot-rules/preview | PARTIAL: only ACTIVE rules → a draft being edited never appears; /rules/{id}/test unused | :223-239; services/admin_bot_rules.py:372-391,394+ |
| Canonical/manual badge | hard-coded titles | MOCK/BROKEN: none of 8 titles exist in seed → every rule shows "Manual" | :58-67,313-318 vs canonical_admin_seed.py:257-363; BE already returns source_type/canonical_key |
| Auto-seed on empty | POST sync-canonical | PARTIAL (silent mutation) | :146-159 |
| (no UI) GET rules/{id}, POST rules/{id}/test, POST /reindex, /seed-defaults, /sync-canonical/status | | ORPHAN | admin_bot_rules.py:72,119,136,151,171 |

### Catalog (CatalogView.tsx)
| Control | Call → BE | Status | Evidence |
|---|---|---|---|
| KPIs / last sync | GET /catalog/status | PARTIAL: last-sync state is a per-process dict, lost on restart, stuck at "queued" forever; DB errors swallowed → zeros | admin.py:313,390-396,409-431 |
| Sync Treejar / Zoho (confirm) | POST /products/sync | OK enqueue; result panel shows placeholder zeros as if real | CatalogView.tsx:60-90,189-227; products.py:107-111 |
| Status load errors | swallowed | PARTIAL | CatalogView.tsx:44-46 |

### Reports (ReportsView.tsx)
| Generate | POST /reports/generate {} | PARTIAL: fixed last-7-days, no date range though BE supports start/end; regenerated on every visit | ReportsView.tsx:27-47; reports.py:19-24 |

### Settings (SettingsView.tsx + AIQualityControlsPanel.tsx + EnableManualModeButton.tsx)
| Control | Call → BE | Runtime reader | Status | Evidence |
|---|---|---|---|---|
| Mode per scope (disabled/manual/daily_sample/scheduled) | PATCH /ai-quality-controls | quality/job.py:554-578,736-760; manager_job.py:323-347; admin_crm.py:99-127 | OK, except red_flags "manual" = no manual entrypoint (acts as disabled) | config.py:370-418 |
| transcript_mode, model, cache_telemetry | same | job.py:611-634,803-827; manager_job.py:396-425; admin_crm.py:149-156 | OK wiring | |
| Model dropdown | same | | BROKEN display: options = gemini-3.1-flash-lite-preview / gpt-5.4-mini / glm5-20260211; current default `openai/gpt-6.1-terra` and cheap `glm-5.2` absent → select shows wrong model, can only pick stale ones | AIQualityControlsPanel.tsx:33-37,759-775; llm/safety.py:50,485-499; quality/config.py:152 |
| daily_budget, max_calls_per_run/day | same | config.py:655-714; job gates | OK (FE max attrs 5000/25/100 vs BE 20000/100/500) | |
| retry max_attempts/backoff | same | evaluator.py:863-865 | OK; FE allows 3, BE le=2 → raw 422 | Panel:847-861; config.py:113 |
| criteria toggles | same | evaluator.py:794,908; manager_evaluator.py:259-270 | OK | |
| alert_on_failure, overrides | same | evaluator.py:864 | OK | |
| "Enable manual mode" | PATCH | | OK (also flips red_flags to useless manual) | EnableManualModeButton.tsx:23-31 |
| Saves audited? | | | NO audit row | admin.py:733-756 |
| Telegram config + test | GET /notifications/config, POST /notifications/test | env | OK (configured flag = token only vs health = token+chat) | notifications.py:43-53; admin.py:542-545 |

Backend-configurable with NO dashboard UI:
- `bot_enabled` (global kill switch; read by chat.py:1350-1358, outbound_safety.py:55-62, health admin.py:532-536) — only via SQLAdmin SystemConfig or orphan PATCH /settings/.
- `telegram_test_mode_enabled` (inbound_channels.py:105-107) — same.
- `payment_reminder_controls` (followup.py:87-117, cron run_automatic_followups worker.py:210) — full GET/PUT/PATCH API orphan (admin.py:759-795); "manual" mode has no trigger (`run_payment_reminders` not registered/enqueued anywhere).
- `legacy_automatic_followup_enabled` (followup.py:616-623) — SQLAdmin only.
- System prompts (`SystemPrompt`, read by llm/prompts.py:176-208 → engine.py:8918) — orphan /prompts endpoints (admin.py:149-201) or SQLAdmin in-place edit.
DEAD values in /settings/ (nothing reads them): `default_language`, `follow_up_enabled`, `max_messages_per_conversation` (admin.py:798-857; grep shows only schemas/admin.py:165-177).

### Audit & System (AuditSystemView.tsx)
| Control | Call → BE | Status | Evidence |
|---|---|---|---|
| Audit list, entity/actor filter, pagination, entity navigation | GET /crm/audit | OK; labels wrong for escalation.create (→"close") and quality.manager_review (→"bot review") | AuditSystemView.tsx:49,69 → admin_crm.py:270 |
| System health | GET /system/health | PARTIAL: no contour can ever be "error"; DB exceptions swallowed (`except: pass`) → looks healthy/needs_seed; `bool("false")`==True; FE swallows fetch errors | admin.py:497-538,548-599; AuditSystemView.tsx:162-172 |

### Guide / Acceptance
- Guide: static (data/adminGuideData.ts). References nonexistent `/test` (lines 763-773, 971; real route /client-self-test main.py:251); claims "every action is audited" (520-521) — false (see AD-14); says escalations filter has "All" (160) — broken.
- Acceptance: POST /admin/client-self-test/submit (admin.py:301) or public /api/v1/client-self-test/submit (client_self_test.py:12-18, unauthenticated Telegram relay, no rate limit).

### Legacy SQLAdmin /admin/ (main.py:113-127, api/admin/views.py)
16 views. Writable: KnowledgeBaseAdmin create/edit/HARD delete (no embedding, no audit, bypasses soft-delete) views.py:96-105; EscalationAdmin edit (no conversation.escalation_status sync) 132-145; SystemConfigAdmin create/edit raw JSON 147-155; SystemPromptAdmin in-place edit (no versioning) 169-182. Read-only: audit, conversations (id/dates only), summaries, messages, outbound audit, products, KB candidates, quality reviews, manager reviews, metrics snapshot, referrals, feedback. Also hosts /admin/login & /admin/logout used by the dashboard. Still required today as the only UI for bot_enabled / test mode / prompts / payment reminders / legacy follow-ups; none of its writes are audited.

## 2. Prioritized defects
(see message body / same list)

| ID | Sev | Title | Evidence | Root cause | Fix | Size | Local w/o owner? |
|---|---|---|---|---|---|---|---|
| AD-01 | P1 (security; P0 if confirmed on prod) | Path traversal / arbitrary file read on public SPA routes | main.py:251-258 (/client-self-test/{path}), main.py:274-280 (landing catch-all) | os.path.join + isfile without realpath containment; uvicorn decodes %2F; nginx `proxy_pass $backend` forwards raw URI. Reproduced with identical route code in scratch TestClient: `/client-self-test/..%2F..%2Fsecret.txt` → 200 file body | Reuse serve_admin_spa containment (main.py:242-248) in both handlers; add regression test | S | yes |
| AD-02 | P1 | Queues view infinite refetch loop after any global refresh | QueuesQualityView.tsx:154-158; useAIQualityControlBlock.ts:155-163 | effect deps include fresh `managerQa` object; effect calls refresh() → setVersion → rerender → loop (refreshSignal is never reset, App.tsx:183) | depend on `managerQa.refresh` (stable useCallback) or useMemo the hook return | S | yes |
| AD-03 | P1 | Escalations "All" filter always empty | QueuesQualityView.tsx:107,129,334 → services/admin_crm.py:692-698 | FE sends status=all; BE filters status=='all' | FE omit status for 'all' and/or BE treat 'all'/'' as no filter | S | yes |
| AD-04 | P1 | CRM drawer save clobbers live fields + desyncs escalation state | ConversationsView.tsx:263-282; services/admin_crm.py:566-598 | PATCH sends all fields from stale snapshot; escalation_status set without Escalation rows (queue/health still "open", or bot paused with no escalation) | Send only dirty fields; BE validate enums; route escalation_status changes via close/create escalation services (or make it read-only in drawer) | M | dirty-fields + validation yes; whether operators may set manual_takeover/pending from card = owner |
| AD-05 | P1 | AI QC model selector stale, misrepresents active model | AIQualityControlsPanel.tsx:33-37,759-775 vs llm/safety.py:50, quality/config.py:152 | hard-coded list predates Terra/glm-5.2 | BE expose `available_models` + default from llm/safety; FE always render current value | S-M | yes (derive from backend policy) |
| AD-06 | P1 | Bot-rule `scope` is a dead switch; "conversation"/empty scopes apply globally | BotRulesView.tsx:206-221; bot_behavior_rules.py:135-176; schemas/admin.py:202,238-248 | runtime filters only by stage/language/segment columns | BE validation: scope≠global requires its field; drop "conversation" until a target id exists (or implement) | M | validation yes; conversation-scope implement vs remove = owner |
| AD-07 | P2 | Canonical badge never shows (mock titles) | BotRulesView.tsx:58-67,313-318 vs canonical_admin_seed.py:257-363 | hard-coded stale titles | use rule.source_type/canonical_key/is_canonical_customized | S | yes |
| AD-08 | P2 | Bot QA rubric drawer is mock, contradicts evaluator | QueuesQualityView.tsx:57-73 vs quality/evaluator.py:151-165 | hand-written list | serve rubric from BE constant (or copy exact 15 rules, 2 pts each) | S | yes |
| AD-09 | P2 | Conversation status "paused"/"closed" doesn't stop Noor | ConversationsView.tsx:810-832; chat.py (no status gate) | status only used by follow-ups/reports | implement pause gate in chat.py OR relabel/remove option | M | no (product semantics) |
| AD-10 | P2 | bot_enabled: no dashboard toggle; inconsistent parsing | chat.py:1350-1358 (missing→on), outbound_safety.py:55-62 (missing→deny), admin.py:536,808 (bool(str)) | ad-hoc readers | shared bool-config helper + explicit seeded row; expose audited toggle with confirm | M | helper yes; toggle exposure = owner/ops |
| AD-11 | P2 | Dead settings default_language / follow_up_enabled / max_messages_per_conversation | admin.py:798-857; schemas/admin.py:165-177 | never wired; follow-ups read `legacy_automatic_followup_enabled` (followup.py:616-623) | remove from /settings (no UI uses it) or wire deliberately | S | removal yes; wiring = owner |
| AD-12 | P2 | Payment reminders: API+runtime, no UI; "manual" mode has no trigger | admin.py:759-795; followup.py:51-55,943-956; worker.py:142-163 | run_payment_reminders not registered/enqueued | decide UI; drop 'manual' or register job + audited admin trigger | M | no |
| AD-13 | P2 | Overview drill-downs ignore period | OverviewView.tsx:203-316; ConversationsView.tsx:174-195; admin_crm.py:62-63 | no date_from in route | add date_from route param from period; also pass reason category | S-M | yes |
| AD-14 | P2 | Audit gaps | admin.py:688-756,771-795,820-857,171-201,375-397,294-298; auth.py:142-161; SQLAdmin writes | no log_admin_action on AI QC/payment/settings/prompts/sync/test notification/manager evaluate/password login | add log_admin_action calls | S-M | yes |
| AD-15 | P2 | System health can't show error; masks DB failures | admin.py:497-538,548-599; also catalog status admin.py:430-431 | broad except: pass; no error branch | per-contour try → status=error; proper bool parse | S | yes |
| AD-16 | P2 | Catalog sync result fake zeros; last-sync in process memory | products.py:111; CatalogView.tsx:189-227; admin.py:313,390-396 | enqueue-only endpoint; in-memory dict | show "queued" only; persist trigger+completion (job writes Redis/SystemConfig) | M | yes |
| AD-17 | P2 | SQLAdmin writable bypasses | views.py:96-105,132-155,169-182 | raw ORM edits skip embeddings/soft-delete/versioning/audit | make KB & Escalation read-only now; move SystemConfig/prompts to audited dashboard endpoints, then lock | S (+M) | KB/Escalation read-only yes; rest needs UI first |
| AD-18 | P2 | Customers list full scan + N+1 | services/admin_crm.py:361-407 | Python grouping/pagination | SQL DISTINCT ON(phone)/window + batched last-message query | M | yes |
| AD-19 | P2 | Public self-test submit = unauthenticated Telegram relay | client_self_test.py:12-18; router.py:42-46 | public by design | rate-limit or tokenized link; or retire | S | no (keep-public decision) |
| AD-20 | P3 | red_flags "manual" mode meaningless; Enable-manual flips it | config.py:393-396; EnableManualModeButton.tsx:14-31 | no manual red-flag entrypoint | hide manual for red_flags / skip in payload | S | yes |
| AD-21 | P3 | AI QC input bounds ≠ backend | AIQualityControlsPanel.tsx:786-869 vs config.py:113-114,175-177 | | align min/max, friendly 422 | S | yes |
| AD-22 | P3 | Sandbox can't test draft rule | BotRulesView.tsx:223-239; admin_bot_rules.py:119 | uses /preview (active only) | call /rules/{id}/test when a rule is selected | S | yes |
| AD-23 | P3 | Bot-rule stage options incomplete | BotRulesView.tsx ~552-561 | | add company_details, feedback | S | yes |
| AD-24 | P3 | KB category list misses 'products' | KnowledgeBaseView.tsx:62-71 | hard-coded | add / derive from data | S | yes |
| AD-25 | P3 | KB language not used by retrieval | rag/pipeline.py:154-172 | | decide: filter by conversation language or label as informational | S | no |
| AD-26 | P3 | Badge semantics/caps | App.tsx:237-243; OverviewView.tsx:71; QueuesQualityView.tsx:133,276; KnowledgeBaseView.tsx:162 | page lengths & period counts used as totals | use totals / system-health open counts | S | yes |
| AD-27 | P3 | Audit action labels wrong | AuditSystemView.tsx:49,69 | copy/paste | add proper keys | S | yes |
| AD-28 | P3 | Silent error swallowing (UI) | CatalogView.tsx:44-46; AuditSystemView.tsx:166-168; OverviewView.tsx:72-76; useAIQualityControlBlock.ts:145-147 (fail → buttons enabled); KB/BotRules auto-seed catch | | surface error state | S | yes |
| AD-29 | P3 | Redundant fetches | all `[refreshSignal, load]` effects re-fire on filter change; KB/BotRules load depends on `selected`; no search debounce | | separate refresh counter ref; drop `selected` dep; debounce | S | yes |
| AD-30 | P3 | Guide inaccuracies | adminGuideData.ts:160,520-521,763-773,971 | | fix /test→/client-self-test etc. | S | yes |
| AD-31 | P3 | Orphan endpoints / dead client fns | BE: admin.py:149-235 (/prompts, /metrics/ + MetricsSnapshot cron worker.py:213-217), 267-285, 733-743 (PUT AIQC), 759-857; KB/BotRules/CRM orphans above. FE unused: fetchCanonicalKnowledgeBaseStatus, fetchCanonicalBotRulesStatus, fetchRecentFeedback, fetchReferralPolicy (api/*.ts) | | per item: wire or delete | S each | partly (deletions of pure-dead yes; prompts/referrals = owner) |
| AD-32 | P3 | Non-i18n strings | ConversationsView.tsx:766,881,899-900; CatalogView.tsx:256; QueuesQualityView.tsx:590,607; App.tsx:148-153; useMetrics.ts 'Unknown error' | | add keys | S | yes |
| AD-33 | P3 | Prompt Redis cache never hits; PUT /prompts drops description | llm/prompts.py:183-185 with core/redis.py:11 decode_responses=True; admin.py:187-192 | bytes check | accept str | S | yes |
| AD-34 | P3 | "target" = status in (active, completed) — 'completed' doesn't exist | services/admin_crm.py:251; dashboard_metrics.py:160 | | define target properly | S | no |
| AD-35 | P3 | Session/login hardening | main.py:75 (no https_only/max_age), auth.py:142-161 (no throttle/audit) | | env-aware https_only, throttle, audit | S | yes |
| AD-36 | P3 | Telegram "configured" inconsistent | notifications.py:50 vs admin.py:542-545 | | require token+chat | S | yes |
| AD-37 | P3 | Auto-FAQ duplicate check counts soft-deleted KB | services/auto_faq.py:204-207 | | add deleted_at IS NULL | S | yes |
| AD-38 | P3 | Reports: no date range; feedback/outbound audits/manager criteria hidden | ReportsView.tsx:27-37; ConversationsView drawer; QueuesQualityView.tsx:684-708 | | add pickers/sections | M | yes |
