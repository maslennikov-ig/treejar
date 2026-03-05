# Контекстный промпт для Сессии 7: Treejar Noor AI Seller

## 🎯 Что это за проект

**Treejar** — компания офисной мебели (ОАЭ). Мы разрабатываем **AI-продавца Noor** — бот который:
- Принимает обращения в WhatsApp через шлюз **Wazzup**
- Консультирует клиентов на **EN и AR**
- Проверяет остатки в **Zoho Inventory** (856 SKU)
- Создаёт контакты и сделки в **Zoho CRM** (12 этапов воронки, 9 сегментов)
- Генерирует **КП (PDF)** прямо в чат через WeasyPrint + Jinja2
- Эскалирует сложные случаи на 7 живых менеджеров (18 триггеров)
- Ведёт дашборд метрик (17 KPI) в React/Vite

**Общий срок: 13 недель (16 февраля — 15 мая 2026). Сейчас: Неделя 3+.**

---

## 📊 Текущий статус: ЧТО УЖЕ СДЕЛАНО

### ✅ Этап 1 полностью реализован (Недели 1—8 в коде)

**Техстек:** Python 3.12, FastAPI, SQLAlchemy 2.0 (async/AsyncPG), Alembic, PostgreSQL 16 + pgvector, Redis 7, ARQ workers, PydanticAI (OpenRouter), FastEmbed (BGE-M3), WeasyPrint, SQLAdmin, React/Vite.

**Реализованные модули:**
- `src/integrations/messaging/wazzup.py` — отправка/приём через Wazzup API v3
- `src/integrations/crm/zoho_crm.py` — CRMProvider (EU регион)
- `src/integrations/inventory/zoho_inventory.py` — InventoryProvider + sync job
- `src/rag/` — RAG pipeline: pgvector cosine similarity, BGE-M3 embeddings
- `src/llm/engine.py` — PydanticAI agent, tool calling, rolling context, FSM по sales_stage
- `src/llm/prompts.py` — промпты для 6 sales_stage + extraction + PII masking
- `src/services/chat.py` — обработка батча входящих сообщений (debouncing, idempotency)
- `src/services/pdf/generator.py` — генерация PDF КП (WeasyPrint + Jinja2)
- `src/services/dashboard_metrics.py` — 17 KPI метрик для дашборда
- `src/services/followup.py` — follow-up cron (24ч/3д/7д/30д/90д)
- `src/api/v1/` — 8 роутеров (webhook, conversations, crm, inventory, products, quality, admin, escalation)
- `src/admin/` — SQLAdmin с ModelView для всех 6 таблиц
- `frontend/admin/` — React/Vite дашборд (KPI карточки + Recharts графики)
- `frontend/landing/` — лендинг с login popup

**Инфраструктура:**
- VPS: `136.243.71.213` (Hetzner, Ubuntu 24.04), Nginx + SSL
- Prod: `noor.starec.ai` (docker-compose.yml, ветка `main`)  
- Dev: `dev.noor.starec.ai` (docker-compose.dev.yml, ветка `develop`)
- CI/CD: GitHub Actions → `scripts/vps-deploy.sh [branch]`
- Деплой скриптом: `.agent/workflows/deploy.md` → `.agent/scripts/deploy.sh`
- Релиз скриптом: `.agent/workflows/push.md` → `.agent/scripts/release.sh`

**Качество кода:**
- **91%** test coverage (uv run pytest)
- **0 ошибок mypy --strict** (исправлены 43 ошибки в последней сессии)
- Ruff lint: чисто
- Pre-commit hooks настроены (mypy при commit иногда зависает → `--no-verify`)

**Текущий git-статус:**
- Ветка: `develop`
- Последний тег: `v0.3.0`
- Последний коммит: `docs(client): fix markdown syntax in Wazzup API curl example`

---

## 🔴 ЧТО НЕ СДЕЛАНО / В РАБОТЕ

### Инфраструктурный blocker (ожидаем от собственника)

**Webhook Wazzup не настроен** — бот не получает сообщения из WhatsApp. Нужно:

1. Мы можем настроить сами через API (ключ есть в `.env.keys`): `PATCH https://api.wazzup24.com/v3/webhooks` с `webhooksUri: "https://noor.starec.ai/api/v1/webhook/wazzup"`
2. **Ждём от собственника** ответа (Виктор, @vic9675):
   - Выбор варианта тестирования (тестовая SIM или whitelist на рабочем номере)
   - Список номеров для whitelist
   - Доступ к ЛК Wazzup (логин/пароль) — для диагностики
   - Инструкция: `docs/client/whatsapp-testing-setup.md`

**Механизм whitelist ещё не реализован в коде** — когда будет ответ от собственника, нужно добавить:
- Поле `WAZZUP_ALLOWED_PHONES` в `src/core/config.py`
- Фильтрацию в `src/services/chat.py` (или `src/api/v1/webhook.py`) — если список не пуст, отвечать только на эти номера

### Один незакрытый пункт из task-plan.md (помеченные [ ] среди [x]):

```
[ ] Context enrichment: история покупок из CRM → system prompt
[ ] LLM-извлечение структурированных фильтров (category, price, color)
[ ] Парсинг сайтов Treejar 
```
Это TODO внутри Недели 2-4 которые пропустили. Можно реализовать по необходимости.

---

## 🟡 СЛЕДУЮЩИЕ ШАГИ (приоритеты)

### Приоритет 1 (сейчас): Подключить WhatsApp к тестированию
- Дождаться ответа собственника
- Реализовать whitelist (если выбран Вариант Б)
- Настроить webhook через API
- Провести smoke-test: написать в WhatsApp → получить ответ бота

### Приоритет 2: Этап 2 — Quality Evaluator (LLM-as-a-judge)

