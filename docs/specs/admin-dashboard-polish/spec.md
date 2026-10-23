# Specification: Admin Dashboard (`/dashboard/`) Quality, Data Seeding, AI Quality Controls Wiring, Instant Tooltips, Bilingual RU/EN Localization & Executive Charts

- **Epic ID:** `tj-ierv`
- **Child Tasks:** `tj-ierv.1`, `tj-ierv.2`, `tj-ierv.3`, `tj-ierv.4`, `tj-ierv.5`
- **Plan:** `docs/plans/2026-10-23-admin-dashboard-polish-plan.md`
- **Date:** 2026-10-23

---

## 1. Executive Summary & Audit Findings

A full code and production database audit of the Treejar Noor Admin Dashboard (`/dashboard/`, source in `frontend/admin/` and `src/api/v1/admin*.py`) revealed five concrete root causes behind the UX and functional gaps:

1. **Knowledge Base (`База знаний`) & Bot Rules (`Правила бота`) appear empty:**
   - **Knowledge Base:** On every customer message, `src/llm/message_processor.py` (`_retrieve_context`) calls `search_knowledge(turn.db, ...)` over `knowledge_base` (`WHERE deleted_at IS NULL AND embedding IS NOT NULL`) and merges it with `with_approved_faq` (`src/llm/company_faq.py`). However, `index_documents` in `src/rag/indexer.py` is never called automatically and has no admin trigger, while all 12 rows in production `knowledge_base` are soft-deleted QA smoke test rows (`QA disposable KB 20260511...`, `deleted_at IS NOT NULL`). Thus `SELECT count(*) FROM knowledge_base WHERE deleted_at IS NULL` is `0`.
   - **Bot Behavior Rules:** On every customer message, `src/llm/message_processor.py` calls `engine.search_behavior_rules(...)` (`src/services/bot_behavior_rules.py`), which retrieves up to 12 active hard/escalation rules (`type IN ('hard_rule', 'escalation_rule')`) plus up to 6 semantically matched soft rules (`playbook`, `upsell_rule`, `style_rule`), injects them as `[BOT OPERATING RULES]` into the prompt, and stores applied rules in `conversation.metadata_["last_applied_bot_rules"]`. However, no canonical Treejar rules were ever seeded into `bot_behavior_rules`; the only 4 rows in production are archived QA smoke test rows (`QA disposable bot rule 20260511...`, `status='archived'`).
   - **Archived Filter Bug:** In `src/services/admin_bot_rules.py` (`list_admin_bot_rules`), `if not include_archived: filters.append(BotBehaviorRule.archived_at.is_(None))` runs even when the UI passes `status='archived'`. Because `archive_admin_bot_rule` sets both `status='archived'` and `archived_at=now()`, selecting `"Архив"` in the UI always returns `0` rows.

2. **AI Quality Controls (`AIQualityControlsPanel` / `src/quality/config.py`) partial backend wiring:**
   - **Connected today:** Stored in `system_configs` (`key = 'ai_quality_controls'`). Scheduled ARQ jobs (`evaluate_mature_conversations_quality`, `evaluate_realtime_red_flags` in `src/quality/job.py` and `evaluate_escalated_conversations` in `src/quality/manager_job.py`) read `mode`, `transcript_mode`, `model`, `max_calls_per_run`, `max_calls_per_day`, and `cache_telemetry_enabled`. Manual triggers check `require_admin_ai_quality_manual_gate`.
   - **Disconnected / Broken today:**
     - **Manual triggers ignore settings:** `run_admin_bot_quality_review` (`src/services/admin_crm.py`), `run_admin_manager_quality_review` (`src/services/admin_crm.py`), and `evaluate_admin_manager_review` (`src/api/v1/admin.py`) check the gate but call `evaluate_conversation` / `evaluate_manager_conversation` **without** passing the configured `gate.model`, `gate.transcript_mode`, or `gate.cache_telemetry_enabled`, and without recording the daily call counter.
     - **Empty `criteria` toggles:** `AIQualityScopeConfig.criteria` defaults to `{}` for all 3 scopes (`bot_qa`, `manager_qa`, `red_flags`), so the UI displays `"No criteria JSON exposed for this scope."` and evaluators never inspect `criteria`.
     - **Unwired `daily_budget_cents`, `retry`, and `alert_on_failure`:** `daily_budget_cents` only checks `> 0` without checking actual daily QA spend; `retry` (`max_attempts`, `backoff_seconds`) and `alert_on_failure` are saved in JSON but not enforced by QA runners.
     - **Blocked manual QA UX & developer jargon:** Because `mode` defaults to `'disabled'`, the `"Bot QA"` and `"Evaluate"` buttons across `Conversations`, `Queues`, and `Quality` are blocked without a 1-click button to enable `manual` mode. Meanwhile, the bottom of `AIQualityControlsPanel.tsx` exposes raw internal developer notes (`"Existing internal endpoint: POST /api/v1/quality/reviews/..."`).

