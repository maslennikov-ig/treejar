# Stage tj-myx7 — Admin Dashboard dead/duplicate controls and filter/audit wiring sweep

- Branch `codex/tj-myx7-admin-controls`, worktree `.worktrees/tj-myx7-admin-controls`,
  base `main` `28cf572` (owner-authorized combined delivery with `tj-p82s`).
- Pinned RAG files (`src/models/product.py`, `src/rag/embeddings.py`,
  `src/rag/pipeline.py`, `src/schemas/product.py`) unchanged vs `main`.

## Root Causes & Delivered Fixes
- **Header BookOpen duplicate (`[data-header-guide-btn]`) & Sidebar theme duplicate (`[data-sidebar-theme-toggle]`)**:
  - Removed `[data-header-guide-btn]` from `App.tsx` (kept `[data-tour-trigger]` «Интерактивный тур» in the header and `[data-nav-item="guide"]` «Справка и инструкции» in the sidebar footer).
  - Removed duplicate `[data-sidebar-theme-toggle]` from `Sidebar.tsx` so theme switching lives solely in the top header.
- **Dead gear / «Администратор» pill -> Interactive Admin Account & Session Menu**:
  - Added `GET /api/v1/admin/session` (`AdminSessionInfoResponse` in `src/schemas/admin.py`, `src/api/v1/admin.py`, session identity persistence in `src/api/admin/auth.py` and `src/main.py`).
  - Replaced static header `<div>` with accessible `[data-admin-account-btn]` + `[data-admin-account-menu]` popover showing auth method (`telegram` / `password` / `session`), identity/actor, quick jumps to Settings, Audit & System Health, SQLAdmin (`/admin/`), and Logout (`/admin/logout`), plus session actions on `SettingsView.tsx`.
- **Header Refresh (`[data-header-refresh-btn]`) & Global Search (`App.tsx`)**:
  - Wired `refreshSignal` from `App.tsx` into all 9 server-backed views; hid refresh and search on static `acceptance` (and refresh on `guide`).
  - Added clear (`[data-header-search-clear]`) and explicit submit (`[data-header-search-submit]`) so typing in header search from `overview`, `catalog`, `reports`, or `settings` jumps straight to filtered conversations.
- **Overview KPI/Chart drilldowns & Conversations filters (`OverviewView.tsx`, `SegmentPieChart.tsx`, `SalesBarChart.tsx`, `ConversationsView.tsx`, `src/services/admin_crm.py`, `src/api/v1/admin_crm.py`)**:
  - Fixed Conversion Rate card, `SegmentPieChart`, and `SalesBarChart` drilldowns to pass `filter: 'deals' | 'target' | 'nontarget'` instead of phantom `status: 'completed'` or `active`/`closed` approximations.
  - Added backend `has_deal`, `target_only`, and `stage=unknown` filters on `/api/v1/admin/crm/customers` & `/conversations`, dismissible `[data-conv-route-filter]` chip, missing `company_details` / `feedback` / `unknown` stages, and real `escalated` status option.
- **Audit filter & deep-link fixes (`AuditSystemView.tsx`, `src/services/admin_crm.py`, `src/api/v1/admin_crm.py`)**:
  - Aligned entity filter options with real audited entities (`bot_behavior_rule` with `bot_rule` compatibility alias, `knowledge_base_candidate`, `admin_session`; removed unused `quality`), added server-side `actor` filter, guarded conversation jump on `entity_id`, and enabled jumps to Bot Rules and Knowledge Base.
- **AI Quality Controls Simple Mode & Light Theme (`AIQualityControlsPanel.tsx`, `AcceptanceDemo.tsx`, `i18n.tsx`)**:
  - Fixed literal `{scope}` interpolation bug on Simple Mode save/error messages, wired per-contour USD budget input across all 3 scopes, added Manager QA & Red Flags Simple Mode selectors, and made `AcceptanceDemo.tsx` light-theme readable.

## Verification
- `cd frontend/admin && npm run lint && npm test && npm run build`: all 15 regression scripts and production build passed.
- `uv run ruff check src/ tests/`, `uv run ruff format --check src/ tests/`, `uv run mypy src/`: passed.
- `uv run pytest tests/test_api_admin.py tests/test_api_admin_auth.py tests/test_telegram_admin_login.py tests/test_admin_crm_api.py tests/test_admin_audit.py tests/test_admin_dashboard_frontend.py tests/test_admin_views_localization.py tests/test_admin_bot_rules_api.py tests/test_admin_knowledge_base_api.py -v --tb=short`: 87 passed, 3 skipped.
- `bash scripts/orchestration/run_process_verification.sh`: passed.
- `docs-reviewed: updated - added stage summary and updated handoff`.
- `graph-reviewed: no-change-needed - bounded admin UI/API wiring within existing modules`.
