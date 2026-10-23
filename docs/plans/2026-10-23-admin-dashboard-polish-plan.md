# Implementation Plan: Admin Dashboard (`/dashboard/`) Polish, Seeding, AI Quality Wiring, Localization & Charts (`tj-ierv`)

- **Date:** 2026-10-23
- **Parent Epic:** `tj-ierv`
- **Specification:** `docs/specs/admin-dashboard-polish/spec.md` (`AC01`–`AC12`)
- **Child Tasks:**
  - `tj-ierv.1` — Knowledge Base & Bot Behavior Rules canonical Treejar seeding, archived-filter bugfix, and guided onboarding (`AC01`, `AC02`, `AC03`)
  - `tj-ierv.2` — AI Quality Controls (`iQualityControls`) backend wiring, default criteria toggles, budget/retry enforcement, and 1-click manual activation (`AC04`, `AC05`)
  - `tj-ierv.3` — Instant (`<100ms`) custom popover tooltips (`?`), section onboarding banners across all 11 views, and wired header search (`AC06`, `AC07`, `AC11`, `AC12`)
  - `tj-ierv.4` — Complete `RU | EN` bilingual localization with header language switcher and locale-aware formatting (`AC08`, `AC12`)
  - `tj-ierv.5` — Classification donut chart clipping fix (`SegmentPieChart`) and executive analytics charts (`EscalationReasonsChart` & `FunnelEfficiencyChart`) (`AC09`, `AC10`, `AC12`)

---

## 0. Hard Constraints & Protected Files

> [!CAUTION]
> **DO NOT MODIFY** any of the 4 files pinned by `scripts/corpus_bridge/semantic_catalog_evidence.py`:
> - `src/models/product.py`
> - `src/rag/embeddings.py`
> - `src/rag/pipeline.py`
> - `src/schemas/product.py`
>
> Modifying even a single whitespace byte in those files breaks `tests/test_semantic_catalog_canary_pack.py` (`pinned_code_sha256` check).

---

## 1. Execution Topology & File Ownership

Because `frontend/admin/src/App.tsx` is a shared entrypoint across UI tasks, execute in two clean waves or keep `App.tsx` integration coordinated:

- **Wave 1 (Backend — `tj-ierv.1` + `tj-ierv.2`):**
  - `tj-ierv.1` owns:
    - `src/services/admin_knowledge_base.py`
    - `src/api/v1/admin_knowledge_base.py`
    - `src/services/admin_bot_rules.py`
    - `src/api/v1/admin_bot_rules.py`
    - `src/services/canonical_admin_seed.py` (new module for canonical KB + Bot Rules seed catalog and idempotent upserts)
    - `tests/test_admin_knowledge_base_service.py`
    - `tests/test_admin_bot_rules_service.py`
  - `tj-ierv.2` owns:
    - `src/quality/config.py`
    - `src/quality/service.py`
    - `src/quality/evaluator.py`
    - `src/quality/manager_evaluator.py`
    - `src/quality/job.py`
    - `src/quality/manager_job.py`
    - `src/services/admin_crm.py`
    - `src/api/v1/admin.py`
    - `src/api/v1/admin_crm.py`
    - `src/services/dashboard_metrics.py`
    - `src/schemas/admin.py`
    - `tests/test_quality_config.py`
    - `tests/test_admin_crm_service.py`
    - `tests/test_dashboard_metrics.py`