3. **Slow native tooltips (`title="..."`) & missing contextual help (`?`):**
   - `TooltippedLabel` in `AIQualityControlsPanel.tsx` uses the native HTML `title` attribute, which has an OS/browser hover delay of 800–1500ms.
   - Outside those 8 labels in `AIQualityControlsPanel.tsx`, the other 10 views of the dashboard have **zero** `?` tooltips and no explanatory onboarding banners.
   - Additionally, the global search input (`Поиск...`) in the top header of `App.tsx` has no `value` or `onChange` handler (dead input), and `Reset preview` in `ConversationsView` uses `window.alert(JSON.stringify(...))`.

4. **Mixed Russian and English UI strings (`RU` + `EN`):**
   - The sidebar and metric tiles are in Russian (`Обзор`, `Диалоги`, `Эскалации`), while the charts (`Classification`, `By Language`, `Target vs Non-target`, `Conversations`, `Sales & Escalation`), editor buttons (`Preview`, `Save and index`, `Reindex`, `Soft-delete`, `Approve`, `Reject`), and the entire `AIQualityControlsPanel` are in English. There is no language switcher.

5. **Clipped `Classification` pie chart (`SegmentPieChart.tsx`) & missing visual analytics:**
   - `SegmentPieChart.tsx` places two Recharts `<PieChart>` components inside a `grid-cols-2` container inside a 1/3-width card (`~160px` per chart) with `outerRadius={70}` and external radial SVG labels (`label={({ name, percent }) => ...}`). The radial leader lines and text (`"EN 94%"`, `"Target 63%"`, `"Non-target 37%"`) overflow the SVG viewport and are visibly sliced off on the left, top, and right.
   - `DashboardMetrics` (`src/services/dashboard_metrics.py`) already computes `escalation_reasons`, `new_vs_returning`, `average_deal_value`, `avg_conversation_length`, `llm_cost_usd`, `feedback_count`, `nps_score`, and `recommend_rate`, none of which are visualized on the `Overview` tab.

---

## 2. Hard Constraints & Protected Files

- **Do NOT modify SHA256-pinned corpus files:**
  - `src/models/product.py`
  - `src/rag/embeddings.py`
  - `src/rag/pipeline.py`
  - `src/schemas/product.py`
  (All Knowledge Base and Bot Rule seeding must live in `src/services/admin_knowledge_base.py` and `src/services/admin_bot_rules.py`, calling `EmbeddingEngine` from `src.rag.embeddings` without editing `src/rag/`.)
- **If `.codex/handoff.md` is updated:** run `uv run python scripts/orchestration/repin_traceability_manifest.py` and keep `.codex/handoff.md` `<= 200` lines.
- **No external Google Fonts:** `frontend/admin/index.html` must not load `fonts.googleapis.com` or `fonts.gstatic.com` (`tests/test_admin_dashboard_frontend.py`).

---

## 3. Detailed Requirements by Task

### 3.1. Task `tj-ierv.1` — Knowledge Base & Bot Behavior Rules Seeding, Filter Bugfix & Guided Onboarding

