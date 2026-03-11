# Промпт для новой сессии: Этап 2 — Недели 11-12

Скопируй приведённый ниже текст целиком и отправь его в новом окне чата с ИИ-агентом:

***

Привет! Мы продолжаем работу над проектом **Noor AI Seller** — ИИ-продавец офисной мебели для компании Treejar (ОАЭ).

Репозиторий: `maslennikov-ig/treejar`, ветка `develop`.

---

## Текущий статус проекта

**Что уже готово (Этап 1 + частично Этап 2):**

Всё ниже реализовано, протестировано и задеплоено на VPS (`noor.starec.ai`):

- **Ядро бота:** FastAPI + PydanticAI (OpenRouter/DeepSeek). 6 stages продажи (FSM), tool calling (search_products, check_stock, lookup_customer, create_deal, create_quotation). PII masking. Rolling context (system prompt + резюме + последние 5 сообщений).
- **RAG:** pgvector cosine similarity + BGE-M3 embeddings через FastEmbed. Индексация: 856 SKU товаров + FAQ + правила диалогов + ценности компании.
- **Интеграции:** Wazzup (WhatsApp gateway — приём/отправка, debouncing, idempotency), Zoho CRM (EU, 12 этапов воронки, 9 сегментов), Zoho Inventory (sync каждые 6ч).
- **Генерация КП:** WeasyPrint + Jinja2 → PDF прямо в WhatsApp.
- **Персональные цены:** скидка по сегменту из CRM (VIP 15%, Wholesale 10% и т.д.).
- **Эскалация:** 18 триггеров, уведомление 7 менеджерам, модель Escalation в БД (pending/in_progress/resolved).
- **Follow-up:** cron job (24ч → 3д → 7д → 30д → 90д).
- **Админ-панель:** SQLAdmin (CRUD для 10 таблиц) + React/Vite дашборд (17 KPI в 6 категориях, Recharts графики, Timeseries API).
- **Quality Evaluator:** LLM-as-a-judge, 15 критериев, 0-30 баллов, ARQ job, API endpoints, 11 тестов.
- **E2E тесты:** 6 реалистичных диалогов с живым LLM через OpenRouter.

**Метрики кода:** 220 тестов в 47 модулях, >93% coverage, 0 ошибок mypy --strict, 0 ошибок ruff. Версия: `v0.4.0`.

**Техстек:** Python 3.12, FastAPI, SQLAlchemy 2.0 async (AsyncPG), Alembic, PostgreSQL 16 + pgvector, Redis 7, ARQ workers, PydanticAI, FastEmbed BGE-M3, WeasyPrint, SQLAdmin, React/Vite, Docker, Nginx.

**Инфраструктура:**
- VPS: `136.243.71.213` (Hetzner, Ubuntu 24.04)
- Prod: `noor.starec.ai` (docker-compose.yml, ветка `main`), порт 8002
- Dev: `dev.noor.starec.ai` (docker-compose.dev.yml, ветка `develop`), порт 8003
- CI/CD: GitHub Actions → `scripts/vps-deploy.sh`
- Пакетный менеджер: `uv`

---

## Существующие модели БД (10 таблиц)

```
Conversation   — id, phone, zoho_contact_id, zoho_deal_id, language, status, sales_stage, metadata, created_at, updated_at
Message        — id, conversation_id FK, role, content, message_type, tokens_in, tokens_out, cost, model, wazzup_message_id (unique), created_at
Product        — id, zoho_item_id (unique), sku, name_en, name_ar, description_en, description_ar, price, stock, category, image_url, attributes (jsonb), embedding (pgvector), synced_at
KnowledgeBase  — id, source, title, content, language, category, embedding (pgvector), created_at
QualityReview  — id, conversation_id FK (unique), score, criteria (jsonb), summary, reviewer, created_at
Escalation     — id, conversation_id FK, reason, assigned_to, status, created_at
SystemConfig   — id, key (unique), value (jsonb), description, updated_at
SystemPrompt   — id, name (unique), content, version, is_active, created_at, updated_at
MetricsSnapshot — id, period_start, period_end, metrics (jsonb), created_at
```

