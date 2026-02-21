# Анализ архитектуры: Топ-3 варианта реализации

## Контекст

Проведён Deep Research (поиск библиотек, фреймворков, готовых решений) и DeepThink (архитектурный анализ рисков и паттернов) двумя независимыми моделями. Документы содержат как совпадающие, так и противоречащие рекомендации. Ниже — критический синтез с тремя вариантами реализации от лучшего к худшему.

### Источники
- `docs/Research/Deep technology research for Treejar's AI sales assistant.md`
- `docs/DeepThink/Architecture Analysis for AI Sales Bot.md`

---

## Ключевые точки согласия (оба документа единогласны)

Эти решения не обсуждаются — они войдут в ЛЮБОЙ вариант:

| Решение | Обоснование |
|---------|-------------|
| **Async queue (Redis + ARQ)** | Webhook Wazzup → 200 OK за <100ms → фоновый воркер. Синхронная обработка = таймауты + дубликаты |
| **Отказ от zohocrmsdk8-0** | Синхронный SDK блокирует event loop. Заменяем на custom httpx.AsyncClient |
| **Локальное зеркало каталога** | Продукты Zoho Inventory → PostgreSQL (sync раз в час). Бот читает из PG, не из Zoho API |
| **Redis distributed lock для OAuth** | `SETNX` на refresh токена Zoho. Без этого — race condition, блокировка аккаунта |
| **PydanticAI для оркестрации** | Нативная поддержка OpenRouter, tool calling, structured outputs, async |
| **FSM в PostgreSQL** | Столбец `sales_stage` в БД. LLM получает правила текущего этапа в system prompt |
| **Multi-model routing** | Дешёвая модель для intent/extraction, мощная для генерации ответа |
| **English system prompts** | LLM рассуждает на EN, отвечает на языке клиента (EN/AR). Так лучше следует инструкциям |
| **Debouncing сообщений** | 3-5 сек ожидание в Redis перед обработкой серии сообщений |
| **Redis idempotency** | `SET NX EX 86400` по message_id. Защита от дублей webhook |
| **Маскировка PII** | UUID вместо реальных телефонов/emails в контексте LLM |
| **24h WhatsApp правило** | Follow-up >24ч — ТОЛЬКО pre-approved template messages через Wazzup |

---

## Ключевые противоречия между документами

| Вопрос | Deep Research | DeepThink | Мой вердикт |
|--------|--------------|-----------|-------------|
| **Векторный поиск** | Qdrant + BGE-M3 hybrid (dense+sparse) | Убрать Qdrant, pgvector + SQL tool calling | **pgvector для MVP** (см. ниже) |
| **WhatsApp gateway** | Заменить Wazzup на Meta Cloud API | Не рассматривает | **Оставить Wazzup** (контракт подписан) |
| **Admin panel** | SQLAdmin | Использовать Zoho CRM как UI | **SQLAdmin** (контрактное требование) |
| **Количество сервисов** | 8 Docker-контейнеров | Резать всё, минимум инфры | **5 сервисов** (app, pg, redis, nginx, qdrant опционально) |
| **Scope** | Полный стек + Whisper + Langfuse | Убрать QC-бот, Qdrant, голосовые, админку | **Полный scope** (контрактное обязательство) |
| **Embeddings** | BGE-M3 via FastEmbed (local) | Не нужны, SQL достаточно | **BGE-M3 но через pgvector** |

### Вердикт по pgvector vs Qdrant

DeepThink прав: для 1,500 SKU с чёткими атрибутами (цена, цвет, категория) **основной поиск = SQL WHERE**. LLM извлекает структурированные фильтры через tool calling → `WHERE price < 500 AND color = 'black'`. Векторный поиск нужен только как fallback для нечётких запросов ("что-то современное для офиса").

**pgvector покрывает оба сценария** без отдельного сервиса. Qdrant имеет смысл при >50K документов или когда нужен полноценный hybrid search с BM25. Для 1,500 SKU это оверинжиниринг.

### Вердикт по Wazzup