1. **Canonical Knowledge Base Seed (`src/services/admin_knowledge_base.py` & `src/api/v1/admin_knowledge_base.py`):**
   - Define `CANONICAL_KB_ENTRIES` containing 8 verified, owner-approved Treejar knowledge entries (no unconfirmed warranty/discount/fee promises):
     1. `Delivery across Dubai, Sharjah & UAE` (`source="faq"`, `category="delivery"`, `language="en"`, content from approved `docs/faq.md` Q9).
     2. `Professional Assembly & Installation` (`source="faq"`, `category="delivery"`, `language="en"`, content from approved `docs/faq.md` Q10).
     3. `UAE 5% VAT & Commercial Quotation Format` (`source="policy"`, `category="pricing"`, `language="en"`, explains that all product and package totals are shown both excl. 5% VAT and incl. 5% VAT, and formal PDF quotations are generated once customer name, company/individual status, delivery address, and exact SKUs/quantities are confirmed).
     4. `Wholesale Orders (20+ Units) & Project Pricing` (`source="policy"`, `category="b2b_handoff"`, `language="en"`, explains that orders of 20+ units or bulk discount requests receive 2–3 in-stock reference options with photos/links and are routed to a dedicated B2B manager with a short project brief).
     5. `Custom & Made-to-Order Office Furniture` (`source="policy"`, `category="b2b_handoff"`, `language="en"`, explains bespoke dimensions/materials routing to a project manager while offering standard in-stock alternatives immediately).
     6. `Treejar Company Values & Consultative Service` (`source="values"`, `category="company_values"`, `language="en"`, core principles from `docs/05-company-values.md`).
     7. `Ergonomic Chairs & Executive Seating Lineup` (`source="catalog_guide"`, `category="products"`, `language="en"`, guide to mesh task chairs, executive leather/fabric seating, visitor chairs, and canonical `treejartrading.ae/product/<slug>` links).
     8. `Workstations, Manager Desks & Acoustic Pods Lineup` (`source="catalog_guide"`, `category="products"`, `language="en"`, guide to single desks, 2/4/6-person clusters, LUMA/NOVO/IMAGO/XTEN series, mobile pedestals, and acoustic booths).
   - Add `seed_default_admin_kb_entries(db: AsyncSession, *, request: object | None = None) -> AdminActionResult` and `POST /api/v1/admin/knowledge-base/seed-defaults`:
     - Idempotently upserts `CANONICAL_KB_ENTRIES` by `(source, title)`, restores `deleted_at = None` if previously soft-deleted, generates embeddings via `EmbeddingEngine().embed_batch_async(...)`, and logs `knowledge_base.seed_defaults` in `AdminActionAudit`.
   - In `list_admin_kb_entries`:
     - Exclude synthetic QA smoke test rows (`source LIKE 'qa_%'` or `title LIKE 'QA disposable%'` or `title LIKE 'QA sentinel%'`) unless `search` explicitly contains `'qa'`.
     - If active non-QA entries count is `0` and no search/filter is active, auto-seed `CANONICAL_KB_ENTRIES` (or provide a 1-click button in the UI + seed on demand) so the Knowledge Base is never inexplicably blank for the client.

2. **Canonical Bot Behavior Rules Seed & Archived Filter Bugfix (`src/services/admin_bot_rules.py` & `src/api/v1/admin_bot_rules.py`):**
   - Fix `list_admin_bot_rules`:
     - When `status == "archived"` or `include_archived is True`, do **not** append `BotBehaviorRule.archived_at.is_(None)`. When `status == "archived"`, filter `BotBehaviorRule.status == "archived"`.
     - Exclude synthetic QA smoke test rows (`title LIKE 'QA disposable%'`) unless `search` explicitly contains `'qa'`.
   - Define `CANONICAL_BOT_RULES` with 7 real, active Treejar rules covering all 5 rule types (`hard_rule`, `playbook`, `upsell_rule`, `style_rule`, `escalation_rule`):
     1. `Consultative B2B Opening & Need Discovery` (`type="playbook"`, `priority=10`, `scope="global"`, `status="active"`).
     2. `5% UAE VAT & Turnkey Package Math Transparency` (`type="hard_rule"`, `priority=15`, `scope="global"`, `status="active"`).
     3. `Canonical Product Links & Real Catalog Photos` (`type="hard_rule"`, `priority=20`, `scope="global"`, `status="active"`).
     4. `Wholesale (20+ Units) & Custom Furniture Manager Handoff` (`type="escalation_rule"`, `priority=25`, `scope="global"`, `status="active"`).
     5. `Formal PDF Quotation Details Gate` (`type="hard_rule"`, `priority=30`, `scope="stage"`, `stage="quoting"`, `status="active"`).
     6. `Workspace Completeness & Cross-Sell (Chairs, Pedestals, Accessories)` (`type="upsell_rule"`, `priority=40`, `scope="stage"`, `stage="solution"`, `status="active"`).
     7. `Concise Executive Tone & Strict EN/AR Language Matching` (`type="style_rule"`, `priority=50`, `scope="global"`, `status="active"`).
   - Add `seed_default_admin_bot_rules(db: AsyncSession, *, request: object | None = None) -> AdminActionResult` and `POST /api/v1/admin/bot-rules/seed-defaults` (plus auto-seed when active non-QA rules count is `0` or via 1-click button in UI).

