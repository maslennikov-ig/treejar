# Full CRM Admin Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task.

**Goal:** Replace the operator-facing `/dashboard/` experience with a full Noor CRM admin workspace while keeping `/admin/` SQLAdmin as a technical fallback.

**Architecture:** Keep the current FastAPI admin-session boundary and Vite/React admin app. Add purpose-built authenticated admin APIs for CRM, knowledge base, and audit, then rebuild the React dashboard as a Russian CRM shell around those APIs. Do not add manual WhatsApp compose/send in this version.

**Tech Stack:** FastAPI, SQLAlchemy async ORM, Alembic, Pydantic, PostgreSQL/pgvector, React 19, Vite, TypeScript, Tailwind 4, lucide-react, existing frontend regression scripts.

**Beads Epic:** `tj-40n0`

---

## Implementation Status

- `tj-40n0.1` through `tj-40n0.5` are closed in Beads.
- Backend audit foundation is implemented with `AdminActionAudit`, Alembic migration, recursive secret masking, `AdminActionAuditRead`, audit service, and read-only SQLAdmin fallback view.
- Admin CRM API is mounted under `/api/v1/admin/crm` with authenticated customer list, conversation list/detail/timeline, conversation update, escalation create/close, reset preview/execute, bot/manager QA triggers, and audit readback.
- Admin knowledge-base API is mounted under `/api/v1/admin/knowledge-base` with entries CRUD, soft-delete, preview duplicate/safety/context checks, reindex, candidate queue, approve/reject, and auto-FAQ candidate persistence from manager reply flow.
- Frontend `/dashboard/` is rebuilt as a Russian CRM shell with sidebar, 3-panel clients/dialogues workspace, KB editor/candidate queue, audit table, overview, and existing operator controls kept accessible. Manual WhatsApp compose/send was not added.
- Verification completed so far:
  - `uv run ruff check src/ tests/`
  - `uv run ruff format --check src/ tests/`
  - `uv run mypy src/`
  - `uv run pytest tests/ -v --tb=short -s` (`913 passed, 19 skipped`)
  - `npm run lint` in `frontend/admin`
  - `npm run build` in `frontend/admin`
  - `uv run pytest tests/test_admin_dashboard_frontend.py -v --tb=short -s`
- Note: canonical pytest without `-s` hit a local pytest capture cleanup `FileNotFoundError` before collection; the same full suite passed with capture disabled.
- Note: local Node is `v18.19.1`; Vite/Tailwind packages warn that Node 20+ is expected. Production build passed after installing the platform optional package `@tailwindcss/oxide-linux-x64-gnu@4.2.1` with `--no-save`; no tracked package files changed.
- Follow-up: `npm install` reports existing frontend dependency vulnerabilities (`1 moderate`, `3 high`); tracked separately as Beads task `tj-puk5`.

---

## Execution Rules

- Worktree: `/home/me/code/treejar/.worktrees/codex-full-crm-admin`
- Branch: `codex/full-crm-admin`
- Do not deploy or mutate production without explicit approval.
- Keep `/api/v1/admin/dashboard/*`, manager-review, report, AI quality, payment-reminder, client-self-test, and product-sync admin endpoints backward compatible.
- Log all mutating CRM/admin actions to `AdminActionAudit`.
- Mask secrets/tokens/passwords/API keys in audit payloads.
- Use TDD for backend behavior and frontend regression behavior: write failing tests first, run targeted RED, implement, then run GREEN.
- Keep `/admin/` SQLAdmin as a fallback; do not remove existing views.

## Task 1: Plan And Tracking Contract (`tj-40n0.1`)

**Files:**
- Create: `docs/plans/2026-05-07-full-crm-admin-implementation.md`
- Update: `.beads/issues.jsonl` after Beads export

**Steps:**
1. Create Beads epic `tj-40n0` and child tasks for audit, CRM API, knowledge-base API, frontend, and verification.
2. Save this plan file.
3. Run `bd export -o .beads/issues.jsonl`.
4. Mark `tj-40n0.1` complete after the plan is tracked.

**Acceptance:**
- Plan file exists and Beads has the epic plus child tasks.
- Git status shows only intentional plan/Beads changes at this point.

## Task 2: Admin Action Audit Foundation (`tj-40n0.2`)

**Files:**
- Create: `src/models/admin_action_audit.py`
- Modify: `src/models/__init__.py`
- Create: `migrations/versions/2026_05_07_add_admin_action_audits.py`
- Modify: `src/schemas/admin.py`
- Create: `src/services/admin_audit.py`
- Modify: `src/api/admin/views.py`
- Test: `tests/test_admin_audit.py`
- Test: `tests/test_admin_views_localization.py`

