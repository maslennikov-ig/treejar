# Дизайн: Оценка работы менеджеров (Manager Assessment)

**Дата:** 2026-03-13
**Статус:** Ожидает утверждения
**Связано с:** ТЗ §2.3.2 (Оценка работы менеджеров), Roadmap недели 10-11

---

## Проблема

Сейчас оценивается только качество AI-диалогов (`quality_reviews`, 15 критериев, 0-30 баллов). После эскалации бота на менеджера — **нет метрик** о качестве работы менеджера. Руководство не знает: как быстро менеджер ответил, закрыл ли сделку, насколько профессионально общался.

## Решение

**Гибридная система оценки** менеджеров: LLM-судья (10 критериев, 0-20 баллов) + автоматические бизнес-метрики (SLA, конверсия, чек).

---

## Решения, принятые на этапе brainstorming

| # | Вопрос | Решение |
|---|--------|---------|
| 1 | Источник данных | **Wazzup webhook** — менеджеры пишут через WhatsApp/Wazzup, все сообщения проходят через наш webhook |
| 2 | Подход к оценке | **Гибрид (A)**: LLM-анализ диалога + количественные метрики |
| 3 | Граница бот/менеджер | **Комбинация (C)**: `escalation_status` как триггер + Wazzup `isEcho`/`authorType` для идентификации автора сообщения |
| 4 | Критерии оценки | **10 LLM-критериев** (0-2, макс 20) + **4 количественных метрики**. См. `docs/08-manager-evaluation-criteria.md` |
| 5 | Хранение и отображение | **Комбинация (C)**: `manager_reviews` таблица + Dashboard KPI + отдельный API endpoint + Telegram-отчёт |

---

## Архитектура

### Поток данных

```
Wazzup Webhook
    │
    ▼
[isEcho=true AND authorType='manager'?]
    │
    yes──► Сохранить как role='manager'
    │       + если conv.escalation_status == 'none':
    │           conv.escalation_status = 'manual_takeover'
    │           бот останавливается
    │
    no ──► [authorType='client'?]
    │       yes──► Сохранить как role='user' (существующий flow)
    │       no ──► Бот-сообщения (authorType='bot' / isEcho=false) — игнорируем
    │
    ▼
[escalation_status != 'none'?] ──yes──► Бот НЕ отвечает
    │
    no ──► Бот отвечает (существующий flow)

...время проходит...

[Cron job: каждые 30 мин]
    │
    ▼
Найти разрешённые эскалации без manager_review
    │
    ▼
Извлечь сообщения менеджера (role='manager') + клиента (role='user')
    после момента эскалации
    │
    ▼
LLM Judge (10 критериев) + Количественные метрики
    │
    ▼
Сохранить в manager_reviews
    │
    ▼
Dashboard API / Telegram Weekly Report
```

### Схема БД: таблица `manager_reviews`

```sql
CREATE TABLE manager_reviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    escalation_id UUID NOT NULL REFERENCES escalations(id),
    conversation_id UUID NOT NULL REFERENCES conversations(id),
    manager_name VARCHAR,                    -- из escalation.assigned_to
    
    -- LLM Judge scores
    total_score NUMERIC(4,1) NOT NULL,       -- сумма 10 критериев (макс 20)
    max_score INTEGER NOT NULL DEFAULT 20,
    rating VARCHAR NOT NULL,                 -- excellent/good/satisfactory/poor
    criteria JSONB NOT NULL,                 -- [{rule_number, rule_name, score, comment}]
    summary TEXT,                            -- LLM-сгенерированная сводка
    
    -- Quantitative metrics
    first_response_time_seconds INTEGER,     -- время до первого ответа менеджера
    message_count INTEGER,                   -- кол-во сообщений менеджера
    deal_converted BOOLEAN DEFAULT FALSE,    -- появился ли zoho_deal_id
    deal_amount NUMERIC(12,2),               -- сумма сделки
    
    reviewer VARCHAR NOT NULL DEFAULT 'ai',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_manager_reviews_escalation_id ON manager_reviews(escalation_id);
CREATE INDEX ix_manager_reviews_manager_name ON manager_reviews(manager_name);
CREATE INDEX ix_manager_reviews_created_at ON manager_reviews(created_at);
CREATE UNIQUE INDEX ix_manager_reviews_one_per_escalation 
    ON manager_reviews(escalation_id);
```

### Изменения в существующих таблицах