Deep Research убедительно показал преимущества Meta Cloud API (каталоги, кнопки, WhatsApp Flows). Но:
- Wazzup указан в подписанном контракте (`docs/tz.md`)
- Миграция на Meta Cloud API — отдельный проект, не укладывается в 13 недель
- **Решение**: абстрагировать messaging layer (interface), чтобы потом можно было переключить

---

## Вариант A: Прагматичный оптимум (РЕКОМЕНДУЕТСЯ)

> Минимум инфраструктуры, максимум надёжности. Фокус на delivery за 13 недель.

### Стек

| Компонент | Технология | Почему |
|-----------|-----------|--------|
| Runtime | Python 3.13, FastAPI 0.129 | LTS, async, проверенный стек |
| DB | Supabase Cloud (PostgreSQL 17 + pgvector) | Managed DB, auto backups, dashboard, zero ops |
| Queue | Redis 8.0 + ARQ | Async queue, cache, debounce, idempotency, OAuth lock — всё в одном |
| Embeddings | BGE-M3 via FastEmbed (local) | Бесплатно, EN/AR, dense + sparse в одном проходе |
| AI orchestration | PydanticAI + pydantic-graph | FSM, tool calling, OpenRouter native |
| LLM | OpenRouter (Haiku → extraction, Sonnet/GPT-4o → generation) | Multi-model routing с fallback |
| WhatsApp | Wazzup (custom httpx) | Контрактное обязательство |
| Zoho CRM + Inventory | Custom httpx.AsyncClient | Async, без bloat SDK |
| Admin | SQLAdmin (mounted в FastAPI) | Zero-frontend, контрактное требование |
| Proxy | Nginx | SSL termination, rate limiting |

### Docker: 3 сервиса (+ Supabase Cloud)

```
app (FastAPI + ARQ worker) :8000
redis (8.0)                :6379
nginx                      :80/443
```

PostgreSQL — Supabase Cloud (managed, auto backups, pgvector из коробки, dashboard).
ARQ worker запускается в том же контейнере `app` как отдельный процесс (supervisor или entrypoint script).

### Архитектура поиска товаров

```
Запрос пользователя
  → LLM (Haiku) извлекает: {category, max_price, colors, semantic_query}
  → Python: SQL WHERE по структурированным фильтрам
  → Если есть semantic_query: + pgvector cosine similarity на оставшемся подмножестве
  → Результат: точные данные из БД (цена, остатки, фото)
```

### Плюсы
- **Минимум инфраструктуры** — 3 контейнера (app, redis, nginx) + Supabase Cloud
- **Один источник правды** — PostgreSQL для data + vectors
- **Простой деплой** — docker-compose up и работает
- **Нет hallucination цен** — LLM физически не видит цены, только tool results
- **Укладывается в 13 недель** — проверенные библиотеки, минимум интеграций
- **Стоимость** — $0 за embeddings (локально), ~$50-100/мес за LLM при 200 диалогов/день

### Минусы
- **pgvector уступает Qdrant** в скорости при >10K документов (не наш случай)
- **Нет hybrid search с BM25** из коробки (для точных SKU/брендов нужен WHERE ILIKE)
- **ARQ проще Celery** но менее гибок (нет приоритетов очередей, chain of tasks)
- **SQLAdmin минималистичен** — нет кастомных dashboard, только CRUD

### Риск: LOW-MEDIUM

---

## Вариант B: Агрессивный (расширенный стек)

> Больше возможностей, но больше инфраструктуры и точек отказа.

### Отличия от Варианта A

| Компонент | Вместо | Что | Зачем |
|-----------|--------|-----|-------|
| Vector DB | pgvector | Qdrant 1.16 (отдельный контейнер) | Hybrid search: dense + sparse + payload filtering |
| Observability | — | Langfuse (self-hosted) | LLM трейсинг, стоимость, prompt versioning |
| Voice | — | Google Cloud STT | Транскрипция голосовых (Gulf Arabic) |
| Gateway | Wazzup | Wazzup → Meta Cloud API (неделя 5+) | Interactive buttons, каталоги, WhatsApp Flows |