---

### 3.2. Task `tj-ierv.2` — AI Quality Controls (`iQualityControls`) End-to-End Wiring & UX

1. **Default Criteria per Scope (`src/quality/config.py`):**
   - Define `DEFAULT_SCOPE_CRITERIA: dict[AIQualityScope, dict[str, bool]]`:
     - `AIQualityScope.BOT_QA`:
       - `"greeting_and_identity": True`
       - `"need_discovery_and_catalog": True`
       - `"commercial_vat_and_quotation": True`
       - `"tone_and_language": True`
     - `AIQualityScope.MANAGER_QA`:
       - `"response_speed_sla": True`
       - `"handover_context_usage": True`
       - `"commercial_terms_accuracy": True`
       - `"closing_and_crm_hygiene": True`
     - `AIQualityScope.RED_FLAGS`:
       - `"missing_identity": True`
       - `"unanswered_customer_question": True`
       - `"unverified_promise_or_hallucination": True`
       - `"missed_escalation_signal": True`
       - `"pushy_or_impolite_tone": True`
   - In `AIQualityControlsConfig`, backfill default criteria for each scope whenever `scope_config.criteria` is empty (`{}`), while preserving any explicit `True`/`False` overrides saved by the admin.

2. **Full Backend Wiring for Manual & Scheduled Execution:**
   - Update `require_admin_ai_quality_manual_gate(db, scope)` in `src/services/admin_crm.py` to return the resolved `(AIQualityScopeConfig, AIQualityRunGate)` instead of `None`.
   - In `run_admin_bot_quality_review` (`src/services/admin_crm.py`), pass `model_name=gate.model`, `transcript_mode=gate.transcript_mode`, and `cache_telemetry_enabled=gate.cache_telemetry_enabled` into `evaluate_conversation(...)`.
   - In `run_admin_manager_quality_review` (`src/services/admin_crm.py`) and `evaluate_admin_manager_review` (`src/api/v1/admin.py`), pass `model_name=gate.model`, `transcript_mode=gate.transcript_mode`, and `cache_telemetry_enabled=gate.cache_telemetry_enabled` into `evaluate_manager_conversation(...)` / `evaluate_escalation(...)`.
   - Enforce disabled criteria filtering in `evaluate_conversation`, `evaluate_manager_conversation`, and `evaluate_red_flags` (e.g. if a red-flag category or criterion group is toggled `False` in `scope_settings.criteria`, filter or weight accordingly).
   - Enforce `retry.max_attempts` / `retry.backoff_seconds` and `alert_on_failure` in `src/quality/job.py` and `src/quality/manager_job.py`.

3. **1-Click Manual Mode Activation & Clear Business Explanation in UI:**
   - In `AIQualityControlsPanel.tsx`, add a 1-click **"Включить ручной режим для всех / Enable Manual Mode for All"** button at the top when scopes are `disabled`, and add a quick action button in `ConversationsView`, `QueuesView`, and `QualityView` so the admin can enable `manual` mode in one click without leaving the current tab.
   - Replace the raw developer notes at the bottom of `AIQualityControlsPanel.tsx` (`POST /api/v1/quality/reviews/...`) with a clear explanation of the 3 quality contours (`Bot QA 30 pts`, `Manager QA 20 pts`, `Red Flags realtime scan`) while keeping `aria`/data hooks needed by tests.

---

### 3.3. Task `tj-ierv.3` — Instant Custom Tooltips (`?`), Section Guides & Global Header Search

1. **Instant Custom Popover Tooltip (`frontend/admin/src/components/ui/InfoTooltip.tsx`):**
   - Render a `?` icon (`HelpCircle`) that opens a styled floating popover **instantly** (`0ms` hover/focus delay, `120ms` opacity/transform transition) on `onMouseEnter`, `onFocus`, or `onClick`.
   - Do **not** rely on browser-delayed native `title="..."` for the visual UX; expose `data-tooltip={tooltip}` and `aria-label={tooltip}` for accessibility and static markup regression tests.
   - Include a reusable `SectionGuideBanner` component with an icon, concise title, 1–2 sentence explanation of how the section works in Noor's pipeline, and optional quick-action button.