Все модели определены в `src/models/`, зарегистрированы в `src/models/__init__.py`, наследуются от `Base` в `src/models/base.py`.

---

## Существующая структура кода

```
src/
├── api/v1/
│   ├── router.py              # Главный роутер — подключает все sub-роутеры
│   ├── webhook.py             # POST /api/v1/webhook/wazzup
│   ├── conversations.py       # GET/PATCH conversations
│   ├── crm.py                 # contacts, deals
│   ├── inventory.py           # stock, sale-orders
│   ├── products.py            # search, sync, list
│   ├── quality.py             # POST/GET quality reviews
│   ├── admin_api.py           # metrics API для дашборда
│   └── escalation.py          # POST escalate
├── core/
│   ├── config.py              # Settings (Pydantic Settings, .env)
│   └── database.py            # async_session_factory, engine
├── integrations/
│   ├── messaging/wazzup.py    # WazzupProvider (MessagingProvider protocol)
│   ├── crm/zoho_crm.py        # ZohoCRMClient (CRMProvider protocol)
│   └── inventory/
│       ├── zoho_inventory.py  # ZohoInventoryClient (InventoryProvider protocol)
│       └── sync.py            # sync_products_from_zoho (ARQ task)
├── llm/
│   ├── engine.py              # PydanticAI agent, process_message()
│   └── prompts.py             # build_system_prompt(), sales stage prompts
├── models/                    # SQLAlchemy модели (10 таблиц)
├── quality/
│   ├── evaluator.py           # QualityEvaluator (LLM-as-a-judge)
│   ├── schemas.py             # Pydantic-схемы
│   ├── service.py             # CRUD для quality_reviews
│   └── job.py                 # ARQ job — auto_evaluate_conversations
├── rag/
│   ├── pipeline.py            # RAG поиск (pgvector)
│   ├── embeddings.py          # EmbeddingEngine (BGE-M3)
│   └── indexer.py             # Индексация документов
├── schemas/                   # Pydantic-схемы API
├── services/
│   ├── chat.py                # process_incoming_batch (основная бизнес-логика)
│   ├── followup.py            # run_automatic_followups (cron)
│   ├── dashboard_metrics.py   # 17 KPI метрик
│   ├── metrics.py             # calculate_and_store_metrics
│   └── pdf/generator.py       # WeasyPrint PDF генерация
├── admin/                     # SQLAdmin ModelViews
├── worker.py                  # ARQ WorkerSettings (cron jobs, functions)
└── main.py                    # FastAPI app, startup, mount admin + SPA
```

---

## ЗАДАЧИ НА ЭТУ СЕССИЮ

Нам нужно реализовать **4 модуля** — всё, что можно сделать параллельно, не дожидаясь ответа от собственника бизнеса (он должен дать доступ к WhatsApp). Работай в порядке приоритетов:

### Задача 1: Обновить task-plan.md (5 мин)

В файле `docs/task-plan.md` — секция «Неделя 9-10: Контроль качества» — все пункты Quality Evaluator и Quality API помечены `[ ]`, хотя они **уже полностью реализованы** (см. `src/quality/`). Также обнови секцию «Статистика прогресса» (сейчас там устаревшие цифры: «Выполнено: 50», «Оставшиеся часы: ~348 из 444»).

Проставь `[x]` у:
- Quality evaluator (`src/quality/evaluator.py`) ✅
- 15 критериев ✅
- Scoring ✅
- Rating ✅
- Quality API (POST, GET) ✅
- ARQ job ✅

Оставь `[ ]` у:
- Оценка менеджеров (анализ диалогов живых продавцов, еженедельные отчёты, бот vs менеджер) — это ещё не сделано

