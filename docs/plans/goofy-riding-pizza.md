# Синхронизация данных из клиентского репозитория

## Контекст

Клиент предоставил публичный репозиторий `Starec-net/noor-ai-seller` с документацией проекта. Нужно выяснить, есть ли там полезная информация, которой нет в нашем репозитории, и синхронизировать её.

---

## Результаты исследования

### Сравнение файлов: клиентский vs наш репозиторий

| Файл в клиентском репо | Наш эквивалент | Статус |
|---|---|---|
| `docs/sales-dialogue-rules.md` | `docs/04-sales-dialogue-guidelines.md` | ДУБЛИКАТ (тот же контент, наш подробнее) |
| `docs/treejar-values.md` | `docs/05-company-values.md` | ДУБЛИКАТ (тот же контент) |
| `docs/evaluation-checklist.md` | `docs/06-dialogue-evaluation-checklist.md` | ДУБЛИКАТ (тот же контент) |
| `docs/faq.md` | **Нет** | ОТСУТСТВУЕТ — 20 FAQ на EN |
| `docs/metrics.md` | **Нет** | ОТСУТСТВУЕТ — 17 метрик + follow-up периоды |
| `docs/checklist-answers.md` | Частично в `response-to-client-2026-02-17.md` | УНИКАЛЬНАЯ ИНФОРМАЦИЯ — подробнее (см. ниже) |
| `docs/dialogue-stats.csv` | **Нет** | ОТСУТСТВУЕТ — помесячная статистика |
| `docs/dialogue-examples/README.md` | **Нет** | УНИКАЛЬНО — 13 классифицированных диалогов + анализ |
| `docs/sample-quotations/README.md` | **Нет** | УНИКАЛЬНО — 4 образца КП + разбор структуры |
| `CLAUDE.md` | Другой (наш CLAUDE.md — инструкции для агента) | УНИКАЛЬНО — полный бизнес-контекст проекта |
| `docs/tz.md` | `docs/01-tz-basic.md` + `docs/02-tz-extended.md` | Есть |
| `docs/architecture.md` | `docs/architecture.md` | Есть |
| `docs/roadmap.md` | `docs/roadmap.md` | Есть |

### Ключевые находки (новая информация)

**1. `docs/checklist-answers.md` — САМЫЙ ЦЕННЫЙ файл**
- Точные Zoho API scopes (CRM + Inventory)
- 97 полей контакта, 72 поля сделки в Zoho CRM (включая кастомные: `Segment`, `Department_Treejar`, `Interest`, `WhatsApp_chat`, `Sales_Person`, UTM-поля)
- **18 триггеров эскалации** (не 8, как мы считали ранее!)
- 9 сегментов клиентов с количеством (End-client B2C: 363, Wholesale: 169, Retail chain B2B: 175, etc.)
- 12 этапов воронки сделки (полный список)
- Кастомное поле `cf_end_product` для фильтрации товаров
- Wazzup: тариф Max, 2 номера, HSM-шаблоны НЕ используются
- Домен `starec.ai` доступен для бота (например, `noor.starec.ai`)
- Bazara.ae (Shopify) — API получен

**2. `docs/faq.md` — 20 FAQ на английском**
- Готовые ответы для базы знаний бота
- Темы: производитель vs трейдер, наличие, кастом, доставка, гарантия, оптовые заказы, оплата

**3. `docs/metrics.md` — 17 метрик для админ-панели**
- 6 категорий: Объём, Классификация, Эскалация, Продажи, Качество, Follow-up
- Точные follow-up периоды: 24ч → 3д → 7д → 30д → 90д (для B2B)

**4. `docs/sample-quotations/README.md` — 4 образца КП**
- AA 291225 (63K AED, bulk adjustable desks)
- CH 090226 (161K AED, 11 стр, полная меблировка по отделам — ИДЕАЛЬНЫЙ образец)
- MS 220525 (12K AED, малый офис)
- PY 291225 (15K AED, стартап)
- Полная структура КП: шапка, данные клиента, таблица товаров (фото, SKU, описание, QTY, цена), delivery, TOTAL → VAT 5% → GRAND TOTAL, Terms

**5. `docs/dialogue-examples/README.md` — 13 классифицированных диалогов**
- 7 успешных, 2 средних, 4 неудачных (с детальным разбором ошибок)
- 59 скриншотов реальных WhatsApp-диалогов
- Контакты 7 менеджеров (телефоны + email)
- 8 типичных ошибок менеджеров и как их избежать
- Идеальный цикл продажи из 9 шагов

**6. `CLAUDE.md` клиентского репо — полный бизнес-контекст**
- 18 триггеров эскалации (полный список)
- Структура КП с правилами
- Типичные ошибки менеджеров
- Идеальный цикл продажи

### Что нужно обновить в наших существующих файлах

**`docs/client-action-items.md`:**
- Убрать "Пример идеального КП" из раздела "Нужно позже" — 4 КП уже получены

**`docs/task-plan.md`:**
- Отразить 18 триггеров эскалации (не 8)
- Добавить: `cf_end_product` фильтрацию в sync job
- Учесть follow-up расписание (24ч, 3д, 7д, 30д, 90д)

---

## План действий

### 1. Скопировать уникальные файлы из клиентского репозитория

Файлы, которых нет у нас и которые содержат уникальную информацию:

| Файл | Куда в нашем репо | Зачем |
|---|---|---|
| `docs/checklist-answers.md` | `docs/checklist-answers.md` | Главный справочник: API scopes, CRM-поля, эскалация, сегменты |
| `docs/faq.md` | `docs/faq.md` | Готовая база знаний (20 Q&A) для RAG pipeline |
| `docs/metrics.md` | `docs/metrics.md` | Спецификация метрик админ-панели + follow-up |
| `docs/dialogue-examples/README.md` | `docs/dialogue-examples/README.md` | Анализ 13 диалогов + ошибки + идеальный цикл |
| `docs/sample-quotations/README.md` | `docs/sample-quotations/README.md` | Структура КП + анализ 4 образцов |
| `docs/dialogue-stats.csv` | `docs/dialogue-stats.csv` (gitignored) | Статистика обращений за 20 месяцев |

**НЕ копируем** (дубликаты наших файлов):
- `docs/sales-dialogue-rules.md` (= наш `04-sales-dialogue-guidelines.md`)
- `docs/treejar-values.md` (= наш `05-company-values.md`)
- `docs/evaluation-checklist.md` (= наш `06-dialogue-evaluation-checklist.md`)
- `docs/tz.md` (= наш `01-tz-basic.md` + `02-tz-extended.md`)
- `docs/architecture.md` (уже есть)
- `docs/roadmap.md` (уже есть)

### 2. Обновить `docs/client-action-items.md`

- Удалить "Пример идеального КП (PDF)" из раздела "Материалы по ходу разработки" и чек-листа — 4 КП уже получены

### 3. Обновить `.gitignore`

- Добавить `docs/dialogue-stats.csv` (если не покрывается `*.csv`)

### 4. Уведомить клиента о безопасности

В клиентском репо файл `.env.keys` содержит реальные API-ключи. Хотя репо приватное, это рискованная практика. Стоит порекомендовать клиенту перенести ключи в Vault/1Password и удалить `.env.keys` из репозитория.

---

## Верификация

1. Все 6 файлов скопированы в наш репо
2. `docs/client-action-items.md` обновлён (КП убрано из "нужно")
3. `git status` — новые файлы в staging
4. `ruff check src/` — без ошибок (docs не проверяются)
5. Коммит и push
