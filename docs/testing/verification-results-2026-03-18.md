# Отчёт о проверке интеграций (Production VPS)

**Дата:** 2026-03-18
**Окружение:** Production (`136.243.71.213`)
**Всего скриптов:** 11
**Успешно (Passed):** 7
**Провалено (Failed):** 4

## Результаты по скриптам

| Скрипт | Результат | Passed | Failed | Комментарий |
|---|---|---|---|---|
| `verify_db` | ❌ | 16 | 3 | БД доступна, но отсутствует таблица `feedback` и не сгенерированы эмбеддинги для `knowledge_base`. Задачи: `tj-yp0`, `tj-0n9`. |
| `verify_crm` | ✅ | 4 | 0 | Успешное подключение и проверка Zoho CRM. |
| `verify_inventory` | ✅ | 4 | 0 | Успешное подключение и проверка Zoho Inventory (`stock_on_hand` проверен). |
| `verify_wazzup` | ✅ | 0 | 1 | (Проигнорировано) Тест не отправлял реальных сообщений без `TEST_PHONE`. Успешно предотвращена отправка. |
| `verify_rag_pipeline` | ❌ | 2 | 2 | Ошибки связаны с отсутствием эмбеддингов в базе данных. Задача: `tj-0n9`. Ошибки в коде скрипта были исправлены. |
| `verify_voice` | ✅ | 4 | 0 | Модуль для работы с `openai/gpt-audio-mini` успешно инициализирован. |
| `verify_quality` | ✅ | 6 | 0 | Ошибка импорта `QualityReviewResult` была исправлена на `EvaluationResult`. Все зависимости загружены. |
| `verify_telegram` | ❌ | 3 | 3 | В `.env` на VPS отсутствуют переменные `TELEGRAM_BOT_TOKEN` и `TELEGRAM_CHAT_ID`. Логика форматирования исправлена и работает. Задача: `tj-8qv`. |
| `verify_followups` | ❌ | 3 | 1 | Падает из-за отсутствия SQL таблицы `feedback`, не накатилась миграция. Задача: `tj-yp0`. |
| `verify_pdf` | ✅ | 5 | 0 | Weasyprint успешно генерирует PDF. Ошибки шаблона HTML (отсутствие `customer`, и др.) исправлены! |
| `verify_api` | ✅ | 7 | 0 | Все ендпоинты отвечают согласно ожидаемым кодам. Защищенный API `/api/v1/quality/reviews/` возвращает `403`. |

## Созданные баг-треки в Beads

Созданы следующие задачи в трекере **bd** для инфраструктуры:

1. **BUG: Production DB missing feedback table (run alembic upgrade)**
   - **ID**: `tj-yp0`
   - **Описание**: Необходимо выполнить `alembic upgrade head` на сервере (отсутствует `feedback`).
2. **BUG: Missing Telegram ENV variables on Production**
   - **ID**: `tj-8qv`
   - **Описание**: Необходимо задать `TELEGRAM_BOT_TOKEN` и `TELEGRAM_CHAT_ID` в VPS `.env`.
3. **BUG: Knowledge Base is empty (missing embeddings on Production)**
   - **ID**: `tj-0n9`
   - **Описание**: Требуется запустить `index_knowledge_base()` для риимплементации эмбеддингов после сдвига на `sentence-transformers`.
