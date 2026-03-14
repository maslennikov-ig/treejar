# Session Prompt: Реализация «Оценка работы менеджеров» (Manager Assessment)

## Контекст

Мы спроектировали фичу **Manager Assessment** — систему автоматической оценки качества работы живых менеджеров после эскалации от AI-бота Noor. Дизайн утверждён, нужно реализовать.

### Проект
- **Backend:** Python 3.12, FastAPI, SQLAlchemy (AsyncPG), PydanticAI
- **БД:** PostgreSQL 16 (pgvector), Redis 7
- **Менеджер зависимостей:** `uv`
- **Тесты:** `pytest`, strict TDD (красный → зелёный → рефакторинг)
- **Стиль:** `ruff`, `mypy --strict`

### Что уже реализовано (релевантное)
- **Quality Evaluator** (`src/quality/evaluator.py`) — LLM-судья для AI-диалогов (15 критериев, шкала 0-30). Использовать как образец архитектуры.
- **Escalation System** (`src/core/escalation.py`, `src/models/escalation.py`) — 18 триггеров, модель Escalation.
- **Wazzup Webhook** (`src/api/v1/webhook.py`, `src/schemas/webhook.py`) — приём сообщений от WhatsApp.
- **Dashboard Metrics** (`src/services/dashboard_metrics.py`) — 17 KPI, `DashboardMetricsResponse`.
- **Weekly Reports** (`src/services/reports.py`) — еженедельные Telegram-отчёты.
- **Conversation Model** (`src/models/conversation.py`) — поле `escalation_status`.
- **Message Model** (`src/models/message.py`) — поле `role` (VARCHAR: user/assistant).

---

## Дизайн-документы (ОБЯЗАТЕЛЬНО прочитать)

1. **`docs/plans/2026-03-13-manager-assessment-design.md`** — полный дизайн: архитектура, схема БД, поток данных, API, компоненты.
2. **`docs/08-manager-evaluation-criteria.md`** — 10 критериев LLM-оценки + 4 количественных метрики.

---

## Что нужно реализовать (10 компонентов)

### Фаза 1: Инфраструктура (компоненты 1-4)

**Компонент 1: Webhook — `isEcho`/`authorType` + роль `manager`**
- Добавить поля `is_echo`, `author_type`, `author_id`, `author_name` в `WazzupIncomingMessage` (schemas/webhook.py)
- В `handle_wazzup_webhook` — маршрутизация по `authorType`: client → role='user', manager → role='manager', bot → игнорировать
- Файлы: `src/schemas/webhook.py`, `src/api/v1/webhook.py`

**Компонент 2: Бот молчит при эскалации**
- В `process_incoming_batch` (`src/services/chat.py`) — проверить `conversation.escalation_status`, если != 'none' → НЕ вызывать LLM, просто сохранить сообщение
- КРИТИЧЕСКИЙ БАГ: сейчас бот отвечает даже после эскалации!
- Файлы: `src/services/chat.py`

**Компонент 3: Manual takeover**
- Если `authorType='manager'` и `escalation_status='none'` → установить `escalation_status='manual_takeover'`, бот останавливается
- Добавить значение `manual_takeover` в `EscalationStatus` enum (если есть) или в допустимые значения
- Файлы: `src/services/chat.py`, `src/schemas/common.py`

**Компонент 4: Миграция — таблица `manager_reviews`**
- Alembic миграция: таблица с полями из дизайн-документа
- SQLAlchemy модель `ManagerReview`
- Связи: `escalation_id` → `escalations(id)`, `conversation_id` → `conversations(id)`
- Unique constraint на `escalation_id` (одна оценка на эскалацию)
- Файлы: `src/models/manager_review.py`, Alembic миграция

### Фаза 2: Оценка (компоненты 5-7)

**Компонент 5: LLM Judge для менеджеров**
- По образцу `src/quality/evaluator.py`, но с 10 критериями из `docs/08-manager-evaluation-criteria.md`
- Промпт: контекст эскалации (причина, триггер) + диалог менеджера (role=manager/user после эскалации)
- Выход: `ManagerEvaluationResult` (по образцу `EvaluationResult`)
- Файлы: `src/quality/manager_evaluator.py`, `src/quality/manager_schemas.py`

**Компонент 6: Количественные метрики**
- Время первого ответа: `first_manager_message.created_at - escalation.created_at`
- Конверсия: проверить `conversation.zoho_deal_id IS NOT NULL`
- Количество сообщений: `COUNT(messages WHERE role='manager')`
- Сумма сделки: `conversation.deal_amount`
- Файлы: `src/quality/manager_evaluator.py`

**Компонент 7: Cron job — автоматическая оценка**
- Периодическая задача (каждые 30 мин): найти resolved эскалации без `manager_review` → запустить оценку
- Интегрировать в `src/worker.py` (arq worker)
- Файлы: `src/quality/manager_job.py`, `src/worker.py`

### Фаза 3: Отображение (компоненты 8-10)

**Компонент 8: API `/api/v1/manager-reviews/`**
- GET `/` — список оценок (фильтры: manager_name, period, rating)
- GET `/{review_id}` — детали
- POST `/{escalation_id}/evaluate` — ручной запуск
- Файлы: `src/api/v1/manager_reviews.py`, `src/schemas/manager_review.py`

**Компонент 9: Dashboard — KPI менеджеров**
- Добавить в `DashboardMetricsResponse`: `avg_manager_score`, `avg_manager_response_time_seconds`, `manager_deal_conversion_rate`, `manager_leaderboard`
- Файлы: `src/services/dashboard_metrics.py`

**Компонент 10: Telegram — Performance Report**
- Добавить секцию в `format_report_text()`: средний балл, SLA, конверсия, топ менеджеров
- Файлы: `src/services/reports.py`

---

## Ключевые находки из Wazzup API

Wazzup webhook отправляет 3 типа событий:
- `authorType='client'` — сообщение клиента
- `authorType='manager'`, `isEcho=true` — менеджер ответил из WhatsApp/CRM
- `authorType='bot'`, `isEcho=false` — бот отправил через API

Доп. поля: `authorId` (ID менеджера), `authorName` (имя).

---

## Порядок работы

1. Прочитай оба дизайн-документа (ссылки выше)
2. Прочитай существующие файлы-образцы: `src/quality/evaluator.py`, `src/quality/schemas.py`, `src/models/quality_review.py`
3. Создай worktree: `git worktree add ../treejar-manager-assessment -b feature/manager-assessment`
4. Реализуй по фазам (1 → 2 → 3), строго TDD
5. Каждый компонент: тест → реализация → `ruff check && mypy . && pytest`
6. После всех компонентов: `pytest` (полный прогон), `/push`, PR

---

## Критерии готовности

- [ ] Все 10 компонентов реализованы
- [ ] Все тесты проходят (`pytest`)
- [ ] `ruff check` — 0 ошибок
- [ ] `mypy --strict` — 0 ошибок
- [ ] Alembic миграция применяется без ошибок
- [ ] LLM Judge генерирует осмысленные оценки (ручная проверка 1-2 диалогов)
