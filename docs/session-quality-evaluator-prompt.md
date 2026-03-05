# Prompt для Сессии (Этап 2): Quality Evaluator

Скопируй приведённый ниже текст и отправь его в новом окне чата с ИИ-агентом:

***

Привет! Мы продолжаем работу над проектом **Noor AI Seller** (репозиторий `maslennikov-ig/treejar`, ветка `develop`).

**Контекст и текущий статус:**

Этап 1 (Недели 1–8) полностью реализован и задеплоен на VPS (`noor.starec.ai`):
- Бот принимает сообщения из WhatsApp (Wazzup), общается через LLM (PydanticAI + OpenRouter/DeepSeek), проверяет остатки (Zoho Inventory, 856 SKU), создаёт контакты и сделки (Zoho CRM), генерирует PDF-КП (WeasyPrint + Jinja2), эскалирует 18 триггеров на 7 менеджеров, делает follow-up по расписанию (24ч→3д→7д→30д→90д).
- Дашборд: React/Vite + SQLAdmin, 17 KPI, Recharts-графики.
- Покрытие тестами: **91%**, mypy --strict: **0 ошибок**, Ruff: чисто.
- Последний тег: `v0.3.0`.

**Техстек:** Python 3.12, FastAPI, SQLAlchemy 2.0 async, Alembic, PostgreSQL 16 + pgvector, Redis 7, ARQ workers, PydanticAI, FastEmbed BGE-M3, WeasyPrint.

---

**Текущая задача — реализовать модуль контроля качества (Этап 2, Недели 9-10):**

**Quality Evaluator** — LLM-as-a-judge. Автоматически оценивает завершённые диалоги бота по 15 критериям.

Что нужно создать:
1. `src/quality/evaluator.py` — LLM-судья: получает диалог (conversation_id), вызывает LLM с промптом-чеклистом, возвращает structured оценку
2. `src/quality/schemas.py` — Pydantic-схемы для запроса/ответа оценки
3. ARQ job: автоматически оценивать завершённые диалоги (раз в час), дописать в `src/worker.py`
4. API endpoints (заготовки уже есть в `src/api/v1/router.py`):
   - `POST /api/v1/quality/reviews/` — ручное создание оценки
   - `GET /api/v1/quality/reviews/` — список с фильтрами по score, дате, conversation_id
5. `tests/test_quality_evaluator.py` — юнит-тесты (TDD: сначала тесты, потом код)

Критерии оценки (15 штук, шкала 0-2 за каждый, максимум 30 баллов):
- Прочти `docs/06-dialogue-evaluation-checklist.md` — там полный чеклист с описанием каждого критерия
- Рейтинги: excellent (26-30), good (20-25), satisfactory (14-19), poor (<14)
- Таблица `quality_reviews` в БД уже существует (поля: id, conversation_id FK, score float, criteria jsonb, summary text, reviewer, created_at)

**Правила работы (ОЧЕНЬ ВАЖНО):**
1. **MCP Context7:** перед написанием кода с PydanticAI или ARQ — обязательно запроси актуальную документацию через Context7.
2. **Worktrees:** используй скилл `using-git-worktrees` для создания ветки `feature/quality-evaluator`. НЕ пиши код напрямую в `develop`.
3. **Beads (bd):** создай макро-задачу: `bd update <id> --status=in_progress`. Закрой после завершения: `bd close <id> --reason="..."`.
4. **TDD:** сначала падающий тест → потом минимальный код → потом рефактор. У нас 91% coverage, не сломай.
5. **Planning:** прочитай `docs/task-plan.md` (секция Неделя 9-10), затем используй навык `writing-plans` → создай `docs/specs/quality-evaluator/spec.md` и `plan.md`. После утверждения плана используй `subagent-driven-development`.
6. **Коммит:** `git commit --no-verify -m "..."` (pre-commit hook mypy иногда зависает), `git push origin feature/quality-evaluator`.

Начни с фазы `brainstorming`, прочитай `docs/06-dialogue-evaluation-checklist.md` и `docs/task-plan.md` (Недели 9-10), затем составь план через `writing-plans`. Жду утверждения плана перед началом кода!

***