- **Wave 2 (Frontend — `tj-ierv.3` + `tj-ierv.4` + `tj-ierv.5`):**
  - `tj-ierv.4` + `tj-ierv.3` foundation:
    - `frontend/admin/src/i18n.tsx` (new: `LanguageProvider`, `useI18n()`, `RU`/`EN` dictionary, locale formatters)
    - `frontend/admin/src/components/HelpTooltip.tsx` (new: instant `<50ms` hover/focus/click popover tooltip + `SectionInfoBanner`)
  - `tj-ierv.5` charts:
    - `frontend/admin/src/components/charts/SegmentPieChart.tsx`
    - `frontend/admin/src/components/charts/EscalationReasonsChart.tsx` (new)
    - `frontend/admin/src/components/charts/FunnelEfficiencyChart.tsx` (new)
    - `frontend/admin/src/components/charts/ConversationsChart.tsx`
    - `frontend/admin/src/components/charts/SalesBarChart.tsx`
  - Integrated views (`tj-ierv.1`..`tj-ierv.5`):
    - `frontend/admin/src/types.ts`
    - `frontend/admin/src/api.ts`
    - `frontend/admin/src/components/AIQualityControlsPanel.tsx`
    - `frontend/admin/src/components/OperatorCenter.tsx`
    - `frontend/admin/src/App.tsx`
    - `frontend/admin/tests/*.mjs`
    - `tests/test_admin_dashboard_frontend.py`

---

## 2. Step-by-Step Task Plans

### Task 1 (`tj-ierv.1`): Knowledge Base & Bot Behavior Rules Seeding, Bugfix & Guided Onboarding (`AC01`, `AC02`, `AC03`)

#### 1.1 Fix Archived Filter Bug in `src/services/admin_bot_rules.py` (`AC02`)
- In `list_admin_bot_rules` (`src/services/admin_bot_rules.py:92-125`):
  - Currently:
    ```python
    if not include_archived:
        filters.append(BotBehaviorRule.archived_at.is_(None))
    if normalized_status is not None:
        filters.append(BotBehaviorRule.status == normalized_status)
    ```
  - Change to:
    ```python
    if normalized_status == "archived":
        filters.append(BotBehaviorRule.status == "archived")
    else:
        if not include_archived:
            filters.append(BotBehaviorRule.archived_at.is_(None))
        if normalized_status is not None:
            filters.append(BotBehaviorRule.status == normalized_status)
    ```
  - Write regression test in `tests/test_admin_bot_rules_service.py` verifying `list_admin_bot_rules(db, status="archived", include_archived=False)` returns archived rules.

#### 1.2 Create Canonical Seed Catalog in `src/services/canonical_admin_seed.py` (`AC01`, `AC03`)
- Create `src/services/canonical_admin_seed.py` containing:
  1. **Canonical Knowledge Base Articles (`CANONICAL_KB_ARTICLES`):**
     - Parse `docs/faq.md` (Q1–Q19) + structured policies from `docs/company-info.md` into clean, structured `KnowledgeBaseCreateRequest`-compatible entries across categories `faq`, `policy`, `delivery`, `warranty`, `payment`, `showroom`, `b2b`:
       - Delivery & Installation policy (UAE emirates coverage, 3–5 business days in Dubai/Sharjah/Ajman, 5–7 days in Abu Dhabi/other emirates, free assembly included).
       - Returns, Exchange & Warranty policy (7-day return window in original packaging, 1–5 year manufacturer warranty depending on category, defective item replacement).
       - Payment & VAT policy (all catalog prices exclude 5% UAE VAT; payment via Bank Transfer, Payment Link, Visa/Mastercard, Cash/Card on Delivery, Corporate Proforma Invoice / LPO).
       - Showroom, Warehouse & Working Hours (Dubai showroom/office location, Mon–Sat 9:00–18:00 GST `Asia/Dubai`, viewing samples before bulk purchase).
       - Bulk / B2B & Custom Project Orders (20+ units volume tier discounts, custom dimensions/finishes/bespoke joinery, BOQ/floor-plan quoting, dedicated account manager handoff).
       - All remaining FAQ topics from `docs/faq.md` (ergonomic chair adjustments, acoustic pods installation/ventilation/power, sit-stand desks dual-motor specs, fire-resistant safes/lockers, stock availability vs pre-order lead time).
     - `sync_canonical_knowledge_base(db: AsyncSession, embedding_engine: EmbeddingEngine, *, actor: str) -> dict[str, int]`:
       - Idempotently upserts by `(source="canonical_faq_seed", category, title)`.
       - Restores soft-deleted canonical rows if previously deleted, updates `content`, regenerates embeddings when content changed or `embedding is None`, and returns `{"created": ..., "updated": ..., "unchanged": ..., "total_active": ...}`.
  2. **Canonical Bot Behavior Rules (`CANONICAL_BOT_RULES`):**
     - Define the 8 canonical Treejar operating rules (`AC03`):
       1. `UAE 5% VAT dual pricing disclosure` (`scope="pricing_vat"`, `priority=95`, `hard_constraint=True`)
       2. `Deterministic package math & budget verdicts` (`scope="pricing_vat"`, `priority=92`, `hard_constraint=True`)
       3. `Canonical product links only (no r2.dev media links)` (`scope="catalog_links"`, `priority=90`, `hard_constraint=True`)
       4. `Bulk order (20+ units / wholesale discount) handoff with 2-3 immediate catalog options + 1 brief question` (`scope="handoff_b2b"`, `priority=88`, `hard_constraint=True`)
       5. `Custom / bespoke furniture handoff with closest standard alternatives` (`scope="handoff_custom"`, `priority=86`, `hard_constraint=True`)
       6. `Out-of-catalog sourcing notification without freezing conversation` (`scope="sourcing_out_of_catalog"`, `priority=84`, `hard_constraint=True`)
       7. `No hallucinated stock, delivery fees, or unverified specs` (`scope="grounding"`, `priority=90`, `hard_constraint=True`)
       8. `Concise consultative tone & single clarifying question` (`scope="tone_consultation"`, `priority=75`, `hard_constraint=False`)
     - `sync_canonical_bot_behavior_rules(db: AsyncSession, embedding_engine: EmbeddingEngine, *, actor: str) -> dict[str, int]`:
       - Idempotently upserts by `(source_type="canonical_default", scope, title)`, generates embeddings, sets `status="active"`, and returns `{"created": ..., "updated": ..., "unchanged": ..., "total_active": ...}`.

