# План задач: ИИ-продавец Treejar

**Обновлено:** 2026-03-14
**Общий срок:** 13 недель (16 февраля -- 15 мая 2026)

Отмечайте `[x]` по мере выполнения. Вложенные задачи -- подзадачи, которые можно делать параллельно.

---

## Этап 1: Базовая автоматизация (недели 1-8)

### Неделя 1: Архитектура и проектирование (24ч) ✅

- [x] Схема БД (6 таблиц: conversations, messages, products, knowledge_base, quality_reviews, escalations)
- [x] SQLAlchemy модели + Alembic миграция
- [x] Pydantic-схемы (9 модулей, все API-контракты)
- [x] FastAPI skeleton (8 роутеров, health endpoint рабочий, остальные 501)
- [x] Docker (Dockerfile multi-stage, docker-compose prod + dev, nginx, entrypoint)
- [x] Protocol-абстракции (MessagingProvider, CRMProvider, InventoryProvider, VectorStore)
- [x] CI: GitHub Actions (ruff + mypy + pytest)
- [x] Dev guide, README, .env.example
- [x] Документ для клиента (пошаговые инструкции регистрации сервисов)
- [x] Доступы получены (Zoho CRM, Zoho Inventory, Wazzup, DeepSeek, Shopify bazara.ae)
- [ ] **Ожидание от клиента:** Отдельный выделенный VPS (вместо текущего разделяемого Hetzner) и аккаунт OpenRouter
### Неделя 2: База знаний + RAG pipeline (40ч) ✅

- [x] Zoho Inventory sync -- коннектор
  - [x] `src/integrations/inventory/zoho_inventory.py` -- реализация `InventoryProvider`
  - [x] OAuth2 token management (distributed lock через Redis)
  - [x] Sync job: Zoho Inventory -> PostgreSQL (таблица `products`), фильтр: `status=active AND cf_end_product=true` (856 SKU)
  - [x] ARQ cron task: синхронизация каждый час
- [x] Embeddings
  - [x] `src/rag/embeddings.py` -- BGE-M3 через FastEmbed (локально)
  - [x] Генерация embeddings для products (name_en + description_en + category)
  - [x] Запись в колонку `products.embedding` (pgvector Vector(1024))
- [x] RAG pipeline
  - [x] `src/rag/pipeline.py` -- SQL WHERE + pgvector cosine similarity
  - [ ] LLM-извлечение структурированных фильтров (category, price, color)
  - [x] Fallback: семантический поиск для нечётких запросов
- [x] Knowledge base indexer
  - [x] `src/rag/indexer.py` -- индексация документов: правила диалогов (17 правил), ценности (14), FAQ (20 Q&A), метрики
  - [x] Источники: `docs/faq.md`, `docs/04-sales-dialogue-guidelines.md`, `docs/05-company-values.md`
  - [ ] Парсинг сайтов Treejar (HTML -> текст -> chunks -> embeddings)
- [x] API endpoints
  - [x] `POST /api/v1/products/search` -- реализация поиска
  - [x] `POST /api/v1/products/sync` -- ручной запуск синхронизации
  - [x] `GET /api/v1/products/` -- список товаров с фильтрами
- [x] Тесты: unit для RAG pipeline, integration для sync

### Неделя 3: LLM ядро + WhatsApp (32ч) ✅

- [x] LLM Engine
  - [x] `src/llm/engine.py` -- PydanticAI agent с OpenRouter
  - [x] Multi-model routing: Haiku для extraction, Sonnet для генерации
  - [x] Tool calling: search_products, get_stock, get_customer_info
  - [x] Rolling context window: system prompt + резюме + последние 5 сообщений
  - [x] FSM navigation: sales_stage в system prompt
