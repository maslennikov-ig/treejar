# Руководство разработчика: Treejar AI Bot

**Версия:** 1.0
**Дата:** 2026-02-21
**Для кого:** Разработчик + Claude Code AI-ассистент

---

## 1. Обзор проекта

Treejar AI Bot — ИИ-продавец офисной мебели для компании Treejar (ОАЭ). Бот работает через WhatsApp (шлюз Wazzup), консультирует клиентов на английском и арабском языках, проверяет остатки в Zoho Inventory, создаёт сделки в Zoho CRM, генерирует коммерческие предложения (SaleOrder) и передаёт сложные случаи живому менеджеру. Проект рассчитан на 13 недель разработки (2 этапа: базовая автоматизация + контроль качества/аналитика).

**Ключевые документы:**

| Документ | Путь | Описание |
|----------|------|----------|
| Техническое задание | `docs/tz.md` | Функциональные требования, критерии приёмки |
| Архитектура | `docs/architecture.md` | Схема системы, БД, API-роуты, потоки данных |
| Дорожная карта | `docs/roadmap.md` | Понедельный план на 13 недель |
| Архитектурные решения | `docs/plans/goofy-riding-pizza.md` | Анализ вариантов реализации, выбор стека |

---

## 2. Быстрый старт

### Предварительные требования

- **Docker Desktop** или Docker Engine + Compose v2
- **Python 3.13+**
- **uv** (менеджер пакетов Python) — `pip install uv`

### Запуск через Docker

```bash
# 1. Скопировать и настроить переменные окружения
cp .env.example .env
# Заполнить .env: SUPABASE_URL, REDIS_URL, OPENROUTER_API_KEY,
# WAZZUP_API_KEY, ZOHO_CRM_*, ZOHO_INVENTORY_*

# 2a. Production-like запуск (использует Supabase Cloud как БД)
docker compose up -d

# 2b. Локальная разработка (поднимает локальный PostgreSQL + pgvector)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# 3. Применить миграции
alembic upgrade head

# 4. Проверить работоспособность
curl http://localhost:8000/api/v1/health
open http://localhost:8000/docs      # Swagger UI
open http://localhost:8000/admin/    # SQLAdmin панель
```

### Локальная разработка без Docker

```bash
# Создать виртуальное окружение и установить зависимости
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"

# Запустить сервер (hot-reload)
uvicorn src.main:app --reload --port 8000

# Запустить ARQ-воркер (в отдельном терминале)
arq src.worker.WorkerSettings
```

### Docker-сервисы

| Режим | Сервисы | БД |
|-------|---------|-----|
| **Production** | `app`, `worker`, `redis`, `nginx` | Supabase Cloud (PostgreSQL 17 + pgvector) |
| **Dev** | `app`, `worker`, `redis`, `postgres` | Локальный `ankane/pgvector:pg17` |

---

## 3. Структура проекта