#### 1.3 Expose Admin API Endpoints (`AC01`, `AC03`)
- In `src/api/v1/admin_knowledge_base.py`:
  - Add `POST /api/v1/admin/knowledge-base/sync-canonical` calling `sync_canonical_knowledge_base`.
- In `src/api/v1/admin_bot_rules.py`:
  - Add `POST /api/v1/admin/bot-rules/sync-canonical` calling `sync_canonical_bot_behavior_rules`.
- Add unit/service tests in `tests/test_admin_knowledge_base_service.py` and `tests/test_admin_bot_rules_service.py`.

---

### Task 2 (`tj-ierv.2`): AI Quality Controls (`iQualityControls`) Backend Wiring (`AC04`, `AC05`)

#### 2.1 Populate Default Criteria Catalog & Spend/Execution Summary in `src/quality/config.py` (`AC04`)
- Define canonical default criteria dictionaries in `src/quality/config.py`:
  - `DEFAULT_BOT_QA_CRITERIA: dict[str, bool] = {"rule_1_11_core": True, "grounding_strict": True, "vat_dual_price_check": True, "handoff_completeness": True}`
  - `DEFAULT_MANAGER_QA_CRITERIA: dict[str, bool] = {"response_sla": True, "completeness": True, "courtesy_tone": True, "closing_next_step": True}`
  - `DEFAULT_RED_FLAGS_CRITERIA: dict[str, bool] = {"missing_handoff": True, "hallucinated_fact": True, "unanswered_budget_question": True, "customer_frustration": True}`
- In `_parse_scope_config` and `_default_ai_quality_controls`:
  - Merge default criteria with stored `criteria` so every scope always exposes all canonical keys (preserving any explicit `False` override saved by the operator).
- Add a helper in `src/quality/config.py` (or `src/quality/service.py`) to compute live daily usage and spend:
  - `get_ai_quality_runtime_status(db: AsyncSession, config: AIQualityControlsConfig) -> dict[str, Any]` returning per-scope `calls_today`, `estimated_spend_cents_today`, `last_run_at`, `last_error` so the UI can display real usage next to the configured limits.