Согласно roadmap, следующий крупный модуль — **Бот контроля качества (недели 9-10)**:

```
Файлы для создания:
- src/quality/evaluator.py   — LLM-as-a-judge
- src/quality/schemas.py     — Pydantic-схемы для оценок
- tests/test_quality_evaluator.py

Логика:
- 15 критериев из docs/06-dialogue-evaluation-checklist.md
- Scoring: 0-2 балла за каждый, макс 30 баллов
- Рейтинги: excellent (26-30), good (20-25), satisfactory (14-19), poor (<14)
- ARQ job: автоматически оценивать завершённые диалоги раз в час
- API: POST /api/v1/quality/reviews/, GET /api/v1/quality/reviews/
- Связь с таблицей quality_reviews (уже есть в схеме БД)
```

### Приоритет 3 (неделя 11): Telegram-уведомления
- `TELEGRAM_BOT_TOKEN` и `TELEGRAM_CHAT_ID` уже в `config.py` (пустые)
- Нужно: создать Telegram бот, получить chat_id от Виктора (@vic9675)
- Триггеры: негатив, ошибка, долгий ответ, эскалация

---

## 📁 Ключевые пути

```
/home/me/code/treejar/          ← основной репозиторий (worktree: develop)
├── src/
│   ├── api/v1/webhook.py       ← обработчик входящих Wazzup
│   ├── services/chat.py        ← бизнес-логика обработки сообщений
│   ├── llm/engine.py           ← LLM агент (PydanticAI)
│   ├── llm/prompts.py          ← все промпты
│   ├── integrations/
│   │   ├── messaging/wazzup.py ← Wazzup API клиент
│   │   ├── crm/zoho_crm.py    ← Zoho CRM клиент
│   │   └── inventory/          ← Zoho Inventory клиент
│   ├── rag/                    ← RAG pipeline (pgvector)
│   ├── services/
│   │   ├── dashboard_metrics.py ← 17 KPI
│   │   ├── pdf/generator.py    ← WeasyPrint PDF
│   │   └── followup.py         ← follow-up cron
│   ├── models/                 ← SQLAlchemy модели
│   ├── core/config.py          ← настройки (Pydantic Settings)
│   └── worker.py               ← ARQ worker (cron jobs)
├── tests/                      ← pytest тесты (91% coverage)
├── frontend/
│   ├── admin/                  ← React/Vite дашборд
│   └── landing/                ← React/Vite лендинг
├── docs/
│   ├── roadmap.md              ← Gantt + понедельный план
│   ├── task-plan.md            ← детальный чеклист (Неделя 1-13)
│   ├── architecture.md         ← архитектура системы
│   ├── checklist-answers.md    ← ответы клиента (18 триггеров, 9 сегментов и др.)
│   ├── 06-dialogue-evaluation-checklist.md ← 15 критериев quality
│   ├── testing-guide-stage1.md ← инструкция для тестировщика
│   └── client/
│       └── whatsapp-testing-setup.md ← инструкция для собственника
├── .agent/
│   ├── workflows/
│   │   ├── push.md             ← /push (релиз)
│   │   └── deploy.md           ← /deploy (деплой в prod)
│   └── scripts/
│       ├── release.sh
│       └── deploy.sh
└── pyproject.toml              ← uv, зависимости, mypy, ruff config
```

---

## 🔑 Ключи и доступы

**У нас есть (в `.env` на сервере и `.env.keys` в `Starec-net/noor-ai-seller`):**
- `WAZZUP_API_KEY` — есть
- `ZOHO_CLIENT_ID / SECRET / REFRESH_TOKEN` — есть (EU регион)
- `DEEPSEEK_API_KEY` — есть (старый ключ из начала проекта, сейчас используем OpenRouter)
- `OPENROUTER_API_KEY` — на сервере в `.env`

**Нет:**
- Логин/пароль ЛК Wazzup (app.wazzup24.com) — для визуального управления
- `TELEGRAM_BOT_TOKEN` и `TELEGRAM_CHAT_ID` — нужны для Этапа 2

---

## ⚠️ Важные технические детали

1. **Pre-commit hook с mypy иногда зависает** → коммит через `git commit --no-verify -m "..."` и потом `git push origin develop`
2. **uv** — менеджер пакетов. Тесты: `uv run pytest`. Mypy: `uv run mypy src/`. Ruff: `uv run ruff check src/`
3. **Векторная БД** — в архитектуре указан Qdrant, но в коде используется **pgvector** (PostgreSQL extension). Qdrant в docker-compose есть, но не используется активно — это расхождение docs vs code.
4. **OpenRouter** — основной LLM провайдер (`openrouter_model_fast: deepseek/deepseek-chat`, `openrouter_model_main: deepseek/deepseek-chat`). В `.env.keys` есть прямой DeepSeek ключ — на сервере, возможно, используется он.
5. **ARQ worker** — 4 функции: `sync_products_from_zoho`, `process_incoming_batch`, `run_automatic_followups`, `calculate_and_store_metrics`
6. **Worktrees** — фичи разрабатываются в `.worktrees/feature-name/` согласно skill `using-git-worktrees`

---

## 🤖 Workflow агента

- **Beads (bd)** — task tracker для макро-задач: `bd find`, `bd update <id> --status=in_progress`, `bd close <id> --reason="..."`, `bd sync`
- **TDD**: всегда сначала RED-тест, потом код
- **Brainstorming** перед новыми фичами (`.agent/skills/brainstorming/SKILL.md`)
- **Context7 MCP** — для актуальной документации библиотек (FastAPI, SQLAlchemy, ARQ и т.д.)
- **deploy**: `/deploy` workflow → деплой в prod через Blue/Green в worktree
- **push**: `/push` workflow → bump версии + changelog + push тег