**Behavior:**
- Add `admin_action_audits` table with UUID id, `actor`, `action`, `entity_type`, `entity_id`, `request_path`, `before`, `after`, `metadata`, `created_at`.
- `before`, `after`, and `metadata` are JSON columns.
- Add indexes on `created_at`, `action`, `entity_type`, and `entity_id`.
- Add `AdminActionAuditRead` schema.
- Add `log_admin_action(db, *, actor, action, entity_type, entity_id, request_path, before, after, metadata)` service.
- Add recursive masking for keys containing `password`, `secret`, `token`, `api_key`, `authorization`, `cookie`, `session`.
- Add read-only SQLAdmin view named `Аудит действия`.

**Tests:**
- RED: `uv run pytest tests/test_admin_audit.py tests/test_admin_views_localization.py -q`
- GREEN: same command passes after implementation.

## Task 3: Admin CRM API (`tj-40n0.3`)

**Files:**
- Modify: `src/schemas/admin.py`
- Create: `src/services/admin_crm.py`
- Create: `src/api/v1/admin_crm.py`
- Modify: `src/api/v1/admin.py` or `src/api/v1/router.py` to mount under `/api/v1/admin/crm`
- Test: `tests/test_admin_crm_api.py`

**Read Endpoints:**
- `GET /api/v1/admin/crm/customers`
  - Returns `PaginatedResponse[AdminCustomerListItem]`.
  - Groups by phone, ordered by latest activity.
  - Supports `q`, `status`, `sales_stage`, `language`, `escalation_status`, `deal_status`, `segment`, `date_from`, `date_to`, `page`, `page_size`.
- `GET /api/v1/admin/crm/conversations`
  - Returns `PaginatedResponse[AdminConversationListItem]`.
  - Supports search by phone, customer name, Zoho contact/deal id, sale order id/number in metadata, and source/UTM values.
- `GET /api/v1/admin/crm/conversations/{conversation_id}`
  - Returns `AdminConversationDetail` with conversation fields, ordered `AdminTimelineMessage[]`, summary, quality reviews, escalations, manager reviews, feedback, outbound audits, source attribution, order metadata, and audit tail.
- `GET /api/v1/admin/crm/audit`
  - Returns paginated `AdminActionAuditRead[]` filtered by action/entity/date.

**Action Endpoints:**
- `PATCH /api/v1/admin/crm/conversations/{conversation_id}`
  - Updates `status`, `sales_stage`, `escalation_status`, `customer_name`, `deal_status`.
  - Logs audit with before/after.
- `POST /api/v1/admin/crm/conversations/{conversation_id}/escalations`
  - Creates or updates escalation assignment/status/reason/notes.
  - Logs audit.
- `POST /api/v1/admin/crm/conversations/{conversation_id}/reset/preview`
  - Uses existing reset preview service and does not mutate.
- `POST /api/v1/admin/crm/conversations/{conversation_id}/reset/execute`
  - Executes reset only for the selected conversation phone and logs audit.
- `POST /api/v1/admin/crm/conversations/{conversation_id}/bot-qa`
  - Runs existing bot QA review creation path when possible; returns 409 if already reviewed.
- `POST /api/v1/admin/crm/escalations/{escalation_id}/manager-qa`
  - Delegates to existing manager review evaluation.

**Tests:**
- Auth: anonymous requests return 401.
- List/detail: include messages, quality, escalation, manager review, feedback, outbound audit, metadata.
- Filters/search: phone, name, Zoho id, sale order metadata, segment.
- Mutations: update state and create audit rows.
- Reset preview is non-mutating; reset execute creates audit.

**Commands:**
- RED/GREEN targeted: `uv run pytest tests/test_admin_crm_api.py -q`
- Compatibility: `uv run pytest tests/test_api_admin.py tests/test_api_conversations.py -q`

## Task 4: Admin Knowledge Base API (`tj-40n0.4`)

**Files:**
- Modify: `src/models/knowledge_base.py` if soft-delete fields are needed
- Create migration if model changes
- Modify: `src/schemas/admin.py`
- Create: `src/services/admin_knowledge_base.py`
- Create: `src/api/v1/admin_knowledge_base.py`
- Mount under `/api/v1/admin/knowledge-base`
- Test: `tests/test_admin_knowledge_base_api.py`