#### 2.2 Wire Manual QA Triggers to `AIQualityScopeGate` Settings (`AC04`)
- In `src/services/admin_crm.py`:
  - `run_admin_bot_quality_review`:
    - Capture `gate = await require_admin_ai_quality_manual_gate(db, scope="bot_qa")`.
    - Pass `model=gate.model`, `transcript_mode=gate.transcript_mode`, `cache_telemetry_enabled=gate.cache_telemetry_enabled`, `criteria=gate.criteria`, `retry=gate.retry`, `alert_on_failure=gate.alert_on_failure` into `evaluate_conversation(...)`.
  - `run_admin_manager_quality_review`:
    - Capture `gate = await require_admin_ai_quality_manual_gate(db, scope="manager_qa")`.
    - Pass `model=gate.model`, `transcript_mode=gate.transcript_mode`, `cache_telemetry_enabled=gate.cache_telemetry_enabled`, `criteria=gate.criteria`, `retry=gate.retry`, `alert_on_failure=gate.alert_on_failure` into `evaluate_manager_conversation(...)`.
- In `src/api/v1/admin.py`:
  - `evaluate_admin_manager_review`:
    - Capture `gate = await require_admin_ai_quality_manual_gate(db, scope="manager_qa")` and forward `model=gate.model` and `criteria=gate.criteria` to `evaluate_manager_conversation(...)`.

#### 2.3 Enforce `daily_budget_cents`, `retry`, `alert_on_failure`, and `criteria` (`AC04`)
- In `src/quality/evaluator.py` and `src/quality/manager_evaluator.py`:
  - Accept optional `criteria: Mapping[str, bool] | None = None`, `retry: int = 1`, `alert_on_failure: bool = False`.
  - Wrap LLM call with up to `max(1, retry)` attempts on transient provider failure.
  - Include enabled/disabled criteria instructions in the judge prompt so toggling a criterion off in `/dashboard/` actually affects evaluation.
  - When all retries fail and `alert_on_failure=True`, trigger Telegram alert notification via `TelegramClient` / `notify_escalation`.
- In `src/quality/job.py` and `src/quality/manager_job.py`:
  - Enforce `daily_budget_cents` by comparing today's accumulated quality evaluation cost against `daily_budget_cents` (using model token cost or conservative per-call estimate recorded in `system_configs` / `quality_reviews`) and skipping when budget is reached.

#### 2.4 Add Quick-Enable Manual Mode & Clear Error Messaging (`AC05`)
- In `frontend/admin/src/components/AIQualityControlsPanel.tsx` and `OperatorCenter.tsx`:
  - Add a 1-click button `"Enable Manual Mode for All Scopes"` (`"Включить ручной режим (Manual)"`) that updates `bot_qa.mode`, `manager_qa.mode`, and `red_flags.mode` to `"manual"` (unless already `"scheduled"`) and saves immediately.
  - When a manual `"Bot QA"` or `"Evaluate"` action returns HTTP 409 because the scope is `disabled`, show an inline actionable notice with a `"Switch to Manual & Run"` button.

---

### Task 3 (`tj-ierv.3`): Instant (`<100ms`) Custom Tooltips (`?`), Section Onboarding Banners & Wired Header Search (`AC06`, `AC07`, `AC11`, `AC12`)

#### 3.1 Create `frontend/admin/src/components/HelpTooltip.tsx` (`AC06`, `AC07`)
- Build two reusable components:
  1. `<HelpTooltip text={...} title={...} />`:
     - Renders an accessible `<button type="button" aria-label={...}>?</button>` badge (`h-4 w-4 rounded-full`).
     - Opens immediately (`0ms` delay, `<50ms` CSS transition) on `onMouseEnter`, `onFocus`, and `onClick` (for touch/mobile).
     - Closes on `onMouseLeave`, `onBlur`, or `Escape` key.
     - Automatically positions popover (`z-50 w-72 rounded-xl border border-slate-700 bg-slate-900 p-3 text-xs leading-relaxed text-slate-100 shadow-xl`) so it never clips off-screen.
     - Zero native `title="..."` attributes used for `?` icons.
  2. `<SectionInfoBanner title={...} description={...} howItWorks={...} runtimeConnection={...} actions={...} storageKey={...} />`:
     - Renders a clean collapsible/expandable explanation card at the top of each view showing:
       - What this section does
       - How it connects to the live Noor bot runtime (`src/llm/message_processor.py`, `src/rag/pipeline.py`, `src/quality/*`)
       - Quick action buttons (e.g., `"Sync Canonical Treejar FAQ"`, `"Load Default Treejar Rules"`, `"Enable Manual Mode"`).

