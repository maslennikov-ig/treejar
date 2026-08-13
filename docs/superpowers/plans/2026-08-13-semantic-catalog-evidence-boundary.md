# План: семантическое доказательство каталога (`tj-rcg5`)

> Реализовать одним связным вертикальным срезом в `tj-rcg5`. Производитель без
> consumer или consumer без строгой проверки создают опасное промежуточное
> состояние, поэтому новые Beads не заводятся и delivery остаётся одним commit.

**Спецификация:**
`docs/superpowers/specs/2026-08-13-semantic-catalog-evidence-boundary-spec.md`

**Уровень:** integration
**Ветка:** `codex/tj-rcg5`
**Документация:** `docs-resolve` выполнен для `pgvector@0.4.2`; ответ первого
источника сохранён через `docs-persist`, первичные ссылки перечислены в spec.

## Цель

Measured round получает top-3 только из production retrieval function на
закреплённом offline-входе, проверяет релевантность отдельно и не может
молча вернуться к keyword matcher.

## Не-цели

- не улучшать production search и не менять BGE-M3 config;
- не воспроизводить LLM-формулировку tool query: query source остаётся
  `frozen_opening` и явно ограничивает вывод;
- не запускать платную генерацию, production, deploy, CRM или сообщения;
- не менять и не re-baseline исторические раунды;
- не заставлять ответ перечислять неподходящие строки.

## Предусловия и стопы

До начала code lane проверить:

1. `--catalog-snapshot` указывает на protected `0600` export со всеми полями из
   spec. Проверенные старые `catalog-cache.json` непригодны: в них нет
   descriptions и embeddings.
2. Полная revision BGE-M3 доступна локально. Найденный кандидат на 2026-08-13:
   `5617a9f61b028005a4858fdac845db406aefb181`. Не называть его production
   revision без отдельного доказательства.
3. Docker/Podman может поднять `pgvector/pgvector:pg16` без production
   credentials; image уже используется в repo compose.

Если snapshot отсутствует, схема неполна, revision требует download или
контейнер недоступен, остановиться и записать точный blocker. Нельзя заменять
integration gate mock-тестом, keyword fallback или live search.

## Ledger приёмки

| Требование spec | Реализация | Проверка |
|---|---|---|
| production search path | producer импортирует `search_products` | monkeypatch spy + real pgvector slice |
| exact pinned retrieval | manifest + DB schema guard | revision/ANN negative tests |
| fail-closed consumer | validator перед provider preflight | missing/stale/duplicate tests |
| rows ≠ relevance | qrels field и отдельная applicability | no-match/forbidden tests |
| retrieval quality | protected golden set evaluator | P@3/R@3/nDCG@3 + hard constraints |
| historical truth | client pack correction | focused text assertion/review |
| privacy | protected paths + tracked allowlist | git diff and mode checks |
| repo health | canonical gates + process check | recorded command output |

## Task 1: один вертикальный срез producer → consumer → evidence

**Bead:** `tj-rcg5`
**Ownership:** один implementing agent; не делегировать части с общей схемой
артефакта.
**Write area:** `scripts/corpus_bridge/`, focused `tests/`, client docs,
`.codex/handoff.md`, Bead notes.

### 1.1 Зафиксировать красные тесты consumer

**Файл:** `tests/test_corpus_bridge_real_opening_acceptance.py`

Добавить Given/When/Then:

1. Given frozen scenarios и отсутствующий artifact, when `preflight` стартует,
   then он падает до `_pinned_model_catalog` и любых provider calls.
2. Given artifact с неверным catalog/query/code/model digest, then каждый тип
   mismatch имеет отдельную понятную ошибку.
3. Given duplicate/missing/extra dialog result, then preflight падает.
4. Given три rows и qrels без релевантных, then `rows_present=True`,
   `catalog_relevant=False`, полный top-3 сохраняется в retrieval artifact, а
   generation messages не получают эти неподтверждённые rows.