```
treejar-ai-bot/
├── src/                          # Исходный код приложения
│   ├── main.py                   # FastAPI application factory + lifespan
│   ├── worker.py                 # ARQ worker (фоновые задачи)
│   ├── api/                      # HTTP-слой
│   │   ├── deps.py               # Общие зависимости (DI)
│   │   └── v1/                   # API v1 endpoints
│   │       ├── router.py         # Главный роутер (собирает все sub-routers)
│   │       ├── health.py         # GET /api/v1/health
│   │       ├── webhook.py        # POST /api/v1/webhook/wazzup
│   │       ├── conversations.py  # CRUD диалогов
│   │       ├── products.py       # Каталог товаров + поиск
│   │       ├── crm.py            # Интеграция Zoho CRM (контакты, сделки)
│   │       ├── inventory.py      # Zoho Inventory (остатки, SaleOrder)
│   │       ├── quality.py        # Контроль качества
│   │       └── admin.py          # Админ-функции (промпты, метрики)
│   ├── core/                     # Ядро приложения
│   │   ├── config.py             # Pydantic Settings (все env-переменные)
│   │   ├── database.py           # SQLAlchemy async engine + session factory
│   │   ├── redis.py              # Redis async client
│   │   └── security.py           # Аутентификация, webhook-верификация
│   ├── models/                   # SQLAlchemy ORM-модели
│   │   ├── base.py               # Базовая модель (UUID PK, timestamps)
│   │   ├── conversation.py       # Диалоги (phone, language, status, FSM stage)
│   │   ├── message.py            # Сообщения (role, content, tokens, cost)
│   │   ├── product.py            # Товары (зеркало Zoho Inventory)
│   │   ├── knowledge_base.py     # База знаний (source, content, category)
│   │   ├── quality_review.py     # Оценки качества диалогов
│   │   └── escalation.py         # Эскалации на менеджера
│   ├── schemas/                  # Pydantic-схемы (request/response)
│   │   ├── common.py             # Общие схемы (pagination, timestamps)
│   │   ├── health.py             # HealthResponse
│   │   ├── webhook.py            # WazzupWebhookPayload
│   │   ├── conversation.py       # ConversationCreate/Read/Update
│   │   ├── product.py            # ProductRead, ProductSearchQuery
│   │   ├── crm.py                # ContactRead, DealCreate/Read
│   │   ├── inventory.py          # StockRead, SaleOrderCreate
│   │   ├── quality.py            # ReviewCreate/Read, ReportQuery
│   │   └── admin.py              # AdminSettings, PromptConfig
│   ├── integrations/             # Внешние сервисы (Protocol-абстракции)
│   │   ├── messaging/            # WhatsApp
│   │   │   └── base.py           # MessagingProvider(Protocol)
│   │   ├── crm/                  # Zoho CRM
│   │   │   └── base.py           # CRMProvider(Protocol)
│   │   ├── inventory/            # Zoho Inventory
│   │   │   └── base.py           # InventoryProvider(Protocol)
│   │   └── vector/               # Векторный поиск
│   │       └── base.py           # VectorStore(Protocol)
│   ├── llm/                      # LLM-оркестрация
│   │   ├── engine.py             # PydanticAI agent, multi-model routing
│   │   └── prompts.py            # Системные промпты (EN), шаблоны
│   ├── rag/                      # RAG-пайплайн
│   │   ├── embeddings.py         # BGE-M3 через FastEmbed (локально)
│   │   ├── indexer.py            # Индексация продуктов и базы знаний
│   │   └── pipeline.py           # SQL-фильтры + pgvector cosine similarity
│   └── quality/                  # Контроль качества
│       └── evaluator.py          # Автоматическая оценка диалогов
├── migrations/                   # Alembic миграции
│   ├── env.py                    # Конфигурация Alembic (async engine)
│   ├── script.py.mako            # Шаблон миграций
│   └── versions/                 # Файлы миграций
├── tests/                        # Тесты
│   ├── conftest.py               # Фикстуры (TestClient, DB session)
│   └── test_health.py            # Тест health endpoint
├── scripts/
│   └── entrypoint.sh             # Docker entrypoint (web | worker)
├── nginx/
│   ├── nginx.conf                # Главная конфигурация Nginx
│   └── conf.d/                   # Server blocks
├── docs/                         # Документация проекта
│   ├── tz.md                     # Техническое задание
│   ├── architecture.md           # Архитектура системы
│   ├── roadmap.md                # Дорожная карта (13 недель)
│   └── plans/                    # Архитектурные решения
├── docker-compose.yml            # Production: app + worker + redis + nginx
├── docker-compose.dev.yml        # Dev overlay: + local PostgreSQL
├── Dockerfile                    # Multi-stage сборка (python:3.13-slim)
├── pyproject.toml                # Зависимости, ruff, mypy, pytest конфиг
├── alembic.ini                   # Конфигурация Alembic
└── .env.example                  # Шаблон переменных окружения
```

---

## 4. Рабочий процесс

### Цикл разработки: Claude Code + Beads

```
1. bd ready                              — найти доступные задачи
2. bd update <id> --status in_progress   — взять задачу (exclusive lock)
3. Написать код, запустить тесты         — реализация
4. ruff check src/ tests/ && mypy src/   — проверить линтер и типы
5. pytest tests/                         — прогнать тесты
6. bd close <id> --reason "описание"     — закрыть задачу
7. git add . && git commit && git push   — закоммитить и запушить
```