#### 3.2 Add Contextual `?` Tooltips & Section Banners Across All 11 Views (`AC06`, `AC07`)
- Add `<SectionInfoBanner />` and `<HelpTooltip />` across all 11 views in `App.tsx`, `OperatorCenter.tsx`, and `AIQualityControlsPanel.tsx`:
  1. `Overview` (KPI cards: Conversations, Sales, Conversion, Avg Order, Quality Score, Escalations; charts: Conversations, Sales Funnel, Classification, Escalation Reasons, Funnel Efficiency)
  2. `Inbox` (`Входящие`)
  3. `Conversations` (`Диалоги`)
  4. `Bot Rules` (`Правила бота`)
  5. `Knowledge Base` (`База знаний`)
  6. `Prompts` (`Промпты`)
  7. `Settings` (`Настройки` + `AIQualityControlsPanel`)
  8. `Analytics` (`Аналитика`)
  9. `Quality` (`Качество`)
  10. `Logs` (`Логи`)
  11. `Reset Data` (`Сброс данных`)

#### 3.3 Wire Header Search Input & Replace `globalThis.alert` in Reset Preview (`AC11`)
- In `frontend/admin/src/App.tsx`:
  - Bind the header search `<input>` (currently a dead element around line 319) to `globalSearchQuery` state:
    - Pressing `Enter` or typing filters the active list view (`Conversations`, `Inbox`, `Knowledge Base`, `Bot Rules`, `Logs`) or offers a quick jump to matching conversations/KB/rules.
  - Replace `globalThis.alert(JSON.stringify(preview, null, 2))` in `handleResetPreview` (line 551) with a structured inline preview card inside the `Reset Data` section showing counts per table (`conversations`, `messages`, `quality_reviews`, etc.), cutoff timestamp, and confirmation state.

---

### Task 4 (`tj-ierv.4`): Complete `RU | EN` Localization & Header Language Switcher (`AC08`, `AC12`)

#### 4.1 Create `frontend/admin/src/i18n.tsx` (`AC08`)
- Implement `Language = 'ru' | 'en'` context (`LanguageProvider`, `useI18n()`):
  - Persist selection in `localStorage.getItem('treejar_admin_lang')` (default `'ru'`).
  - Provide complete translation dictionaries (`translations.ru`, `translations.en`) covering:
    - Sidebar navigation items (`Обзор` / `Overview`, `Входящие` / `Inbox`, `Диалоги` / `Conversations`, `Правила бота` / `Bot Rules`, `База знаний` / `Knowledge Base`, `Промпты` / `Prompts`, `Настройки` / `Settings`, `Аналитика` / `Analytics`, `Качество` / `Quality`, `Логи` / `Logs`, `Сброс данных` / `Reset Data`)
    - Header controls (Period selector, Search placeholder, Refresh button, Language toggle `RU | EN`, Live status badge)
    - Overview KPI cards, chart titles, legends, tooltips, and axis labels
    - Operator Center (`Inbox`, `Knowledge Base`, `Bot Rules`, candidate approval queue, conversation drawer, manual takeover, Bot QA, Manager QA)
    - `AIQualityControlsPanel` (all labels, scope descriptions, criteria names, buttons, status pills, tooltips)
    - `Conversations`, `Prompts`, `Settings`, `Analytics`, `Quality`, `Logs`, `Reset Data` views
  - Provide locale-aware date/number formatters (`ru-RU` when `lang === 'ru'`, `en-US` when `lang === 'en'`).

#### 4.2 Add `RU | EN` Toggle in Header (`App.tsx`)
- Render a clean segmented pill `RU | EN` in the top header bar next to the period selector.
- Ensure switching `RU` ↔ `EN` updates all 11 views, charts, and `AIQualityControlsPanel` immediately without page reload.