- [x] Prompts (источники: `docs/04-sales-dialogue-guidelines.md`, `docs/faq.md`, `docs/05-company-values.md`, `docs/dialogue-examples/README.md`)
  - [x] `src/llm/prompts.py` -- system prompt на EN, ответы на языке клиента (EN основной, AR растёт)
  - [x] Промпт для каждого sales_stage (greeting, qualifying, needs_analysis, solution, quoting, closing)
  - [x] Промпт для extraction (intent + structured filters)
  - [x] Правила из анализа реальных диалогов: избегать 8 типичных ошибок менеджеров (см. `docs/dialogue-examples/README.md`)
  - [x] Идеальный цикл продажи (9 шагов): запрос → приветствие → уточнение → показ товара → аналог → sample/шоурум → КП → follow-up → оплата → доставка
  - [x] PII masking: UUID вместо реальных данных в LLM-контексте
  - [x] WhatsApp-совместимое форматирование (жирный, курсив, моно, цитаты)
- [x] Wazzup интеграция
  - [x] `src/integrations/messaging/wazzup.py` -- реализация `MessagingProvider`
  - [x] Отправка текста, фото, файлов через Wazzup API v3
  - [x] `POST /api/v1/webhook/wazzup` -- полная обработка входящих
  - [x] Message debouncing: Redis key `debounce:{chat_id}` с TTL 3-5 сек
  - [x] Webhook idempotency: `SET NX EX 86400` по message_id
  - [x] ARQ background worker: webhook -> 200 OK за <100ms -> фоновая обработка
  - [x] Author routing: client → LLM, manager → save only, bot → skip
- [x] Conversations
  - [x] `GET /api/v1/conversations/` -- реализация (pagination, фильтры)
  - [x] `GET /api/v1/conversations/{id}` -- с сообщениями
  - [x] `PATCH /api/v1/conversations/{id}` -- обновление статуса/этапа
- [x] **Контрольная точка (Этап 1a):** бот отвечает в WhatsApp на тестовые вопросы ✅ Оплачено

#### Дополнительно реализовано (сверх плана Недели 3):
- [x] Тестовое покрытие (Code Coverage) доведено до **91%** (включая безопасность, RAG, API и кэш).
- [x] Интегрирован `deptry` для контроля чистоты зависимостей (проверка в CI).
- [x] Введены строгие Pre-push проверки (Ruff --fix, MyPy --strict, Pytest) для защиты main-ветки.

### Неделя 4: Zoho CRM + проверка остатков (36ч) ✅

- [x] Zoho CRM коннектор (EU регион: zohoapis.eu, 97 полей контакта, 72 поля сделки)
  - [x] `src/integrations/crm/zoho_crm.py` -- реализация `CRMProvider`
  - [x] OAuth2 token management (shared lock с Inventory, единый Zoho One аккаунт)
  - [x] `find_contact_by_phone()` -- поиск по телефону (поля: Phone, Mobile, WhatsApp)
  - [x] `create_contact()` -- создание с UTM-метками (utm_source/medium/campaign/content/term, GCLID, Ad_ID)
  - [x] `create_deal()` -- создание сделки. 12 этапов: Qualification → New Lead → New Lead Saudi Arabia → Negotiations → Offer sent → IN WORK → Order confirmed → Order sent to warehouse → Consignment → Order collected/delivered → ON HOLD → Closed Lost
  - [x] `update_deal()` -- обновление стадии
  - [x] Кастомные поля: Segment (9 сегментов), Department_Treejar, Interest, Sales_Person
- [x] CRM API endpoints
  - [x] `GET /api/v1/crm/contacts/{phone}` -- реализация
  - [x] `POST /api/v1/crm/contacts/` -- реализация
  - [x] `POST /api/v1/crm/deals/` -- реализация
  - [x] `PATCH /api/v1/crm/deals/{deal_id}` -- реализация
- [x] LLM tools для CRM
  - [x] Tool: `lookup_customer` -- поиск клиента в CRM по телефону
  - [x] Tool: `create_deal` -- создание сделки из диалога
  - [ ] Context enrichment: история покупок из CRM -> system prompt