### Создание задач

| Тип работы | Команда |
|------------|---------|
| Фича | `bd create -t feature --files path/to/file.py` |
| Баг | `bd create -t bug` |
| Техдолг | `bd create -t chore` |
| Исследование | `bd mol wisp exploration` |
| Большая фича (>1 дня) | `bd mol bond bigfeature-pipeline` |

### Многотерминальная работа

- Каждый терминал берёт отдельную задачу через `bd update --status in_progress`
- Exclusive lock: один терминал = одна задача
- Авто-освобождение через 30 минут бездействия
- Найти свободные задачи: `bd list --unlocked`

### Делегирование сложных задач

Для задач, требующих изменений в нескольких файлах, Claude Code использует паттерн оркестратора:

1. Собрать контекст (прочитать файлы, проверить паттерны)
2. Делегировать подагентам с полным контекстом
3. **Обязательно** проверить результат самостоятельно: `Read` файлов, `ruff check`, `mypy`, `pytest`
4. Перенаправить, если результат неверен

---

## 5. Соглашения по коду

### Python

- **Python 3.13** — используем новейший синтаксис
- Типизация: `str | None` вместо `Optional[str]`, `list[int]` вместо `List[int]`
- `match/case` где уместно
- `from __future__ import annotations` в каждом файле

### Форматирование

- **ruff format** — автоформатирование
- **ruff check** — линтер (E, W, F, I, UP, B, SIM, TCH)
- Длина строки: **88 символов**
- Проверка типов: **mypy --strict** (с плагином pydantic)

### Именование

| Что | Стиль | Пример |
|-----|-------|--------|
| Файлы, функции, переменные | `snake_case` | `get_stock_level()` |
| Классы, модели | `PascalCase` | `ConversationModel` |
| Pydantic-схемы | `XxxCreate`, `XxxRead`, `XxxUpdate`, `XxxQuery` | `ProductCreate`, `ProductRead` |
| Константы | `UPPER_SNAKE_CASE` | `MAX_RETRY_COUNT` |
| Env-переменные | `UPPER_SNAKE_CASE` | `OPENROUTER_API_KEY` |

### Импорты

- **Только абсолютные**: `from src.core.config import settings`
- Сортировка: `ruff` с isort-правилами (`known-first-party = ["src"]`)

### Async

- Асинхронность **везде**: `asyncpg`, `httpx.AsyncClient`, `redis.asyncio`, `arq`
- Нет блокирующих вызовов в event loop
- `async def` для всех endpoint-ов и сервисных функций

---

## 6. Git-воркфлоу

### Ветвление

- Одна ветка: **main** (production)
- Все коммиты идут напрямую в main

### Формат коммитов

```
type(scope): описание на русском или английском

Примеры:
feat(webhook): обработка входящих сообщений Wazzup
fix(crm): retry при 429 от Zoho API
docs(roadmap): обновить сроки этапа 2
refactor(models): вынести base model в отдельный файл
test(products): unit-тесты для поиска товаров
chore(deps): обновить fastapi до 0.115
```

**Типы:** `feat`, `fix`, `docs`, `refactor`, `test`, `chore`

### Правила

- `ruff check` и `mypy` должны проходить перед коммитом
- ID задачи из Beads добавлять, когда применимо
- Никаких секретов в коммитах (`.env`, ключи API, токены)

---

## 7. Стратегия тестирования

### Структура тестов

```
tests/
├── conftest.py           # Общие фикстуры
├── test_health.py        # Smoke test
├── unit/                 # Юнит-тесты (моки для внешних сервисов)
│   ├── test_llm.py
│   ├── test_rag.py
│   └── test_schemas.py
├── integration/          # Интеграционные (реальная БД через testcontainers)
│   ├── test_models.py
│   └── test_api.py
└── e2e/                  # End-to-end (полный стек)
    └── test_webhook_flow.py
```

### Запуск

```bash
# Все тесты
pytest tests/

# Только юнит-тесты
pytest tests/ -m unit

# Только интеграционные
pytest tests/ -m integration

# С покрытием
pytest tests/ --cov=src --cov-report=html
```

