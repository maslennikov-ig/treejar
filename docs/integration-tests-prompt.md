# Промпт: Интеграционные тесты бота без моков

Скопируй это в новое контекстное окно Antigravity:

---

## Задача

Мне нужно переписать тесты бота TreeJar так, чтобы они **ничего не мокали** — работали с реальными API (Zoho CRM, Zoho Inventory, Wazzup), реальной БД и реальным LLM.

### Контекст проблемы

Наши текущие unit-тесты мокают все внешние зависимости. Из-за этого мы пропустили критический баг на проде: Zoho CRM возвращает поле `Segment` как **список** (`["Wholesale"]`), а наши моки передавали **строку** (`"Wholesale"`). В результате `discounts.py` падал с `TypeError: unhashable type: 'list'`, бот отвечал fallback-сообщением об ошибке.

### Что нужно сделать

1. **Изучить проект**: прочитай `PRODUCT.md`, `ARCHITECTURE.md`, структуру тестов в `tests/`.
2. **Изучить существующие тесты**: `tests/test_e2e_tools.py`, `tests/test_llm_engine.py`, `tests/test_dialog_scenarios.py`, `tests/test_dialog_real_llm.py`, `tests/test_core_discounts.py`.
3. **Создать integration test suite** (например, `tests/test_integration_live.py`), который:
   - Подключается к **реальной dev-БД** (через `DATABASE_URL` из `.env.dev`)
   - Вызывает **реальный Zoho CRM API** для получения контакта и проверяет типы полей (Segment = list)
   - Вызывает **реальный Zoho Inventory API** для проверки наличия товаров (`stock_on_hand`)
   - Запускает LLM-движок с реальным промптом и проверяет, что `search_products` работает end-to-end со скидками
   - Проверяет, что `create_quotation` корректно генерирует PDF
   - Помечается `@pytest.mark.integration` чтобы не запускался в CI по умолчанию

4. **Обновить `test_core_discounts.py`** — добавить edge-cases:
   - `segment = ["Wholesale"]` (список)
   - `segment = []` (пустой список)
   - `segment = None`
   - `segment = ["Unknown", "Retail chain B2B"]` (multi-select с несколькими значениями)

5. **Конфигурация**:
   - Тесты должны читать credentials из `.env` или `.env.dev` (НЕ хардкодить)
   - Пометить `@pytest.mark.skipif` если env-переменные отсутствуют (graceful skip в CI)
   - Создать `conftest.py` фикстуру для DB session и API клиентов

### Ключевые файлы

| Файл | Что делает |
|------|-----------|
| `src/core/discounts.py` | Расчёт скидок по сегменту клиента |
| `src/llm/engine.py` | LLM-агент с инструментами (search_products, get_stock, create_quotation, etc.) |
| `src/integrations/zoho/crm.py` | Клиент Zoho CRM |
| `src/integrations/zoho/inventory.py` | Клиент Zoho Inventory |
| `src/services/chat.py` | Обработка входящих сообщений |
| `tests/test_e2e_tools.py` | Текущие тесты с моками (referencia) |
| `tests/test_core_discounts.py` | Тесты скидок |
| `scripts/bot_test_suite.py` | Скрипт для live-тестирования бота через Wazzup |

### Важно

- **Строгий TDD**: пиши тест → запускай → убедись что падает → фикси → убедись что проходит
- **Не ломай существующие тесты** — интеграционные тесты ДОПОЛНЯЮТ unit-тесты
- **Используй MCP Context7** для актуальной документации по PydanticAI, SQLAlchemy, pytest
- **Каждый тест должен быть idempotent** — не оставлять мусора в БД (используй transactions с rollback)
- Marker `@pytest.mark.integration` + `pytest.ini` конфигурация для отдельного запуска
