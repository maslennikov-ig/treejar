# Implementation Plan: Week 7 (Admin Panel & Metrics)

## Phase 1: Authentication & SQLAdmin Setup 

**Task 1: Basic Auth for SQLAdmin**
- **File:** `src/api/admin/auth.py`
- **Action:** Create `AdminAuth` class extending `AuthenticationBackend` from `sqladmin`.
- **Validation:** Check `admin_username` and `admin_password` from `src.core.config.settings`.

**Task 2: SQLAdmin Extension & ModelViews**
- **File:** `src/api/admin/views.py`
- **Action:** Register `ModelView` for `Conversation`, `Message`, `Product`, `KnowledgeBase`, `QualityReview`, `Escalation`, `SystemConfig`.
- **File:** `src/main.py`
- **Action:** Mount `sqladmin.Admin` onto the FastAPI app using the `AdminAuth` backend and the SQLAlchemy sync/async engine.
- **Test:** Verify `GET /admin` redirects to login and grants access to tables.

## Phase 2: System Prompts Management

**Task 3: Prompts Database Model**
- **File:** `src/models/system_prompt.py`
- **Action:** Create `SystemPrompt` model (`name`, `content`, `version`, `is_active`).
- **File:** `migrations/versions/xxxx_add_system_prompts.py`
- **Action:** Generate Alembic migration.

**Task 4: Prompts API Endpoints**
- **File:** `src/api/v1/prompts.py` (or `src/api/admin.py`)
- **Action:** Implement `GET /api/v1/admin/prompts/` and `PUT /api/v1/admin/prompts/{name}`. Add to FastAPI router.
- **Integration:** Update `src/llm/engine.py` or `src/llm/prompts.py` to fetch from DB instead of hardcoded strings (using a cache like Redis).

## Phase 3: Configuration & Settings API

**Task 5: Settings API Endpoint**
- **File:** `src/api/v1/admin.py`
- **Action:** Implement `GET /api/v1/admin/settings/` (fetch all `SystemConfig` rows).
- **Action:** Implement `PATCH /api/v1/admin/settings/` (bulk update or point update `SystemConfig` key-value pairs).
- **Test:** Ensure `tests/test_api_admin.py` verifies updates taking effect.

## Phase 4: Metrics Dashboard API

**Task 6: Metrics Calculation Logic**
- **File:** `src/api/v1/metrics.py` (or `src/services/metrics.py`)
- **Action:** Use SQLAlchemy `select()`, `count()`, `func.sum()`, `func.avg()` to calculate:
  - Daily/Weekly/Monthly conversation volume.
  - Conversion rates (Count of Closed Won deals / Total Sales conversations * 100).
  - Escalation counts and triggers (JSON breakdown).
  - Average LLM response times & token costs based on `tokens_in/out` in `messages` table.

**Task 7: Metrics API Endpoint**
- **File:** `src/api/v1/admin.py`
- **Action:** Expose `GET /api/v1/admin/metrics/` returning compiled JSON payload adhering to the structure defined in `docs/metrics.md`.
- **Test:** Add mock data and test that calculations and format match expectations.