### Конфигурация

- `asyncio_mode = "auto"` — все тесты запускаются в async event loop
- Маркеры: `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.e2e`
- **Целевое покрытие: 80%+**

### Принципы

- **Юнит-тесты**: мокаем `httpx`, Redis, Zoho API. Тестируем бизнес-логику изолированно
- **Интеграционные**: реальная PostgreSQL через testcontainers, проверяем ORM-запросы
- **E2E**: имитация полного цикла webhook -> обработка -> ответ

---

## 8. Деплой

### Production-окружение

| Компонент | Где | Как |
|-----------|-----|-----|
| Приложение (FastAPI + ARQ worker) | VPS (Docker) | `docker compose up -d` |
| База данных | Supabase Cloud | Managed PostgreSQL 17 + pgvector |
| Redis | VPS (Docker) | Контейнер `redis:7-alpine` |
| Nginx | VPS (Docker) | Reverse proxy, SSL termination |

### Процесс деплоя

```bash
# На сервере
git pull origin main
docker compose build --no-cache
docker compose up -d
alembic upgrade head        # Применить новые миграции
docker compose logs -f app  # Проверить логи
```

### CI/CD

- **GitHub Actions**: автодеплой по push в main
- Pipeline: `ruff check` -> `mypy` -> `pytest` -> SSH deploy на VPS

### Бэкапы

- **PostgreSQL**: Supabase Cloud автоматически (ежедневные бэкапы, point-in-time recovery)
- **Redis**: append-only file, volume `redis-data`

### SSL

- Let's Encrypt через Nginx, автообновление сертификатов

---

## 9. Ключевые интеграции

| Сервис | Назначение | Код | Протокол |
|--------|-----------|-----|----------|
| **Wazzup** | WhatsApp-шлюз (отправка/приём сообщений) | `src/integrations/messaging/` | `MessagingProvider` |
| **Zoho CRM** | Контакты, сделки, история покупок | `src/integrations/crm/` | `CRMProvider` |
| **Zoho Inventory** | Товары, остатки, SaleOrder (КП) | `src/integrations/inventory/` | `InventoryProvider` |
| **OpenRouter** | LLM API (Claude Haiku для extraction, Sonnet для генерации) | `src/llm/engine.py` | Через `openai` SDK с `base_url` |
| **Supabase** | PostgreSQL 17 + pgvector (managed) | `src/core/database.py` | SQLAlchemy async |
| **Redis** | Кеш сессий, очереди ARQ, debounce, idempotency, OAuth lock | `src/core/redis.py` | `redis.asyncio` |
| **FastEmbed** | Локальные embeddings (BGE-M3, EN/AR) | `src/rag/embeddings.py` | `fastembed` |
| **PydanticAI** | Оркестрация LLM (tool calling, structured output) | `src/llm/engine.py` | Нативная интеграция |

### Все внешние сервисы изолированы за Protocol-интерфейсами

```
src/integrations/
├── messaging/base.py    → MessagingProvider(Protocol)
├── crm/base.py          → CRMProvider(Protocol)
├── inventory/base.py    → InventoryProvider(Protocol)
└── vector/base.py       → VectorStore(Protocol)
```

Переключение провайдера = новый класс + изменение DI-конфигурации. Бизнес-логика не затрагивается.

---

## 10. Архитектурные решения

Основано на анализе из `docs/plans/goofy-riding-pizza.md` (Вариант A — прагматичный оптимум).

### Выбранный стек и обоснование

