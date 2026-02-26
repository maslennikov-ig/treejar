# План задач: ИИ-продавец Treejar

**Обновлено:** 2026-02-21
**Общий срок:** 13 недель (16 февраля -- 15 мая 2026)

Отмечайте `[x]` по мере выполнения. Вложенные задачи -- подзадачи, которые можно делать параллельно.

---

## Этап 1: Базовая автоматизация (недели 1-8)

### Неделя 1: Архитектура и проектирование (24ч)

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
### Неделя 2: База знаний + RAG pipeline (40ч)

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

### Неделя 3: LLM ядро + WhatsApp (32ч)

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
- [x] Wazzup интеграция
  - [x] `src/integrations/messaging/wazzup.py` -- реализация `MessagingProvider`
  - [x] Отправка текста, фото, файлов через Wazzup API v3
  - [x] `POST /api/v1/webhook/wazzup` -- полная обработка входящих
  - [x] Message debouncing: Redis key `debounce:{chat_id}` с TTL 3-5 сек
  - [x] Webhook idempotency: `SET NX EX 86400` по message_id
  - [x] ARQ background worker: webhook -> 200 OK за <100ms -> фоновая обработка
- [x] Conversations
  - [x] `GET /api/v1/conversations/` -- реализация (pagination, фильтры)
  - [x] `GET /api/v1/conversations/{id}` -- с сообщениями
  - [x] `PATCH /api/v1/conversations/{id}` -- обновление статуса/этапа
- [x] **Контрольная точка (Этап 1a):** бот отвечает в WhatsApp на тестовые вопросы

#### Дополнительно реализовано (сверх плана Недели 3):
- [x] Тестовое покрытие (Code Coverage) доведено до **91%** (включая безопасность, RAG, API и кэш).
- [x] Интегрирован `deptry` для контроля чистоты зависимостей (проверка в CI).
- [x] Введены строгие Pre-push проверки (Ruff --fix, MyPy --strict, Pytest) для защиты main-ветки.

### Неделя 4: Zoho CRM + проверка остатков (36ч)

- [ ] Zoho CRM коннектор (EU регион: zohoapis.eu, 97 полей контакта, 72 поля сделки)
  - [ ] `src/integrations/crm/zoho_crm.py` -- реализация `CRMProvider`
  - [ ] OAuth2 token management (shared lock с Inventory, единый Zoho One аккаунт)
  - [ ] `find_contact_by_phone()` -- поиск по телефону (поля: Phone, Mobile, WhatsApp)
  - [ ] `create_contact()` -- создание с UTM-метками (utm_source/medium/campaign/content/term, GCLID, Ad_ID)
  - [ ] `create_deal()` -- создание сделки. 12 этапов: Qualification → New Lead → New Lead Saudi Arabia → Negotiations → Offer sent → IN WORK → Order confirmed → Order sent to warehouse → Consignment → Order collected/delivered → ON HOLD → Closed Lost
  - [ ] `update_deal()` -- обновление стадии
  - [ ] Кастомные поля: Segment (9 сегментов), Department_Treejar, Interest, Sales_Person
- [ ] CRM API endpoints
  - [ ] `GET /api/v1/crm/contacts/{phone}` -- реализация
  - [ ] `POST /api/v1/crm/contacts/` -- реализация
  - [ ] `POST /api/v1/crm/deals/` -- реализация
  - [ ] `PATCH /api/v1/crm/deals/{deal_id}` -- реализация
- [ ] LLM tools для CRM
  - [ ] Tool: `lookup_customer` -- поиск клиента в CRM по телефону
  - [ ] Tool: `create_deal` -- создание сделки из диалога
  - [ ] Context enrichment: история покупок из CRM -> system prompt
- [ ] Проверка остатков (Inventory)
  - [ ] `GET /api/v1/inventory/stock/{sku}` -- реализация
  - [ ] `GET /api/v1/inventory/stock/` -- bulk query
  - [ ] Tool: `check_stock` -- для LLM (доступность, цена, склад)
- [ ] Тесты: mock Zoho API, integration для CRM flow

### Неделя 5: Генерация КП (SaleOrder) (36ч)

- [ ] SaleOrder
  - [ ] `POST /api/v1/inventory/sale-orders/` -- реализация
  - [ ] `GET /api/v1/inventory/sale-orders/{order_id}` -- с PDF URL
  - [ ] Zoho Inventory: создание SaleOrder через API
  - [ ] Получение PDF из Zoho и отправка клиенту через Wazzup