### Docker: 7 сервисов

```
app (FastAPI + ARQ worker) :8000
postgres (17)              :5432
qdrant (1.16)              :6333
redis (8.0)                :6379
langfuse                   :3000
nginx                      :80/443
```

### Плюсы
- **Мощный поиск** — Qdrant hybrid (dense + sparse + payload filtering) лучше для сложных запросов
- **Полная наблюдаемость** — Langfuse: каждый LLM-вызов с метриками, стоимостью, latency
- **Голосовые** — не теряем 30-40% MENA-лидов, которые отправляют voice notes
- **Rich UI в WhatsApp** — кнопки, списки товаров, карусели (если перейдём на Meta Cloud API)

### Минусы
- **+3 Docker сервиса** — Qdrant, Langfuse, потенциально whisper
- **Миграция на Meta Cloud API** — 2-3 недели дополнительной работы, выходит за рамки контракта
- **Langfuse self-hosted** — нужен мониторинг + бекапы ещё одного сервиса
- **Google Cloud STT** — платный ($0.006/15 сек), нужен GCP аккаунт
- **Сложнее деплой** — 7 контейнеров на одном VPS (RAM? CPU?)
- **Больше точек отказа** — Qdrant down = поиск не работает

### Риск: MEDIUM-HIGH

Главный вопрос: уложимся ли в 13 недель как соло-разработчик с расширенным стеком? Вероятно нет — Langfuse и Meta Cloud API вынесены в post-MVP.

---

## Вариант C: Контрарный (минималистичный прототип)

> Максимально быстрая поставка демо, с техдолгом для переработки.

### Отличия от Варианта A

| Компонент | Вместо | Что | Зачем |
|-----------|--------|-----|-------|
| DB mirror | Local PostgreSQL | Zoho Inventory live API | Нет синхронизации, меньше кода |
| Vector search | pgvector | Нет. Только SQL + ILIKE | 1,500 SKU помещаются в prompt |
| Queue | ARQ | FastAPI BackgroundTasks | Меньше зависимостей |
| Admin | SQLAdmin | Zoho CRM как UI | Нет отдельной панели |

### Docker: 3 сервиса

```
app (FastAPI)  :8000
postgres       :5432
redis          :6379
```

### Плюсы
- **Минимум кода** — нет синхронизации Zoho, нет embeddings, нет отдельного queue
- **Быстрый старт** — можно показать демо за 2 недели
- **Простой деплой** — 3 контейнера

### Минусы
- **Zoho live API** — 100 req/min лимит, при 200 диалогах/день = гарантированный rate limiting
- **BackgroundTasks** — не durабельный, задачи теряются при рестарте
- **Нет vector search** — невозможно обрабатывать нечёткие запросы ("что-то стильное для кабинета")
- **Нет admin panel** — нарушение контракта (прописано в tz.md, раздел 2.2.4)
- **Потребует полной переработки** при масштабировании >50 диалогов/день
- **Zoho live = медленные ответы** — 2-5 сек на каждый API-call вместо <10ms из PostgreSQL

### Риск: MEDIUM (для прототипа LOW, для production HIGH)

Этот вариант **не рекомендуется** для контрактного проекта. Подходит только как proof-of-concept на 1-2 недели.

---

## Сводная таблица

| Критерий | A (Прагматичный) | B (Агрессивный) | C (Минималист) |
|----------|:-----------------:|:----------------:|:--------------:|
| Docker-сервисов | 3 + Supabase Cloud | 7 | 3 |
| Укладывается в 13 недель | Да | Сомнительно | Как прототип |
| Соответствует контракту | Полностью | Полностью+ | Частично |
| Поиск товаров | SQL + pgvector | Qdrant hybrid | SQL + ILIKE |
| Масштабируемость | До 500 диалогов/день | До 2000+ | До 50 |
| Стоимость инфры/мес | ~$20 VPS + $0-25 Supabase | ~$40 VPS | ~$15 VPS |
| Наблюдаемость LLM | Логи + метрики | Langfuse | Логи |
| Голосовые сообщения | Post-MVP | С недели 4 | Нет |
| Техдолг | Низкий | Средний | Критический |
| **Общий риск** | **LOW-MEDIUM** | **MEDIUM-HIGH** | **MEDIUM** |