2. **Add `?` Tooltips & Section Guides Across All 11 Views:**
   - Every view (`Overview`, `Conversations`, `Queues`, `Knowledge Base`, `Bot Rules`, `Catalog`, `Quality`, `Reports`, `Settings`, `Audit`, `Support`), every KPI tile, every chart header, every CRM inspector section, and every form field in `KnowledgeBaseView`, `BotRulesView`, and `AIQualityControlsPanel` must have a clear `?` tooltip explaining its meaning and impact on the bot.
   - Replace `globalThis.alert(JSON.stringify(preview, null, 2))` in `ConversationsView` (`handleResetPreview`) with a clean inline/modal Reset Preview card in the right-hand inspector.
   - Wire the top-header global search input (`Поиск...` / `Search...`) so typing filters the current view (`Conversations`, `Knowledge Base`, `Bot Rules`, `Audit`) or switches to `Conversations` search when typing from other tabs.

---

### 3.4. Task `tj-ierv.4` — Full Bilingual Localization (`RU` / `EN`) & Language Switcher

1. **Bilingual Dictionary & Provider (`frontend/admin/src/i18n/`):**
   - Create `frontend/admin/src/i18n/translations.ts` and `frontend/admin/src/i18n/LanguageContext.tsx` supporting `lang: 'ru' | 'en'` (persisted in `localStorage` under `'noor_admin_lang'`, defaulting to `'ru'`).
   - Add a `RU | EN` segmented toggle in the top header of `DashboardApp` (`frontend/admin/src/App.tsx`).
   - Translate 100% of UI text in both languages:
     - Sidebar navigation, header controls, period selector (`День / Неделя / Месяц / Все` vs `Day / Week / Month / All`).
     - All chart titles, subtitles, axis labels, legend items, empty states, and tooltip labels (`Conversations` ↔ `Динамика диалогов`, `Classification` ↔ `Классификация диалогов`, `By Language` ↔ `По языкам`, `Target vs Non-target` ↔ `Целевые и нецелевые`, `Sales & Escalation` ↔ `Продажи и эскалации`, plus the new charts).
     - All form labels, buttons, badges, statuses, confirmation prompts, and inspector headings in `ConversationsView`, `QueuesView`, `KnowledgeBaseView`, `BotRulesView`, `CatalogView`, `QualityView`, `ReportsView`, `SettingsView`, `AuditView`, `SupportView`, `AIQualityControlsPanel`, and `OperatorCenter`.
     - Locale-aware `formatDate`, `formatDateTime`, and `formatDuration` (`ru-RU` when `ru`, `en-US` when `en`).

---

### 3.5. Task `tj-ierv.5` — Classification Donut Chart Fix & Executive Analytics Suite

1. **Fix `SegmentPieChart.tsx` (`Classification` / `Классификация диалогов`):**
   - Remove the external radial SVG `label={({ name, percent }) => ...}` prop that caused `"EN 94%"`, `"Target 63%"`, and `"Non-target 37%"` to get clipped by the SVG viewport.
   - Use clean donut geometry (`innerRadius={38}`, `outerRadius={56}`, `paddingAngle={3}`) with a centered summary metric overlay (total conversations / target share) and a **structured breakdown legend below each donut** displaying:
     - Color dot
     - Localized segment name (`Английский (EN)` / `Арабский (AR)` and `Целевые` / `Нецелевые`)
     - Exact conversation count (`658`, `43` / `442`, `259`)
     - Percentage badge (`93.9%`, `6.1%` / `63.1%`, `36.9%`)
   - Guarantee zero text clipping at all desktop/tablet/mobile widths.

2. **Add `EscalationReasonsChart.tsx` (`Причины эскалаций / Escalation Reasons Breakdown`):**
   - Group raw `data.escalation_reasons` into 5 clear business categories:
     1. *КП, опт и комплексные заказы / Quotations & Bulk Orders*
     2. *Запрос менеджера или звонка / Human Call & Manager Request*
     3. *Доставка, сборка и спецусловия / Delivery, Assembly & Terms*
     4. *Нестандартный товар / Вне каталога / Custom & Out-of-Catalog*
     5. *Срочные вопросы и претензии / Urgent & Complaints*
   - Render horizontal progress bars with counts and percentages, plus a collapsible/scrollable list of top specific reasons.