| Решение | Что выбрали | Почему |
|---------|-------------|--------|
| **Async queue** | Redis + ARQ | Webhook -> 200 OK за <100ms -> фоновый воркер. Синхронная обработка = таймауты |
| **Векторный поиск** | pgvector (не Qdrant) | 1500 SKU — pgvector покрывает. Нет лишнего сервиса. SQL + cosine similarity |
| **LLM-оркестрация** | PydanticAI | Нативная поддержка OpenRouter, tool calling, structured output, async |
| **Zoho SDK** | Custom httpx (не zohocrmsdk) | Официальный SDK синхронный, блокирует event loop |
| **Интеграции** | Protocol-абстракции | Переключение провайдера без изменения бизнес-логики |
| **Поиск товаров** | SQL WHERE + pgvector fallback | LLM извлекает фильтры (цена, цвет, категория) -> SQL. Семантика — для нечётких запросов |
| **БД** | Supabase Cloud | Managed PostgreSQL, auto backups, pgvector из коробки, dashboard |
| **Embeddings** | BGE-M3 через FastEmbed (локально) | Бесплатно, мультиязычность (EN/AR), dense + sparse |
| **Admin** | SQLAdmin | Встроен в FastAPI, zero-frontend, CRUD из коробки |

### Критические паттерны

| Паттерн | Описание | Где |
|---------|----------|-----|
| **Message debouncing** | Redis key `debounce:{chat_id}` с TTL 3-5 сек. Серия сообщений -> один batch | Webhook handler |
| **Webhook idempotency** | `SET debounce:{message_id} NX EX 86400`. Дубль -> drop | Webhook handler |
| **OAuth distributed lock** | `SET zoho_refresh_lock NX EX 30`. Один воркер обновляет токен | Zoho integration |
| **Rolling context window** | System prompt + резюме старых сообщений + последние 5 raw | LLM engine |
| **24h WhatsApp rule** | >24ч с последнего сообщения -> только template messages | Messaging layer |
| **PII masking** | UUID вместо реальных данных в LLM-контексте | LLM engine |
| **Multi-model routing** | Haiku для extraction/intent, Sonnet для генерации ответа | LLM engine |
| **English system prompts** | LLM думает на EN, отвечает на языке клиента | Prompts |
| **FSM в PostgreSQL** | Столбец `sales_stage` в conversations. LLM получает правила текущего этапа | Models + LLM |

---

## 11. Устранение неполадок

| Проблема | Причина | Решение |
|----------|---------|---------|
| `docker compose up` падает с ошибкой порта | Порт 5432/6379/8000 уже занят | `lsof -i :PORT` -> `kill PID` или изменить порт в `.env` |
| `alembic upgrade head` — connection refused | БД не запущена или неверный `DATABASE_URL` | Проверить `docker compose ps`, проверить `.env` |
| `asyncpg.InvalidCatalogNameError` | БД не существует | Создать: `CREATE DATABASE treejar;` или проверить Supabase dashboard |
| `pgvector extension not found` | pgvector не установлен | В Supabase: включить через dashboard. Локально: образ `ankane/pgvector:pg17` |
| `ModuleNotFoundError: src` | Неверный PYTHONPATH | Убедиться, что установлен `pip install -e ".[dev]"` или запуск из корня проекта |
| `redis.ConnectionError` | Redis не запущен | `docker compose up -d redis` или проверить `REDIS_URL` |
| Zoho API 429 (rate limit) | Слишком частые запросы | Встроен retry с exponential backoff. Проверить логи на частоту вызовов |
| Zoho OAuth `invalid_grant` | Refresh token протух | Перегенерировать refresh token в Zoho API Console, обновить `.env` |
| Wazzup webhook не приходит | Неверный URL или нет SSL | Проверить URL в кабинете Wazzup, убедиться что HTTPS работает |
| LLM отвечает на английском вместо арабского | Промпт не содержит language instruction | Проверить `src/llm/prompts.py`, передать `language` из conversation |
| `ruff check` — ошибки импортов | Неправильный порядок | `ruff check --fix src/ tests/` — автоисправление |
| `mypy` — ошибки в миграциях | mypy проверяет `migrations/` | В `pyproject.toml` уже настроен `exclude = ["migrations/"]` |
| Тесты падают с `Event loop is closed` | Проблема с pytest-asyncio | Проверить `asyncio_mode = "auto"` в `pyproject.toml` |
| Docker build долгий | Пересборка зависимостей | Использовать Docker layer cache: `docker compose build` (без `--no-cache`) |
| Hot-reload не работает в Docker | Volume не подключён | Запускать через `docker-compose.dev.yml` (монтирует `./src:/app/src`) |