**`messages`** — поле `role` теперь поддерживает 3 значения:
- `user` — сообщение клиента
- `assistant` — ответ бота
- `manager` — ответ менеджера

> Не требует миграции — поле уже `VARCHAR`, просто добавляем новое значение.

**`conversations.escalation_status`** — новое значение:
- `manual_takeover` — менеджер перехватил диалог без эскалации

**`escalations.assigned_to`** — заполнять из `isFromMe` (имя менеджера из Wazzup, если передаётся) или оставить `NULL` (определяется позже).

### Изменения в Wazzup Webhook

✅ **ПРОВЕРЕНО:** Wazzup webhook отправляет **3 типа событий** для WhatsApp:
1. Новое сообщение клиента (`authorType='client'`)
2. Новое сообщение менеджера (`authorType='manager'`, `isEcho=true`)
3. Новое сообщение бота (`authorType='bot'`, `isEcho=false`)

Дополнительные поля: `authorId` (ID менеджера), `authorName` (имя менеджера).

Нужно:

1. Добавить поля в `WazzupIncomingMessage` schema:
   - `is_echo: bool | None = Field(None, alias='isEcho')`
   - `author_type: str | None = Field(None, alias='authorType')`
   - `author_id: str | None = Field(None, alias='authorId')`
   - `author_name: str | None = Field(None, alias='authorName')`
2. В `handle_wazzup_webhook`:
   - `authorType='manager'` → сохранить как `role='manager'`, проверить/установить `escalation_status`
   - `authorType='bot'` с `isEcho=true` → эхо нашего бота, можно игнорировать
   - `authorType='client'` → существующий flow (`role='user'`)
3. В `process_incoming_batch` — проверять `escalation_status`, если `!= 'none'` → НЕ вызывать LLM

### API Endpoints

```
/api/v1/manager-reviews/
    GET  /                          — список оценок (фильтры: manager_name, period, rating)
    GET  /{review_id}               — детали оценки
    POST /{escalation_id}/evaluate  — ручной запуск оценки

/api/v1/dashboard/metrics           — расширить DashboardMetricsResponse:
    + avg_manager_score: float
    + avg_manager_response_time_seconds: float
    + manager_deal_conversion_rate: float
    + manager_leaderboard: [{name, avg_score, reviews_count}]
```

### Telegram Weekly Report

Добавить в `format_report_text()`:

```
📊 Manager Performance
  Avg Score: 16.2/20 (good)
  Avg Response Time: 8 min
  Deal Conversion: 65%
  Reviews: 12
  Top: Israullah (17.5), Annabelle (16.8)
```

---

## Компоненты для реализации

| # | Компонент | Файлы | Зависит от |
|---|-----------|-------|------------|
| 1 | Webhook: `isFromMe` + роль `manager` | `schemas/webhook.py`, `api/v1/webhook.py`, `services/chat.py` | — |
| 2 | Бот молчит при эскалации | `services/chat.py` | #1 |
| 3 | Manual takeover (менеджер без эскалации) | `services/chat.py`, `schemas/common.py` | #1 |
| 4 | Миграция: таблица `manager_reviews` | `models/manager_review.py`, Alembic | — |
| 5 | LLM Judge для менеджеров | `quality/manager_evaluator.py`, `quality/manager_schemas.py` | #4 |
| 6 | Количественные метрики | `quality/manager_evaluator.py` | #4 |
| 7 | Cron job: автоматическая оценка | `quality/manager_job.py`, `worker.py` | #5, #6 |
| 8 | API: `/manager-reviews/` | `api/v1/manager_reviews.py`, `schemas/manager_review.py` | #4 |
| 9 | Dashboard: KPI менеджеров | `services/dashboard_metrics.py`, `schemas/__init__.py` | #4 |
| 10 | Telegram: Performance Report | `services/reports.py` | #4, #9 |

---

## ~~Нерешённые вопросы~~ Решённые вопросы

> [!TIP]
> ✅ **Wazzup webhook полностью поддерживает определение автора.** Поля `isEcho`, `authorType`, `authorId`, `authorName` позволяют точно различать клиента, менеджера и бота. Этапирование не требуется — реализуем полную версию сразу.

> [!NOTE]  
> **Manual takeover** — отдельная задача: если менеджер пишет без эскалации, бот должен остановиться со статусом `manual_takeover`. Определяется по `authorType='manager'` при `escalation_status='none'`.