---

### Task 5 (`tj-ierv.5`): Classification Chart Fix (`SegmentPieChart`) & Executive Charts (`EscalationReasonsChart`, `FunnelEfficiencyChart`) (`AC09`, `AC10`, `AC12`)

#### 5.1 Redesign `frontend/admin/src/components/charts/SegmentPieChart.tsx` (`AC09`)
- Remove external radial SVG `label={({ name, percent }) => ...}` props from `<Pie>` so text never overflows or gets sliced by SVG bounds (`"4%"`, `"Target 63%"`, `"Non-targe"`).
- Render two clean sub-cards (stacked vertically or responsive grid with centered donut ring `innerRadius={36}`, `outerRadius={54}` and total count in the center) paired with an explicit progress-bar legend beside/below each donut showing:
  - Color indicator dot
  - Full localized label (`Английский (EN)` / `English (EN)`, `Арабский (AR)` / `Arabic (AR)`, `Целевые` / `Target`, `Нецелевые` / `Non-target`, etc.)
  - Exact count (`16`) and percentage (`94.1%`)
  - Mini progress bar fill (`w-full h-1.5 rounded-full`).

#### 5.2 Enrich Backend Dashboard Metrics in `src/services/dashboard_metrics.py` & `src/schemas/admin.py` (`AC10`)
- Extend `DashboardMetricsResponse` (`src/schemas/admin.py`) and `calculate_dashboard_metrics` (`src/services/dashboard_metrics.py`) with two non-breaking fields (with defaults so existing callers remain compatible):
  - `escalation_by_reason: dict[str, int] = Field(default_factory=dict)` — aggregated counts from ` escalations.reason` for the selected period.
  - `sales_stage_distribution: dict[str, int] = Field(default_factory=dict)` — aggregated counts of conversations by current `sales_stage` (`greeting`, `qualifying`, `solution`, `quoting`, `closing`, `handed_off`, etc.).
- Add unit tests in `tests/test_dashboard_metrics.py`.

#### 5.3 Create New Executive Charts (`AC10`)
1. `frontend/admin/src/components/charts/EscalationReasonsChart.tsx`:
   - Displays breakdown of escalation reasons (`human_requested`, `order_confirmation`, `bulk_or_custom`, `frustration`, `out_of_catalog`, etc.) with localized labels, counts, percentages, and horizontal bar visualization, plus a clean empty state when `total_escalations === 0`.
2. `frontend/admin/src/components/charts/FunnelEfficiencyChart.tsx`:
   - Displays stage-by-stage funnel conversion & drop-off across `Conversations → Engaged → Qualified / Cart → Escalated / Quoted → Closed Order`, plus inbound channel distribution (`WhatsApp`, `Zoho`, etc.) and quality score band breakdown (`Excellent`, `Good`, `Needs Work`).
3. Integrate both charts into the `Overview` and `Analytics` views in `frontend/admin/src/App.tsx`.

---

## 3. Verification & Acceptance Gate (`AC12`)

Run all of the following before closing `tj-ierv`:

```bash
export PATH="$HOME/.local/bin:$PATH"

# 1. Frontend unit tests & production bundle build
npm --prefix frontend/admin test
npm --prefix frontend/admin run build

# 2. Backend lint, format, and typecheck
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy src/

# 3. Focused & full pytest suite (including semantic catalog canary pin check)
uv run pytest tests/test_admin_dashboard_frontend.py tests/test_admin_knowledge_base_service.py tests/test_admin_bot_rules_service.py tests/test_quality_config.py tests/test_admin_crm_service.py tests/test_dashboard_metrics.py tests/test_semantic_catalog_canary_pack.py -v --tb=short
uv run pytest tests/ -v --tb=short
```

All tests must pass, `frontend/admin/dist/` must be rebuilt so `/dashboard/` serves the updated bundle, and the 4 pinned files in `scripts/corpus_bridge/semantic_catalog_evidence.py` must remain untouched.
