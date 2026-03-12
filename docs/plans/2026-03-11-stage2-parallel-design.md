# Stage 2 Parallel Features — Design Document

**Date:** 2026-03-11
**Scope:** Tasks 1-5 (Weeks 11-12)
**Branch:** `feature/stage2-parallel`

## Context

We are implementing 4 new modules + 1 documentation update for the Noor AI Seller. The specifications are provided in `docs/session-stage2-parallel-prompt.md`. All tasks are independent and can be developed in parallel.

## Design Decisions

### 1. Telegram Client Architecture
**Approach:** Single `TelegramClient` class in `src/integrations/notifications/telegram.py` using `httpx.AsyncClient` with:
- Retry via `tenacity` (3 retries, exponential backoff) — consistent with existing Zoho clients
- Graceful no-op when `telegram_bot_token == ""` — silent skip, no exceptions
- Rate limit awareness: Telegram allows 30 msg/sec, we add 0.05s delay between consecutive sends

**Alternative considered:** Using `python-telegram-bot` library — rejected because it adds a heavy dependency for simple `sendMessage`/`sendDocument` calls. Raw HTTP via `httpx` (already a project dependency) is simpler.

### 2. Notification Service Layer
**Approach:** `src/services/notifications.py` as a thin orchestration layer:
- Accepts domain objects (Conversation, QualityReview) → formats HTML → calls TelegramClient
- Each notification type is a separate function (not a class hierarchy) — matches project style
- HTML formatting for Telegram (`<b>`, `<i>`, `<code>`) — simple, no Markdown escaping issues

### 3. Reports
**Approach:** Reuse queries from `src/services/dashboard_metrics.py` where possible:
- `calculate_dashboard_metrics()` already computes 80% of needed data
- New: top-5 products query (GROUP BY on messages.content with product extraction), rejection reasons aggregation from `escalations.reason`
- Output: both plain text (for Telegram) and JSON (for API) — single `ReportData` Pydantic model

### 4. Product Recommendations
**Approach:** pgvector cosine similarity (already used in RAG pipeline):
- `get_similar_products()` — SQL query using `<=>` operator on `products.embedding`, filtering `is_active=True`
- `get_cross_sell()` — rule-based from `SystemConfig(key="cross_sell_rules")` JSON
- New LLM tool `recommend_products` — returns formatted list for natural conversation

### 5. Referral System
**Approach:** New `Referral` model + Alembic migration:
- Code format: `NOOR-XXXXX` (5 alphanumeric chars) — generated via `secrets.token_urlsafe`
- Discount application: modify existing `apply_discount()` in `src/core/discounts.py` to check for referral discount
- LLM tools: `generate_referral_code` and `apply_referral_code` — simple CRUD wrappers

### 6. Integration Points Summary

| Integration | File | Change |
|---|---|---|
| Escalation → Telegram | `src/integrations/notifications/escalation.py` | Call `notify_escalation()` after DB update |
| Quality → Telegram | `src/quality/job.py` | Call `notify_quality_alert()` when score < 14 |
| Daily summary → Cron | `src/worker.py` | Add `notify_daily_summary` cron (09:00 UTC daily) |
| Weekly report → Cron | `src/worker.py` | Add `generate_weekly_report` cron (Mon 09:00 UTC) |
| Recommendations → LLM | `src/llm/engine.py` | New tool `recommend_products` |
| Referrals → LLM | `src/llm/engine.py` | New tools `generate_referral_code`, `apply_referral_code` |
| API Router | `src/api/v1/router.py` | Add `notifications`, `reports`, `referrals` routers |
| Admin | `src/api/admin/views.py` | Add `ReferralAdmin` ModelView |
| Models | `src/models/__init__.py` | Register `Referral` |