**Behavior:**
- Add `is_deleted` and `deleted_at` if not already present.
- `GET /api/v1/admin/knowledge-base/` lists/searches KB entries by `q`, `source`, `category`, `language`, `is_auto_generated`, `include_deleted`.
- `GET /api/v1/admin/knowledge-base/{entry_id}` returns one entry.
- `POST /api/v1/admin/knowledge-base/preview` validates payload and returns duplicate/unsafe/context-specific warnings without saving.
- `POST /api/v1/admin/knowledge-base/` creates entry, generates embedding, logs audit.
- `PATCH /api/v1/admin/knowledge-base/{entry_id}` updates entry, regenerates embedding when content/title changes, logs audit.
- `DELETE /api/v1/admin/knowledge-base/{entry_id}` soft-deletes entry and logs audit.
- `POST /api/v1/admin/knowledge-base/{entry_id}/reindex` regenerates embedding and logs audit.
- `GET /api/v1/admin/knowledge-base/candidates` exposes auto-FAQ candidate-like rows from existing `KnowledgeBase` auto-generated metadata where possible; if no durable candidate table exists, return an empty, typed list and keep approval limited to explicit create/update.

**Tests:**
- Auth for every endpoint.
- CRUD and soft-delete behavior.
- Reindex uses mocked `EmbeddingEngine`.
- Preview surfaces duplicate/unsafe/context-specific warnings.
- Mutating actions write audit rows.

**Commands:**
- RED/GREEN targeted: `uv run pytest tests/test_admin_knowledge_base_api.py tests/test_auto_faq.py -q`

## Task 5: CRM Dashboard Frontend Shell (`tj-40n0.5`)

**Files:**
- Modify: `frontend/admin/src/App.tsx`
- Modify: `frontend/admin/src/index.css`
- Create/modify under `frontend/admin/src/api/`
- Create/modify under `frontend/admin/src/types/`
- Create/modify under `frontend/admin/src/components/`
- Add tests under `frontend/admin/tests/`
- Modify: `tests/test_admin_dashboard_frontend.py`

**Design Direction:**
- Operational, dense, Russian-first CRM UI.
- Sidebar navigation: `Обзор`, `Клиенты и диалоги`, `Очереди`, `База знаний`, `Каталог`, `Качество`, `Отчеты`, `Настройки`, `Аудит`.
- Avoid landing-page/marketing layout.
- No manual WhatsApp compose/send controls.
- Use existing lucide-react icons.
- Keep existing operator controls accessible under relevant tabs.

**Core Views:**
- `Обзор`: KPI tiles and existing charts/report highlights.
- `Клиенты и диалоги`: 3-panel workspace:
  - left: searchable/filterable customer/conversation list;
  - center: full ordered chat/timeline with role, timestamp, text, audio/transcription/media markers;
  - right: inspector with CRM fields, stages, source/UTM, order metadata, quality, escalations, outbound audit, and allowed actions.
- `Очереди`: pending escalations, pending manager reviews, QA candidates.
- `База знаний`: list/search, editor, preview warnings, save-and-index, soft-delete, reindex.
- `Каталог`: existing product sync controls and catalog status.
- `Качество`: AI quality controls and QA actions.
- `Отчеты`: weekly report generation and preview.
- `Настройки`: AI quality/payment reminder controls.
- `Аудит`: searchable audit table.

**Frontend Tests:**
- CRM shell renders all navigation labels.
- Conversation workspace renders list, selected chat timeline, and inspector.
- Dangerous action buttons require confirmation state.
- KB editor renders preview/save/reindex/delete affordances and does not show WhatsApp compose/send.
- Audit table renders action rows.

**Commands:**
- `npm --prefix frontend/admin run lint`
- `uv run pytest tests/test_admin_dashboard_frontend.py -q`

## Task 6: Verification And Closeout (`tj-40n0.6`)

**Files:**
- Update: `.beads/issues.jsonl`
- Update: `.codex/handoff.md` only if stage truth changes materially

**Commands:**
- `uv run ruff check src/ tests/`
- `uv run ruff format --check src/ tests/`
- `uv run mypy src/`
- `env DYLD_FALLBACK_LIBRARY_PATH="${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}" uv run pytest tests/ -v --tb=short`
- `npm --prefix frontend/admin run lint`
- `uv run pytest tests/test_admin_dashboard_frontend.py -q`
- `scripts/orchestration/run_process_verification.sh`

**Closeout:**
- Mark completed Beads child tasks complete.
- Keep any justified defers explicit in Beads and handoff.
- Do not deploy.
