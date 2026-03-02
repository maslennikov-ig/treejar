# Spec: Week 7 (Admin Panel & Metrics)

## Core Objective
Deliver a comprehensive back-office administrative interface for Noor AI Seller.
This interface allows business owners to manage system prompts, debug database issues visually,
review system configurations (LLM models/thresholds), and track overall platform performance metrics.

## Requirements from Product Plan
Based on `docs/task-plan.md` (Week 7: 32 hours):

1. **SQLAdmin Extension Integration:**
   - Visual CRUD representation of 7 tables (`conversations`, `messages`, `products`, `knowledge_base`, `quality_reviews`, `escalations`, `system_configs`).
   - Read-only or restricted updates as necessary, with robust relationships.
   - Built-in data export logic if supported by SQLAdmin natively.

2. **System Prompt Management API:**
   - Table `system_prompts` storing textual prompt components (e.g., stages, rules, core identity).
   - Versioning logic (soft-delete old prompts or maintaining historical keys).
   - Endpoints: `GET /api/v1/admin/prompts/`, `PUT /api/v1/admin/prompts/{name}`.

3. **Metrics Tracker API:**
   - Endpoint: `GET /api/v1/admin/metrics/`.
   - Calculate 17 metric values (defined in `docs/metrics.md`):
     - Volume (daily/weekly/monthly active conversations).
     - Classification (language split En/Ar, Segment dispersion).
     - Escalation (total count, breakdown by 18 triggers - assuming JSON extraction).
     - Sales (deals won, conversion %, avg check).
     - Quality (message speed).
     - LLM Usage (approx. cost proxy based on tokens).

4. **Settings Configuration API:**
   - Endpoints for `SystemConfig`: `GET /api/v1/admin/settings/`, `PATCH /api/v1/admin/settings/`.
   - Modifying runtime thresholds (default language, escalation limit, follow-up window, LLM router selections).

## Security & Architectural Constraints
- Fast API router endpoints must reside under `/api/v1/admin/`.
- Admin API endpoints MUST require authentication.
- Admin Panel GUI (SQLAdmin) must require HTTP Basic Auth or session tokens checking `admin_username` / `admin_password` from `src.core.config`.
- Metrics generation must be heavily optimized using native PostgreSQL grouping/window functions (avoid loading entire tables in python memory).

## Out of Scope
- Building a custom React/Next.js frontend. The requirement dictates the backend side of the API, alongside building the backend-rendered `sqladmin` views. 