- [x] Проверка остатков (Inventory)
  - [x] `GET /api/v1/inventory/stock/{sku}` -- реализация
  - [x] `GET /api/v1/inventory/stock/` -- bulk query
  - [x] Tool: `check_stock` -- для LLM (доступность, цена, склад)
- [x] Тесты: mock Zoho API, integration для CRM flow

### Неделя 5: Генерация КП / SaleOrder (36ч) ✅

- [x] Инфраструктура PDF (WeasyPrint)
  - [x] Установка `weasyprint`, `jinja2`, настройка Docker-образа (зависмости Pango, HarfBuzz, шрифты для кириллицы)
  - [x] `src/services/pdf/generator.py` -- сервис генерации HTML -> PDF через WeasyPrint (в `run_in_threadpool`)
  - [x] Механизм скачивания/кэширования картинок товаров из Zoho для вставки в HTML
  - [x] Jinja2 шаблоны (`templates/quotation.html` и CSS) с поддержкой разрывов страниц, repeating thead, и footer-а
- [x] Интеграция Sale Order с Zoho Inventory
  - [x] Запись черновика (Draft) Sale Order в Zoho Inventory для складского учета
  - [x] `POST /api/v1/inventory/sale-orders/` -- создание заказа
  - [x] `GET /api/v1/inventory/sale-orders/{order_id}`
- [x] LLM flow для КП (4 образца КП получены: AA, CH, MS, PY. См. `docs/sample-quotations/`)
  - [x] Tool: `create_quotation` -- собирает данные (имя, компания, email, товары, QTY) и формирует структуру
  - [x] Интеграция генерации PDF и отправки через Wazzup (`client.send_media`)
  - [x] FSM: переход в stage `quoting` при согласии клиента
  - [x] Подтверждение менеджером/клиентом перед отправкой
- [x] Тесты: mock WeasyPrint, mock Zoho API, PDF flow

### Неделя 6: Персональные цены + эскалация (32ч) ✅

- [x] Индивидуальные цены и скидки
  - [x] Таблица скидок: segment -> discount% (из Google Sheets или Zoho)
  - [x] Определение сегмента клиента (VIP, постоянный, новый)
  - [x] Персональная цена в ответах бота и КП
- [x] Передача диалога менеджеру
  - [x] Логика эскалации: 18 триггеров (просит человека, бот не понимает 2 раза, негатив, заказ >10K AED, нестандартные условия, вопросы вне базы, возврат, просит конкретного менеджера, шоурум, B2B, оптовый заказ, полная меблировка, крупный проект, чертежи/планировки, запрос образцов, не убеждён ботом, хочет звонок, просит менеджера определённой национальности)
  - [x] Уведомление менеджеру через Wazzup (или Telegram). 7 менеджеров: Israullah, Annabelle, Sreeja, Radhika, Luna, Shariq, Azad
  - [x] Передача полной истории диалога
  - [x] Escalation API: `POST /api/v1/conversations/{id}/escalate`
  - [x] Модель Escalation: запись в БД, статус pending/in_progress/resolved
  - [x] **Manual takeover:** менеджер пишет в чат без эскалации → бот останавливается (escalation_status = manual_takeover)
- [x] Follow-up и 24h WhatsApp правило
  - [x] Cron job: проверка last_message_at
  - [x] Если >24ч -- только template messages через Wazzup (Wazzup Max тариф, HSM-шаблоны НЕ используются)
  - [x] Follow-up расписание: 24ч → 3д → 7д → 30д → 90д (для крупных B2B)

### Неделя 7: Админ-панель (32ч) ✅

> **Архитектура:** Гибрид — SQLAdmin (CRUD) + React/Vite дашборд (аналитика).
> SQLAdmin встроен в FastAPI для управления данными. React/Vite (`frontend/admin/`) — тот же стек, что и лендинг — для дашборда, метрик и отчётов.