---

## Рекомендация

**Вариант A** — единственный, который реалистично укладывается в 13 недель для соло-разработчика и полностью соответствует контракту.

Элементы из Варианта B добавляются итеративно после MVP:
- Langfuse — неделя 9-10 (этап 2, контроль качества)
- Google Cloud STT — неделя 11-12 (если клиент подтвердит потребность)
- Meta Cloud API — отдельный проект после сдачи

---

## Архитектурные абстракции (future-proofing)

Все внешние сервисы изолируются за Protocol-интерфейсами для безболезненной замены:

```
src/integrations/
  messaging/
    base.py              # MessagingProvider(Protocol)
    wazzup.py            # WazzupProvider → завтра: TelegramProvider, MetaCloudProvider
  crm/
    base.py              # CRMProvider(Protocol)
    zoho_crm.py          # ZohoCRMClient → завтра: SalesforceClient, HubSpotClient
  inventory/
    base.py              # InventoryProvider(Protocol)
    zoho_inventory.py    # ZohoInventoryClient
  vector/
    base.py              # VectorStore(Protocol)
    pgvector.py          # PgVectorStore → завтра: QdrantStore, PineconeStore
```

Переключение = новый класс + изменение DI-конфига. Бизнес-логика не затрагивается.

---

## Критические паттерны (войдут в реализацию)

Из DeepThink — уникальные инсайты, которых не было в исходной архитектуре:

1. **Message debouncing** — Redis key `debounce:{chat_id}` с TTL 3s. При новом сообщении: сбросить таймер, аккумулировать. По истечении — отправить batch в очередь
2. **Webhook idempotency** — `SET debounce:{message_id} NX EX 86400`. Если ключ уже есть → drop request
3. **OAuth distributed lock** — `SET zoho_refresh_lock NX EX 30`. Один воркер обновляет токен, остальные ждут 1 сек и берут новый
4. **Rolling context window** — System prompt + семантическое резюме старых сообщений + последние 5 raw messages
5. **24h template rule** — cron job проверяет last_message_at, для >24h использует ТОЛЬКО Wazzup template messages
6. **PII masking** — internal UUID в LLM context, реальные данные подставляются на уровне Python перед отправкой в Zoho

---

## План реализации (после утверждения варианта)

После выбора варианта возвращаемся к исходному плану kickoff:
1. **Project initialization** — code skeleton с учётом выбранной архитектуры
2. **Sprint plan week 1** — Beads задачи (24 часа)
3. **Dev guide** — внутренний workflow
4. **API contracts** — Pydantic schemas + FastAPI stubs

Ключевые файлы-источники:
- `docs/architecture.md` — схема БД, роуты API, Docker-сервисы
- `docs/tz.md` — функциональные требования, критерии приёмки
- `docs/07-knowledge-base-spec.md` — модель данных продуктов
- `docs/06-dialogue-evaluation-checklist.md` — 15 правил оценки качества
- `docs/04-sales-dialogue-guidelines.md` — правила продаж (для промптов)
- `docs/05-company-values.md` — ценности компании (для промптов)

### Верификация

После реализации kickoff:
1. `docker-compose up -d` — 3 локальных сервиса стартуют (app, redis, nginx)
2. Supabase Cloud доступен, `DATABASE_URL` указывает на облако
3. `curl localhost:8000/api/v1/health` → `{"status": "ok"}`
4. `localhost:8000/docs` — Swagger UI со всеми эндпоинтами
5. `alembic upgrade head` — создаёт таблицы в Supabase (включая pgvector extension)
6. `pytest tests/` — проходит
7. `ruff check src/ tests/` + `mypy src/` — без ошибок
