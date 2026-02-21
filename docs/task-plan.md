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
- [ ] **Ожидание от клиента:** доступы к Zoho CRM, Zoho Inventory, Wazzup, Supabase, OpenRouter

### Неделя 2: База знаний + RAG pipeline (40ч)

- [ ] Zoho Inventory sync -- коннектор
  - [ ] `src/integrations/inventory/zoho_inventory.py` -- реализация `InventoryProvider`
  - [ ] OAuth2 token management (distributed lock через Redis)
  - [ ] Sync job: Zoho Inventory -> PostgreSQL (таблица `products`)
  - [ ] ARQ cron task: синхронизация каждый час
- [ ] Embeddings
  - [ ] `src/rag/embeddings.py` -- BGE-M3 через FastEmbed (локально)
  - [ ] Генерация embeddings для products (name_en + description_en + category)
  - [ ] Запись в колонку `products.embedding` (pgvector Vector(1024))
- [ ] RAG pipeline
  - [ ] `src/rag/pipeline.py` -- SQL WHERE + pgvector cosine similarity
  - [ ] LLM-извлечение структурированных фильтров (category, price, color)
  - [ ] Fallback: семантический поиск для нечётких запросов
- [ ] Knowledge base indexer
  - [ ] `src/rag/indexer.py` -- индексация документов (правила диалогов, преимущества, FAQ)
  - [ ] Парсинг сайтов Treejar (HTML -> текст -> chunks -> embeddings)
- [ ] API endpoints
  - [ ] `POST /api/v1/products/search` -- реализация поиска
  - [ ] `POST /api/v1/products/sync` -- ручной запуск синхронизации
  - [ ] `GET /api/v1/products/` -- список товаров с фильтрами
- [ ] Тесты: unit для RAG pipeline, integration для sync

### Неделя 3: LLM ядро + WhatsApp (32ч)

- [ ] LLM Engine
  - [ ] `src/llm/engine.py` -- PydanticAI agent с OpenRouter
  - [ ] Multi-model routing: Haiku для extraction, Sonnet для генерации
  - [ ] Tool calling: search_products, get_stock, get_customer_info
  - [ ] Rolling context window: system prompt + резюме + последние 5 сообщений
  - [ ] FSM navigation: sales_stage в system prompt
- [ ] Prompts
  - [ ] `src/llm/prompts.py` -- system prompt на EN, ответы на языке клиента
  - [ ] Промпт для каждого sales_stage (greeting, qualifying, needs_analysis, solution, quoting, closing)
  - [ ] Промпт для extraction (intent + structured filters)
  - [ ] PII masking: UUID вместо реальных данных в LLM-контексте
- [ ] Wazzup интеграция
  - [ ] `src/integrations/messaging/wazzup.py` -- реализация `MessagingProvider`
  - [ ] Отправка текста, фото, файлов через Wazzup API v3
  - [ ] `POST /api/v1/webhook/wazzup` -- полная обработка входящих
  - [ ] Message debouncing: Redis key `debounce:{chat_id}` с TTL 3-5 сек
  - [ ] Webhook idempotency: `SET NX EX 86400` по message_id
  - [ ] ARQ background worker: webhook -> 200 OK за <100ms -> фоновая обработка
- [ ] Conversations
  - [ ] `GET /api/v1/conversations/` -- реализация (pagination, фильтры)
  - [ ] `GET /api/v1/conversations/{id}` -- с сообщениями
  - [ ] `PATCH /api/v1/conversations/{id}` -- обновление статуса/этапа
- [ ] **Контрольная точка (Этап 1a):** бот отвечает в WhatsApp на тестовые вопросы

### Неделя 4: Zoho CRM + проверка остатков (36ч)

- [ ] Zoho CRM коннектор
  - [ ] `src/integrations/crm/zoho_crm.py` -- реализация `CRMProvider`
  - [ ] OAuth2 token management (shared lock с Inventory)
  - [ ] `find_contact_by_phone()` -- поиск по телефону
  - [ ] `create_contact()` -- создание с UTM-метками
  - [ ] `create_deal()` -- создание сделки
  - [ ] `update_deal()` -- обновление стадии
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
- [ ] LLM flow для КП
  - [ ] Tool: `create_quotation` -- собирает данные и создаёт SaleOrder
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
  - [ ] Логика эскалации: триггеры (жалоба, крупный заказ, нестандартный запрос, явная просьба)
  - [ ] Уведомление менеджеру через Wazzup (или Telegram)
  - [ ] Передача полной истории диалога
  - [ ] Escalation API: `POST /api/v1/conversations/{id}/escalate`
  - [ ] Модель Escalation: запись в БД, статус pending/in_progress/resolved
- [ ] 24h WhatsApp правило
  - [ ] Cron job: проверка last_message_at
  - [ ] Если >24ч -- только template messages через Wazzup

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
- [ ] Метрики
  - [ ] `GET /api/v1/admin/metrics/` -- реализация
  - [ ] Кол-во диалогов за период, средняя длительность
  - [ ] Стоимость LLM за период
  - [ ] Количество эскалаций, конверсия (если есть данные)
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
| Выполнено | 10 (неделя 1) |
| Оставшиеся часы (по ТЗ) | ~420 из 444 |