- [ ] LLM flow для КП (4 образца КП получены: AA 63K, CH 161K, MS 12K, PY 15K AED. См. `docs/sample-quotations/`)
  - [ ] Tool: `create_quotation` -- собирает данные и создаёт SaleOrder
  - [ ] Структура КП: шапка (Skyland+Treejar), данные клиента, таблица товаров (фото, SKU, описание, QTY, цена), delivery, TOTAL → VAT 5% → GRAND TOTAL
  - [ ] Для крупных проектов -- структурировать по отделам/зонам (как в CH 090226)
  - [ ] FSM: переход в stage `quoting` при согласии клиента
  - [ ] Сбор данных: название компании, email, товары, количество
  - [ ] Подтверждение перед отправкой
- [ ] Тесты: mock SaleOrder creation, PDF flow

### Неделя 6: Персональные цены + эскалация (32ч)

- [ ] Индивидуальные цены и скидки
  - [ ] Таблица скидок: segment -> discount% (из Google Sheets или Zoho)
  - [ ] Определение сегмента клиента (VIP, постоянный, новый)
  - [ ] Персональная цена в ответах бота и КП
- [ ] Передача диалога менеджеру
  - [ ] Логика эскалации: 18 триггеров (просит человека, бот не понимает 2 раза, негатив, заказ >10K AED, нестандартные условия, вопросы вне базы, возврат, просит конкретного менеджера, шоурум, B2B, оптовый заказ, полная меблировка, крупный проект, чертежи/планировки, запрос образцов, не убеждён ботом, хочет звонок, просит менеджера определённой национальности)
  - [ ] Уведомление менеджеру через Wazzup (или Telegram). 7 менеджеров: Israullah, Annabelle, Sreeja, Radhika, Luna, Shariq, Azad
  - [ ] Передача полной истории диалога
  - [ ] Escalation API: `POST /api/v1/conversations/{id}/escalate`
  - [ ] Модель Escalation: запись в БД, статус pending/in_progress/resolved
- [ ] Follow-up и 24h WhatsApp правило
  - [ ] Cron job: проверка last_message_at
  - [ ] Если >24ч -- только template messages через Wazzup (Wazzup Max тариф, HSM-шаблоны НЕ используются)
  - [ ] Follow-up расписание: 24ч → 3д → 7д → 30д → 90д (для крупных B2B)

### Неделя 7: Админ-панель (32ч)

- [ ] SQLAdmin расширение
  - [ ] ModelView для всех 6 таблиц (conversations, messages, products, knowledge_base, quality_reviews, escalations)
  - [ ] Кастомные страницы: список диалогов с фильтрами, детали диалога
  - [ ] Экспорт данных
- [ ] Управление промптами
  - [ ] `GET /api/v1/admin/prompts/` -- реализация
  - [ ] `PUT /api/v1/admin/prompts/{id}` -- редактирование
  - [ ] Версионирование промптов (history)
  - [ ] Хранение в БД (новая таблица `prompts`)
- [ ] Метрики (спецификация: `docs/metrics.md`, 17 метрик в 6 категориях)
  - [ ] `GET /api/v1/admin/metrics/` -- реализация
  - [ ] Объём: диалоги/день/неделю/месяц, уникальные клиенты, новые vs повторные
  - [ ] Классификация: по 9 сегментам, целевой/нецелевой, по языку EN/AR
  - [ ] Эскалация: количество передач, причины по 18 триггерам
  - [ ] Продажи: продажи Noor, после передачи, конверсия ~11%, средний чек AED
  - [ ] Качество: средняя длина диалога, оценка 0-30, время ответа бота
  - [ ] Follow-up: повторные обращения, эффективность (отправлено → ответ → сделка)
  - [ ] Стоимость LLM за период
- [ ] Настройки бота
  - [ ] `GET /api/v1/admin/settings/` -- реализация
  - [ ] `PATCH /api/v1/admin/settings/` -- обновление
  - [ ] Настройки: язык по умолчанию, порог эскалации, follow-up таймаут

### Неделя 8: Тестирование + Деплой (36ч)

- [ ] Тестирование этапа 1
  - [ ] Unit-тесты: LLM engine (mock OpenRouter), RAG pipeline, Zoho clients
  - [ ] Integration-тесты: БД (testcontainers), Redis, API endpoints
  - [ ] E2E-тест: полный цикл webhook -> обработка -> ответ -> CRM
  - [ ] Покрытие >= 80%
  - [ ] Тест арабского языка (RTL, форматирование)
