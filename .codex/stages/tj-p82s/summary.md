# Stage tj-p82s — Default Overview period to Month with persistence & complete onboarding/guide coverage

- Branch `codex/tj-p82s-dashboard-period` (rebased onto `codex/tj-myx7-admin-controls` off `main` `28cf572`), owner-authorized combined delivery to `main` and `https://noor.starec.ai`.
- Pinned RAG files (`src/models/product.py`, `src/rag/embeddings.py`, `src/rag/pipeline.py`, `src/schemas/product.py`) unchanged vs `main`.

## Delivered Changes
- **Default `month` period + browser `localStorage` persistence (`frontend/admin/src/App.tsx`, `Primitives.tsx`)**:
  - Added `PERIOD_STORAGE_KEY = 'treejar_admin_period'`, `isValidPeriod`, `readStoredPeriod('month')`, and `writeStoredPeriod`. Overview defaults to `'month'` on first visit and restores the last selected period (`'day' | 'week' | 'month' | 'all_time'`) on subsequent visits, with `aria-pressed` on `SegmentedControl`.
- **Full 14-step spotlight tour & complete bilingual Guide (`frontend/admin/src/data/adminGuideData.ts`, `GuideView.tsx`, `i18n.tsx`)**:
  - Expanded `TOUR_TRACKS.full` from 10 to 14 steps covering all 11 workspaces (added `reports`, `settings`, `auditSystem`, and `[data-acceptance-view]` `acceptance`), aligned header tour/playbook copy with the interactive Admin Profile & Session menu (`tj-myx7`), expanded playbooks to 9 (including Telegram manager quote/escalation actions and Self-Test), glossary groups to 5, and FAQs to 8.
- **Cross-branch review refinements (`src/services/admin_audit.py`, `src/services/admin_crm.py`, `ConversationsView.tsx`, `SalesBarChart.tsx`, `OverviewView.tsx`)**:
  - Inferred `AdminActionAudit.actor` from `request.session["admin_actor"]` when omitted so all dashboard mutations record per-admin Telegram/password identity.
  - Added `escalation=any` and `escalation=open` support so `SalesBarChart`, `EscalationReasonsChart`, and the `waiting` quick tab match `dashboard_metrics.py` and open-escalation definitions 1:1.
- **Client portal manual (`docs/reports/2026-10-24-treejar-admin-dashboard-guide.html`)**:
  - Updated and linted with 14-step tour, 9 playbooks, default `Месяц` + remembered period, voice transcripts, editable CRM fields, KB safety preview, Telegram manager workflow, and top-right session/logout menu.

## Verification
- `cd frontend/admin && npm run lint && npm test && npm run build`: 15/15 frontend regression scripts and Vite production build passed.
- `uv run ruff check src/ tests/`, `uv run ruff format --check src/ tests/`, `uv run mypy src/`, admin + manifest `pytest` suites, and `bash scripts/orchestration/run_process_verification.sh`: passed.
- `docs-reviewed: updated - added stage summary, updated handoff and client portal HTML manual, re-pinned traceability manifest`.
- `graph-reviewed: no-change-needed - bounded admin UI/API polish and onboarding data within existing modules`.