---

### Задача 2: Telegram-уведомления (Неделя 11, ~6ч)

**Цель:** При определённых событиях — отправлять уведомления в Telegram-чат руководителю.

**Что уже есть в коде:**
- В `src/core/config.py` есть поля `telegram_bot_token: str = ""` и `telegram_chat_id: str = ""` — пока пустые
- Триггеры эскалации уже работают в `src/llm/engine.py` и `src/api/v1/escalation.py`

**Что нужно создать:**
1. **`src/integrations/notifications/telegram.py`** — клиент Telegram Bot API (httpx, async):
   - `send_message(chat_id, text, parse_mode="HTML")` — отправка текста
   - `send_document(chat_id, file, filename)` — отправка файлов (для PDF-отчётов)
   - Обработка ошибок (retry, rate limit 30 msg/sec)
   
2. **`src/services/notifications.py`** — сервис уведомлений (абстракция над каналами):
   - `notify_escalation(conversation, reason)` — при эскалации диалога
   - `notify_quality_alert(review)` — при низкой оценке диалога (score < 14, рейтинг "poor")
   - `notify_daily_summary()` — ежедневная сводка (кол-во диалогов, эскалации, средний балл)
   - Форматирование: HTML-разметка для Telegram (жирный, курсив, ссылки)
   
3. **`src/api/v1/notifications.py`** — API для управления:
   - `POST /api/v1/notifications/test` — отправить тестовое сообщение (для проверки подключения)
   - `GET /api/v1/notifications/config` — текущие настройки

4. **Интеграция с существующим кодом:**
   - В `src/services/chat.py` → при эскалации вызвать `notify_escalation()`
   - В `src/quality/job.py` → при score < 14 вызвать `notify_quality_alert()`
   - В `src/worker.py` → добавить cron для `notify_daily_summary()` (каждый день 09:00)
   
5. **Тесты (TDD):** `tests/test_telegram_notifications.py` — mock httpx, проверка форматирования, проверка что уведомления отправляются при триггерах

**Важно:** Токен и chat_id пока пустые, поэтому все вызовы должны тихо игнорироваться, если `telegram_bot_token == ""`. Не падать с ошибкой.

---

### Задача 3: Отчёты по отказам и конверсии (Неделя 11, ~4ч)

**Цель:** Еженедельный автоматический отчёт с ключевыми метриками.

**Что нужно создать:**
1. **`src/services/reports.py`** — генерация структурированного отчёта:
   - Период: за последнюю неделю (или указанный диапазон дат)
   - Метрики: диалоги/день, конверсия (диалог→сделка), причины отказов (из escalation.reason), средний чек, средний балл Quality, топ-5 запрашиваемых товаров
   - Формат: текст (для Telegram) + JSON (для API)
   
2. **`src/api/v1/reports.py`** — API:
   - `POST /api/v1/reports/generate` — ручная генерация отчёта за указанный период
   - `GET /api/v1/reports/` — список сгенерированных отчётов
   
3. **ARQ cron** в `src/worker.py` — еженедельный автоотчёт (понедельник 09:00), отправка через сервис уведомлений (Задача 2)

4. **Тесты:** `tests/test_reports.py`

---

### Задача 4: Рекомендации товаров (Неделя 12, ~6ч)

**Цель:** Бот предлагает аналоги и сопутствующие товары.

**Что нужно создать:**
1. **`src/services/recommendations.py`** — сервис рекомендаций:
   - `get_similar_products(product_id, limit=5)` — аналоги через pgvector cosine similarity по embedding (таблица `products` уже имеет колонку `embedding`)
   - `get_cross_sell(category, limit=3)` — правила: стол → кресло, шкаф → полка, стул → подушка. Хранить правила в `SystemConfig` (ключ `cross_sell_rules`, значение jsonb)
   