- [ ] Деплой на VPS клиента
  - [ ] Настройка VPS: Docker, firewall (ufw), SSH hardening
  - [ ] SSL сертификат (Let's Encrypt, certbot)
  - [ ] docker-compose up на production
  - [ ] alembic upgrade head на Supabase Cloud
  - [ ] Настройка Wazzup webhook URL
  - [ ] Smoke-тест: отправить сообщение в WhatsApp -> получить ответ
  - [ ] Мониторинг: healthcheck, логи
- [ ] **Контрольная точка (Этап 1b):** полный цикл работает, админка доступна

---

## Этап 2: Контроль и аналитика (недели 9-13)

### Неделя 9-10: Контроль качества (32ч)

- [ ] Quality evaluator
  - [ ] `src/quality/evaluator.py` -- LLM-as-a-judge
  - [ ] 15 критериев оценки из `docs/06-dialogue-evaluation-checklist.md`
  - [ ] Scoring: 0-2 баллов по каждому критерию, total 0-30
  - [ ] Rating: excellent (26-30), good (20-25), satisfactory (14-19), poor (<14)
- [ ] Quality API
  - [ ] `POST /api/v1/quality/reviews/` -- создание оценки (автоматическая)
  - [ ] `GET /api/v1/quality/reviews/` -- список оценок с фильтрами
  - [ ] ARQ job: автоматическая оценка завершённых диалогов
- [ ] Оценка менеджеров
  - [ ] Анализ диалогов живых продавцов (из Wazzup history)
  - [ ] Еженедельные отчёты по менеджерам
  - [ ] Сравнение: бот vs менеджер

### Неделя 11: Уведомления + отчёты (28ч)

- [ ] Telegram-уведомления
  - [ ] Telegram Bot API: создание бота, получение chat_id
  - [ ] Триггеры: негативный отзыв, ошибка бота, долгий ответ менеджера, эскалация
  - [ ] Настройка получателей в админке
- [ ] Отчёты по отказам и конверсии
  - [ ] `POST /api/v1/quality/reports/` -- генерация отчёта
  - [ ] Метрики: диалоги/день, конверсия, причины отказов, средний чек
  - [ ] Отправка на email / Telegram
  - [ ] ARQ cron: еженедельный автоотчёт

### Неделя 12: Рекомендательная + реферальная система (48ч)

- [ ] Рекомендации товаров
  - [ ] Аналоги: pgvector similarity по embedding
  - [ ] Сопутствующие: правила (стол -> кресло, шкаф -> полка)
  - [ ] Cross-sell в диалоге: "Также рекомендуем..."
- [ ] Реферальная система
  - [ ] Новая таблица `referrals` (code, referrer, referee, discount, status)
  - [ ] Генерация уникальных реферальных кодов
  - [ ] Отслеживание использования
  - [ ] Начисление бонусов/скидок
  - [ ] LLM tool: `generate_referral_code`, `apply_referral_code`

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
- [ ] Документация
  - [ ] Обновить README, dev-guide
  - [ ] Инструкция для менеджера (как передать диалог)
  - [ ] Инструкция для администратора (промпты, настройки)
- [ ] **Контрольная точка (Финальная сдача):** все модули работают, отчёты отправляются

---

## Контрольные точки и оплата

| Дата | Этап | Критерий приёмки | Оплата |
|------|------|------------------|--------|
| До старта | Предоплата | -- | 150 000 руб |
| ~6 марта | Этап 1a (неделя 3) | Бот отвечает в WhatsApp на EN/AR | 150 000 руб |
| ~10 апреля | Этап 1b (неделя 8) | Полный цикл: консультация -> КП -> CRM. Админка. Деплой | 150 000 руб |
| ~15 мая | Этап 2 (неделя 13) | Качество, отчёты, рекомендации, рефералы | 150 000 руб |
| При сдаче | Премия за сроки | Все этапы в срок | +100 000 руб |

---

## Статистика прогресса

| Метрика | Значение |
|---------|----------|
| Всего задач верхнего уровня | ~70 |
| Выполнено | 50 (недели 1-3) |
| Оставшиеся часы (по ТЗ) | ~348 из 444 |

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
| `docs/06-dialogue-evaluation-checklist.md` | Методика оценки: 15 правил, шкала 0-2, макс 30 баллов |
| `docs/07-knowledge-base-spec.md` | Спецификация базы знаний |