5. Given старый keyword matcher, then measured `_prepare_cases` не вызывает его
   и не имеет fallback-пути.

Сначала запустить только новые тесты и записать ожидаемый RED.

### 1.2 Реализовать схемы и чистый validator

**Новый файл:** `scripts/corpus_bridge/semantic_catalog_evidence.py`

1. Dataclasses/Pydantic-модели manifest, query result и qrels.
2. Канонический JSON и SHA-256 для snapshot, query set и retrieval-contract
   files.
3. Проверка `0600`, пути вне repo, полных обязательных полей, уникальных ids/SKU
   и полного model revision.
4. `validate_evidence(...)` без I/O к сети/БД, возвращает immutable mapping по
   dialog id.
5. Метрики P@3, R@3, nDCG@3 и forbidden violations как чистые функции.

Довести consumer unit tests до GREEN, не реализуя ещё контейнер.

### 1.3 Написать producer через production function

**Файлы:**

- `scripts/corpus_bridge/semantic_catalog_evidence.py`;
- новый `tests/test_corpus_bridge_semantic_catalog_evidence.py`.

TDD lane:

1. RED: incomplete snapshot, floating revision, wrong dimension и ANN index
   отклоняются.
2. RED: synthetic catalog + семантический запрос даёт релевантный товар первым;
   forbidden row в top-3 блокирует публикацию. Exact SKU не включать: этот
   запрос принадлежит production route `get_stock`, а не semantic retrieval.
3. Поднять временный `pgvector/pgvector:pg16`, применить только нужную schema,
   загрузить snapshot и построить product embeddings закреплённой моделью в
   `local_files_only` режиме.
4. Для каждого frozen opening создать `ProductSearchQuery(query=opening,
   limit=3)` и вызвать именно `src.rag.pipeline.search_products`.
5. Перед запросами проверить `pg_indexes`: HNSW/IVFFlat отсутствуют; прочитать
   версию extension.
6. Записать artifact сначала во временный файл, валидировать, затем атомарно
   опубликовать с mode `0600`. Существующий target не перезаписывать.
7. Напечатать per-query и aggregate retrieval report; hard constraint делает
   exit code ненулевым и не публикует artifact.

Integration test использует маленький синтетический каталог и ту же pinned
модель. Он не доказывает качество реального каталога, зато доказывает wiring и
exact pgvector behavior.

### 1.4 Перевести measured preflight на artifact

**Файл:** `scripts/corpus_bridge/real_opening_acceptance.py`

1. Добавить обязательный `--retrieval-evidence` для measured preflight.
2. Валидировать artifact до `_pinned_model_catalog`, cost estimate и любых paid
   clients.
3. `_prepare_cases` принимает validated mapping, сохраняет порядок
   `relevant_skus` из production top-3 и не повторяет поиск; неподтверждённые
   строки остаются только retrieval-доказательством.
4. Заменить `catalog_relevant=bool(evidence)` на значение из qrels; добавить
   `catalog_rows_present` для наблюдаемости.
5. Удалить `catalog_matches` из measured module. Если диагностика всё ещё
   нужна существующим тестам, вынести её под именем
   `lexical_catalog_approximation` с `unmeasured` output marker; measured CLI её
   не импортирует.
6. Все catalog-derived digests в `preflight.json` брать из semantic artifact.

Повторить focused consumer suite до GREEN.

### 1.5 Проверить защищённый реальный slice

Без paid calls:

```bash
uv run python scripts/corpus_bridge/semantic_catalog_evidence.py produce \
  --database-url <loopback-isolated-pgvector-url> \
  --catalog-snapshot <protected-semantic-catalog.jsonl> \
  --scenarios <protected-frozen-scenarios.json> \
  --qrels <protected-retrieval-qrels.json> \
  --model BAAI/bge-m3 \
  --revision <full-hash> \
  --output <protected-new-directory>/retrieval-evidence.json
```

Проверить:

- mode директории `0700`, файлов `0600`;
- schema/digests/revision/exact mode/pgvector version;
- 436, 442, typo, EN, AR и no-match в per-query report;
- отсутствие forbidden violations;
- никакого provider/production вызова по сетевому журналу и коду пути.

Если реальный retrieval нарушает hard constraint, остановиться. Создать новый
Bead на production retrieval quality с digest защищённого отчёта; `tj-rcg5`
может быть закрыт только после того, как measured harness честно потребляет эту
выдачу и клиентский документ не обещает качество, которого нет.

### 1.6 Исправить историческую документацию

**Файлы:**

- `docs/client/noor-opening-acceptance-2026-08-13.md`;
- `.codex/handoff.md`.

В client pack рядом с описанием каталогозависимых выводов написать:

- старые раунды использовали keyword stand-in;
- правила 8/9 и grounding по тем раундам не являются измерением production
  product selection;
- оценки не пересчитаны;
- новый semantic artifact доказывает только записанную revision/snapshot/query
  source.

Handoff оставить current-state only и ≤200 строк. После изменения выполнить:

```bash
uv run python scripts/orchestration/repin_traceability_sources.py \
  --source repo-contract
```

Если фактический CLI требует отдельные вызовы, сначала свериться с `--help`; не
угадывать синтаксис.

### 1.7 Верификация и один commit

Focused acceptance:

```bash
uv run pytest tests/test_corpus_bridge_semantic_catalog_evidence.py \
  tests/test_corpus_bridge_real_opening_acceptance.py -v --tb=short
```

Перед commit выполнить repo gates и process verification:

```bash
uv run ruff check src/ tests/ scripts/
uv run ruff format --check src/ tests/ scripts/
uv run mypy src/
uv run pytest tests/ -v --tb=short
scripts/orchestration/run_process_verification.sh
```

Затем один root acceptance:

```bash
uv run python scripts/orchestration/run_stage_closeout.py \
  --stage tj-rcg5-semantic-catalog-evidence \
  --level slice_acceptance \
  --command 'uv run pytest tests/test_corpus_bridge_semantic_catalog_evidence.py tests/test_corpus_bridge_real_opening_acceptance.py -v --tb=short'
```

До commit:

1. `git diff --check`;
2. `git status --short` и подтверждение, что чужая правка `.gitignore` не
   staged;
3. в Bead notes: команды, counts, artifact/report digests, model revision,
   catalog/query digests, exact mode, normal/failure/edge cases и оставшееся
   ограничение `query_source=frozen_opening`;
4. `bd close tj-rcg5 --reason=...`, export Beads по repo convention;
5. один commit `fix(acceptance): use semantic catalog evidence`.

## Матрица случаев

| Класс | Случай | Ожидание |
|---|---|---|
| Normal | общий desk/workstation запрос | production top-3 сохранён; relevance из qrels |
| Boundary | точный SKU | не входит в semantic qrels; владелец — direct-SKU/get_stock route |
| Failure | нет artifact | preflight fail до provider |
| Failure | stale snapshot/model/code/query digest | точная ошибка, no fallback |
| Failure | ANN index | producer отказывается публиковать |
| Failure | forbidden item | retrieval report красный; replies не меняются |
| Edge | rows есть, релевантных нет | top-3 виден в artifact, но не модели; applicability false |
| Edge | опечатка/разговорный запрос | метрики и порядок записаны |
| Edge | Arabic | та же модель/revision, отдельный qrel |
| Edge | duplicate dialog/SKU | schema validation fail |

## Delivery boundary

После зелёных gates сделать fresh fetch и убедиться, что `origin/main` не
впереди и не разошёлся. Обычный push в `origin/main` уже разрешён исходным
handoff, но deploy-команду не запускать: CI при `src/`-изменении действует
автоматически. В этой задаче `src/` меняться не должен, поэтому автоматический
deploy не ожидается. PR не создавать.