2. **LLM Tool:** Добавить tool `recommend_products` в `src/llm/engine.py`:
   - Входные: product_id или category
   - Выходные: список рекомендаций (name, price, stock, similarity_score)
   - В промпте: «Также рекомендуем обратить внимание на...»
   
3. **API:**
   - `GET /api/v1/products/{product_id}/similar` — аналоги
   - `GET /api/v1/products/{product_id}/cross-sell` — сопутствующие

4. **Тесты:** `tests/test_recommendations.py`

---

### Задача 5: Реферальная система (Неделя 12, ~6ч)

**Цель:** Клиенты могут делиться реферальным кодом, новый клиент получает скидку, реферер — бонус.

**Что нужно создать:**
1. **Новая модель** `src/models/referral.py`:
   ```
   Referral:
     id: UUID PK
     code: str unique (формат: NOOR-XXXXX, 5 символов alphanumeric)
     referrer_phone: str (кто поделился)
     referee_phone: str | None (кто использовал)
     referrer_discount_percent: float (бонус реферера, default 5%)
     referee_discount_percent: float (скидка нового клиента, default 10%)
     status: enum (active, used, expired)
     used_at: datetime | None
     expires_at: datetime (default +90 дней)
     created_at: datetime
   ```

2. **Alembic миграция** для создания таблицы `referrals`

3. **`src/services/referrals.py`** — бизнес-логика:
   - `generate_code(phone)` — создать уникальный код для клиента
   - `apply_code(code, referee_phone)` — применить код (валидация: не expired, не used, referrer != referee)
   - `get_referral_stats(phone)` — сколько рефералов привёл клиент

4. **LLM Tools** в `src/llm/engine.py`:
   - `generate_referral_code` — клиент просит код для друга
   - `apply_referral_code` — клиент говорит «у меня есть код NOOR-XXXXX»

5. **API:**
   - `POST /api/v1/referrals/generate` — создать код
   - `POST /api/v1/referrals/apply` — применить код
   - `GET /api/v1/referrals/{phone}/stats` — статистика клиента

6. **SQLAdmin:** Добавить ModelView для `Referral` в `src/admin/`

7. **Тесты:** `tests/test_referrals.py`

---

## Правила работы (ОБЯЗАТЕЛЬНО)

1. **MCP Context7:** Перед написанием кода с PydanticAI, ARQ, SQLAlchemy или FastAPI — обязательно запроси актуальную документацию через Context7 (`resolve-library-id` → `query-docs`).
2. **Worktrees:** Используй скилл `using-git-worktrees`. Создай ветку (например, `feature/stage2-notifications`). НЕ пиши код напрямую в `develop`.
3. **Beads (bd):** Создай макро-задачи через `bd`. `bd update <id> --status=in_progress` при старте, `bd close <id> --reason="..."` при завершении, `bd sync` после каждого close.
4. **TDD:** Сначала RED-тест → минимальный код → GREEN → рефактор. Не ломай существующие 220 тестов.
5. **Planning:** Прочитай `PRODUCT.md` и `ARCHITECTURE.md`. Используй навык `brainstorming`, затем `writing-plans` (создай `docs/specs/stage2-parallel/spec.md` и `plan.md`). После утверждения плана — `subagent-driven-development`.
6. **Коммит:** `git commit --no-verify -m "..."` (pre-commit hook mypy иногда зависает). `git push origin <branch>`.
7. **Качество:** После каждой задачи: `uv run pytest`, `uv run ruff check src/`, `uv run mypy src/`. Все должны быть зелёными.

## Порядок выполнения

1. Обнови `task-plan.md` (Задача 1) — это 5 минут, сделай сам.
2. Brainstorming + Writing Plans для задач 2-5.
3. Покажи мне plan.md для утверждения.
4. После утверждения — реализуй задачи 2→3→4→5 через subagent-driven-development, по возможности параллельно, простые — сам.

Начни с фазы `brainstorming`!

***