- [x] SQLAdmin кастомизация
  - [x] ModelView для всех 6 таблиц (conversations, messages, products, knowledge_base, quality_reviews, escalations)
  - [x] `column_filters` и `column_searchable_list` для фильтрации по статусу, языку, дате
  - [x] `column_formatters` для отображения relationships (диалог → кол-во сообщений)
  - [x] Экспорт данных (кастомный action → CSV)
- [x] Управление промптами (через SQLAdmin)
  - [x] ModelView для `system_prompts` с inline-редактированием
  - [x] Версионирование: автоинкремент `version` при сохранении, хранение предыдущих версий
  - [x] Хранение в БД (таблица `system_prompts` уже создана)
- [x] React/Vite дашборд (`frontend/admin/`)
  - [x] Инициализация проекта (React + Vite + Tailwind, аналогично `frontend/landing/`)
  - [x] API endpoints для метрик: `GET /api/v1/admin/metrics/`
  - [x] Дашборд с KPI-карточками и графиками (Recharts / Tremor)
  - [x] Метрики (спецификация: `docs/metrics.md`, 17 метрик в 6 категориях):
    - [x] Объём: диалоги/день/неделю/месяц, уникальные клиенты, новые vs повторные
    - [x] Классификация: по 9 сегментам, целевой/нецелевой, по языку EN/AR
    - [x] Эскалация: количество передач, причины по 18 триггерам
    - [x] Продажи: продажи Noor, после передачи, конверсия ~11%, средний чек AED
    - [x] Качество: средняя длина диалога, оценка 0-30, время ответа бота
    - [x] Follow-up: повторные обращения, эффективность (отправлено → ответ → сделка)
    - [x] Стоимость LLM за период
  - [x] Интеграция в Docker build (stage в Dockerfile, аналогично лендингу)
  - [x] Роутинг через FastAPI: `/dashboard/*` → Vite SPA
- [x] Настройки бота (через SQLAdmin)
  - [x] ModelView для `system_config` с редактированием JSONB-значений
  - [x] Настройки: язык по умолчанию, порог эскалации, follow-up таймаут

### Неделя 8: Тестирование + Деплой (36ч) ✅

- [x] Тестирование этапа 1
  - [x] Unit-тесты: LLM engine (mock OpenRouter), RAG pipeline, Zoho clients
  - [x] Integration-тесты: БД (testcontainers), Redis, API endpoints
  - [x] E2E-тест: полный цикл webhook -> обработка -> ответ -> CRM
  - [x] Покрытие >= 80%
  - [x] Тест арабского языка (RTL, форматирование)