3. **Add `FunnelEfficiencyChart.tsx` (`Воронка продаж и операционные KPI / Sales Funnel & Operational KPIs`):**
   - Visualize the 4-step conversion funnel (`Всего диалогов / Total` → `Целевые / Target` → `Передано менеджеру / Escalated` → `Сделки (Noor + Менеджеры) / Deals Won`) with conversion percentages between stages.
   - Display secondary operational metrics already returned by `DashboardMetrics`:
     - `Средний чек / Avg Deal Value` (`AED`)
     - `Новые / Повторные клиенты / New vs Returning`
     - `Средняя длина диалога / Avg Length` (messages)
     - `Расход AI / LLM Spend` (`$ USD`)
     - `Оценка клиентов и NPS / Feedback & NPS` (`Overall /5`, `Delivery /5`, `NPS`).

---

## 4. Acceptance Criteria (`AC01`–`AC12`)

- **AC01 (KB Seeding & Onboarding):** `POST /api/v1/admin/knowledge-base/seed-defaults` (and auto-seeding when active non-QA KB is empty) populates the 8 canonical Treejar KB entries with embeddings; synthetic `QA disposable...` entries are hidden by default.
- **AC02 (Bot Rules Seeding & Archive Filter Fix):** `POST /api/v1/admin/bot-rules/seed-defaults` populates the 7 canonical Treejar bot behavior rules with embeddings; selecting `status="archived"` in `BotRulesView` / `list_admin_bot_rules` returns archived rules instead of `0` rows.
- **AC03 (Pinned RAG Safety):** `src/models/product.py`, `src/rag/embeddings.py`, `src/rag/pipeline.py`, and `src/schemas/product.py` remain completely unmodified (SHA256 pins intact).
- **AC04 (AI Quality Controls Default Criteria):** `AIQualityControlsConfig` exposes populated default criteria dictionaries for `bot_qa`, `manager_qa`, and `red_flags` (backfilling empty `{}` on read), and `AIQualityControlsPanel` renders interactive checkboxes for each criterion.
- **AC05 (AI Quality Controls Manual & Scheduled Wiring):** Manual Bot QA and Manager QA triggers pass `gate.model`, `gate.transcript_mode`, `gate.cache_telemetry_enabled`, and `criteria` to the evaluators and enforce daily call/budget limits; 1-click "Enable Manual Mode" works from the UI.
- **AC06 (AI Quality Controls Business UX):** Developer-only internal notes in `AIQualityControlsPanel` are replaced by localized business explanations of the 3 QA contours while preserving test hooks.
- **AC07 (Instant Custom Tooltips & Section Guides):** `InfoTooltip` renders custom popovers on hover/focus/click with `<100ms` transition (no native `title` delay) and is present with `SectionGuideBanner` across all 11 dashboard views, metric tiles, charts, and form fields.
- **AC08 (Global Header Search & Reset Preview Card):** The top header search input filters/navigates across views, and `Reset preview` in `ConversationsView` renders a structured UI card instead of `window.alert(JSON)`.
- **AC09 (Complete RU Localization):** With `RU` selected in the header language switcher, 100% of navigation, headers, charts (`Динамика диалогов`, `Классификация диалогов`, `По языкам`, `Целевые и нецелевые`, `Продажи и эскалации`), buttons, forms, `AIQualityControlsPanel`, and tooltips render in Russian with zero untranslated English UI labels.
- **AC10 (Complete EN Localization):** With `EN` selected in the header language switcher, 100% of navigation, headers, charts, buttons, forms, `AIQualityControlsPanel`, and tooltips render in English with zero untranslated Russian UI labels.
- **AC11 (Bug-Free Classification Donut Chart):** `SegmentPieChart.tsx` renders `By Language` and `Target vs Non-target` donuts without radial label clipping at any viewport width, showing exact counts and percentages in structured legend rows below each donut.
- **AC12 (New Executive Charts & Full Verification):** `OverviewView` renders `EscalationReasonsChart` and `FunnelEfficiencyChart` using live `DashboardMetrics` fields; `npm run build` / `npm run lint` in `frontend/admin`, all `frontend/admin/tests/*.mjs` scripts, `uv run ruff check`, `uv run mypy src/`, and `uv run pytest` pass.
