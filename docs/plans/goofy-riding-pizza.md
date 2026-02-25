# Проверка работы агента: Неделя 2 — Zoho Inventory Sync + RAG Pipeline

## Контекст

Агент реализовал задачи Недели 2 по промпту из `.tmp/current/week2-agent-prompt.md`. Нужно проверить качество, найти баги и исправить их.

## Quality Gate

| Проверка | Результат |
|---|---|
| `ruff check src/ tests/` | PASSED |
| `mypy src/` | PASSED (58 files) |
| `pytest tests/ -q` | PASSED (10/10) |

## Code Review — Результаты

### Что реализовано хорошо

1. **`src/integrations/inventory/zoho_inventory.py`** — Zoho client: OAuth2 с Redis lock, retry с backoff (3 попытки), обработка 401 (token expired) и 429 (rate limit), EU URLs корректны.

2. **`src/integrations/inventory/sync.py`** — Sync job: PostgreSQL upsert (INSERT ON CONFLICT), pagination через `has_more_page`, маппинг полей Zoho → Product корректный, `synced_at = func.now()`.

3. **`src/rag/embeddings.py`** — Singleton EmbeddingEngine, lazy loading модели, batch по 32, формат текста `"Name | Category | Description"`.

4. **`src/rag/pipeline.py`** — PgVectorStore реализует VectorStore protocol, гибридный поиск (SQL фильтры + pgvector cosine distance), `search_knowledge()` для knowledge base.

5. **`src/worker.py`** — Cron jobs зарегистрированы (каждые 6ч), sync в `functions` list.

6. **`src/api/v1/products.py`** — Пагинация с count, EmbeddingEngine как FastAPI dependency, sync через ARQ queue.

7. **Тесты** — 10 тестов, всё замокано (без реальных DB/Redis/model), покрыты: singleton, embed, embed_batch, product embeddings, KB embeddings, RAG search, Zoho client, sync job.

### Найденные проблемы

#### BUG-1: CRITICAL — `indexer.py` upsert без unique constraint

**Файл:** `src/rag/indexer.py:74`
```python
stmt = stmt.on_conflict_do_update(
    index_elements=[KnowledgeBase.source, KnowledgeBase.title],
    ...
)
```

Модель `KnowledgeBase` НЕ имеет unique constraint на `(source, title)`. PostgreSQL выбросит ошибку `there is no unique or exclusion constraint matching the ON CONFLICT specification`. Это упадёт при первом вызове `index_documents()`.

**Исправление:**
1. Добавить unique constraint в модель `src/models/knowledge_base.py`:
   ```python
   from sqlalchemy import UniqueConstraint

   class KnowledgeBase(UUIDMixin, Base):
       __tablename__ = "knowledge_base"
       __table_args__ = (
           UniqueConstraint("source", "title", name="uq_knowledge_base_source_title"),
       )
       # ... остальные поля без изменений
   ```
2. Создать Alembic миграцию: `alembic revision --autogenerate -m "add unique constraint on knowledge_base source+title"`

#### BUG-2: MINOR — inline imports в теле функций

**Файл:** `src/api/v1/products.py:52`
```python
import math  # должен быть вверху файла
```

**Файл:** `src/integrations/inventory/sync.py:133`
```python
from sqlalchemy.sql import func  # должен быть вверху файла
```

**Исправление:** Переместить оба import в начало файлов.

---

## План исправлений

### Шаг 1: Fix BUG-1 — unique constraint на knowledge_base
- **Файл:** `src/models/knowledge_base.py` — добавить `__table_args__` с UniqueConstraint
- **Миграция:** `alembic revision --autogenerate -m "add unique constraint on knowledge_base source+title"`

### Шаг 2: Fix BUG-2 — inline imports
- **Файл:** `src/api/v1/products.py` — переместить `import math` вверх
- **Файл:** `src/integrations/inventory/sync.py` — переместить `from sqlalchemy.sql import func` вверх

### Шаг 3: Quality Gate
```bash
ruff check src/ tests/
mypy src/
pytest tests/ -q
```

### Шаг 4: Commit + Push
Закоммитить все изменения агента + фиксы.

## Файлы для изменения

| Файл | Действие |
|---|---|
| `src/models/knowledge_base.py` | Добавить UniqueConstraint |
| `src/api/v1/products.py` | Переместить `import math` вверх |
| `src/integrations/inventory/sync.py` | Переместить `from sqlalchemy.sql import func` вверх |
| Alembic миграция | Автогенерация для нового constraint |