- [x] Деплой на VPS клиента
  - [x] Настройка VPS: Docker, firewall (ufw), SSH hardening
  - [x] SSL сертификат (Let's Encrypt, certbot)
  - [x] docker-compose up на production
  - [x] alembic upgrade head на Supabase Cloud
  - [x] Настройка Wazzup webhook URL
  - [x] Smoke-тест: отправить сообщение в WhatsApp -> получить ответ
  - [x] Мониторинг: healthcheck, логи
- [x] **Контрольная точка (Этап 1b):** полный цикл работает, админка доступна

---

## Этап 2: Контроль и аналитика (недели 9-13)

### Неделя 9-10: Контроль качества (32ч) ✅

- [x] Quality evaluator
  - [x] `src/quality/evaluator.py` -- LLM-as-a-judge
  - [x] 15 критериев оценки из `docs/06-dialogue-evaluation-checklist.md`
  - [x] Scoring: 0-2 баллов по каждому критерию, total 0-30
  - [x] Rating: excellent (26-30), good (20-25), satisfactory (14-19), poor (<14)
- [x] Quality API
  - [x] `POST /api/v1/quality/reviews/` -- создание оценки (автоматическая)
  - [x] `GET /api/v1/quality/reviews/` -- список оценок с фильтрами
  - [x] ARQ job: автоматическая оценка завершённых диалогов
- [x] Оценка менеджеров (**merged 2026-03-14**)
  - [x] `src/quality/manager_evaluator.py` -- LLM-судья с 10 критериями (макс 20 баллов)
  - [x] `src/quality/manager_schemas.py` -- Pydantic-схемы для Manager Assessment
  - [x] `src/quality/manager_job.py` -- ARQ cron job: автоматическая оценка
  - [x] `migrations/.../add_manager_reviews_table.py` -- таблица manager_reviews
  - [x] Количественные метрики: SLA, время ответа, конверсия, средний чек
  - [x] Dashboard KPI: avg_manager_score, leaderboard, response_time
  - [x] Telegram weekly report: секция Manager Performance
  - [x] Author routing в webhook: client/manager/bot через Wazzup authorType
  - [x] Manual takeover: менеджер перехватывает диалог без формальной эскалации
  - [x] Bot silencing: бот молчит при активной эскалации/takeover
  - [x] API: `GET /api/v1/manager-reviews/`, `POST /{escalation_id}/evaluate`
  - [x] 8 файлов тестов, 39 тестов (all green)

### Неделя 11: Уведомления + отчёты (28ч) ✅

- [x] Telegram-уведомления
  - [x] Telegram Bot API: `TelegramClient` с retries, no-op guard
  - [x] Триггеры: эскалация, low quality score, daily summary
  - [x] API: `POST /notifications/test`, `GET /notifications/config`
  - [x] PII masking: `_mask_phone()` для телефонов в Telegram
- [x] Отчёты по отказам и конверсии
  - [x] `POST /api/v1/reports/generate` -- генерация отчёта (ReportData model)
  - [x] Метрики: диалоги/день, конверсия, причины отказов, средний чек, top products
  - [x] Отправка через Telegram `send_message` + `send_document`
  - [x] ARQ cron: еженедельный автоотчёт (Monday 06:00 UTC)

### Неделя 12: Рекомендательная + реферальная система (48ч) ✅

- [x] Рекомендации товаров
  - [x] Аналоги: pgvector similarity по embedding (`get_similar_products`)
  - [x] Сопутствующие: правила из SystemConfig (`get_cross_sell`)
  - [x] Cross-sell в диалоге: LLM tool `recommend_products`
  - [x] API: `GET /products/{id}/similar`, `GET /products/{id}/cross-sell`
- [x] Реферальная система
  - [x] Новая таблица `referrals` + Alembic миграция (code, referrer, referee, discount, status)
  - [x] Генерация уникальных реферальных кодов (NOOR-XXXXX, IntegrityError retry)
  - [x] Отслеживание использования (`apply_code`, проверки: expired/used/self-referral)
  - [x] Начисление бонусов/скидок (referrer 5%, referee 10%)
  - [x] LLM tool: `generate_referral_code`, `apply_referral_code`
  - [x] API: `POST /referrals/generate`, `POST /referrals/apply`, `GET /referrals/{phone}/stats`

### Неделя 13: Финальное тестирование (24ч)

- [ ] E2E тесты этапа 2
  - [ ] Quality evaluation flow
  - [ ] Telegram notification delivery
  - [ ] Report generation
  - [ ] Referral code lifecycle
- [ ] Нагрузочное тестирование
  - [ ] 50+ одновременных диалогов
  - [ ] Rate limiting, debouncing под нагрузкой
- [ ] Security audit
  - [ ] Проверка .env (нет секретов в коде)
  - [ ] SQL injection, XSS в админке
  - [ ] Wazzup webhook signature verification
- [x] Документация
  - [x] Обновить README, dev-guide
  - [x] Инструкция для менеджера (`docs/manager-guide.md`)
  - [x] Инструкция для администратора (`docs/admin-guide.md`)
- [ ] **Контрольная точка (Финальная сдача):** все модули работают, отчёты отправляются

---

## Нереализованные требования ТЗ (backlog)

> Эти задачи выявлены при аудите 2026-03-13 и заведены в Beads.

| ID | Приоритет | Требование ТЗ | Статус |
|----|-----------|---------------|--------|
| `tj-6mv` | P1 | **Распознавание голосовых сообщений** (Whisper API, EN/AR) | open |
| `tj-dpv` | P2 | **Статус заказа клиента** (check_order_status через Zoho CRM/Inventory) | open |
| `tj-lzt` | P2 | **Сбор обратной связи** после закрытия сделки (ratings, NPS) | open |

### Мелкие доработки (не заведены как задачи):
- [ ] LLM tool для отправки фото товара по запросу (`send_product_photo`)
- [ ] LLM-извлечение структурированных фильтров (category, price, color) в RAG
- [ ] Context enrichment: история покупок из CRM -> system prompt
- [ ] Парсинг сайтов Treejar (HTML -> текст -> chunks -> embeddings)
- [ ] Обновить `docs/architecture.md` (Qdrant → pgvector, Jina → BGE-M3)

---

## Контрольные точки и оплата

| Дата | Этап | Критерий приёмки | Оплата | Статус |
|------|------|------------------|--------|--------|
| До старта | Предоплата | — | 150 000 руб | ✅ Оплачено |
| ~6 марта | Этап 1a (неделя 3) | Бот отвечает в WhatsApp на EN/AR | 150 000 руб | ✅ Оплачено |
| ~10 апреля | Этап 1b (неделя 8) | Полный цикл: консультация -> КП -> CRM. Админка. Деплой | 150 000 руб | ⏳ Ожидает приёмки |
| ~15 мая | Этап 2 (неделя 13) | Качество, отчёты, рекомендации, рефералы | 150 000 руб | ⏳ В работе |
| При сдаче | Премия за сроки | Все этапы в срок | +100 000 руб | ⏳ |

---

## Статистика прогресса

| Метрика | Значение |
|---------|----------|
| Всего задач верхнего уровня | ~75 |
| Выполнено | ~69 (недели 1-12 + доработки) |
| Осталось (план) | ~6 (неделя 13 + 3 требования ТЗ) |
| Текущая неделя по roadmap | 4 (фактически: неделя 12 завершена) |
| Тесты | 294 passed, 91% coverage |
| Модели БД | 12 (+ system_prompts, system_config, referrals, manager_reviews, metrics_snapshot) |
| API endpoints | 25+ |
| Деплой | Production (noor.starec.ai), Dev (dev.noor.starec.ai) |

---

## Ключевые документы-источники

| Документ | Содержание |
|----------|-----------|
| `docs/checklist-answers.md` | Ответы клиента: API scopes, CRM-поля (97+72), 18 триггеров эскалации, 9 сегментов, 12 этапов воронки |
| `docs/faq.md` | 20 FAQ на EN для базы знаний бота |
| `docs/metrics.md` | 17 метрик админ-панели + follow-up расписание (24ч/3д/7д/30д/90д) |
| `docs/dialogue-examples/README.md` | 13 диалогов: 7 успешных, 2 средних, 4 неудачных + 8 ошибок + 9-шаговый идеальный цикл |
| `docs/sample-quotations/README.md` | 4 образца КП (12K-161K AED) + структура |
| `docs/04-sales-dialogue-guidelines.md` | 17 правил ведения диалогов (RU + EN) |
| `docs/05-company-values.md` | 14 ценностей компании (RU + EN) |
| `docs/06-dialogue-evaluation-checklist.md` | Методика оценки бота: 15 правил, шкала 0-2, макс 30 баллов |
| `docs/07-knowledge-base-spec.md` | Спецификация базы знаний |
| `docs/08-manager-evaluation-criteria.md` | Методика оценки менеджеров: 10 критериев, шкала 0-2, макс 20 баллов |
