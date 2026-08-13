# Спецификация: семантическое доказательство каталога для измеряемых раундов

Дата: 2026-08-13
Bead: `tj-rcg5`
Статус: принято владельцем, готово к реализации
Решение по документации: `use docs-resolve` для pgvector 0.4.2 и закрепления
ревизии модели; локальная база кода остаётся источником истины для поведения
Treejar.

## Решение

Измеряемый раунд больше не подбирает товары по совпавшим словам. Поиск и
генерация становятся двумя независимыми, проверяемыми этапами:

1. локальный производитель загружает защищённый снимок каталога во временный
   PostgreSQL с pgvector, строит эмбеддинги закреплённой ревизией BGE-M3 и
   вызывает `src.rag.pipeline.search_products`;
2. раунд генерации принимает только версионированный артефакт этого поиска и
   прекращает работу до платных вызовов, если его идентичность не совпадает с
   текущими сценариями, снимком, моделью или кодом поиска.

Это сохраняет воспроизводимость генерации и одновременно делает строки в её
промпте результатом того же SQL/pgvector-пути, которым пользуется приложение.
Архитектура не учит Noor повторять выданные строки: наличие строк и их
релевантность остаются разными фактами.

## Дефект и граница утверждений

`scripts/corpus_bridge/real_opening_acceptance.py::catalog_matches` считает
совпадения слов в названии, SKU, slug, категории и описании. Для диалога 436
это стабильно подставляло три неподходящих товара. Отказ Noor перечислять их
был верным. Диалог 442, напротив, случайно получал подходящие товары, поэтому
подмена долго выглядела правдоподобно.

Раунды, подготовленные старым подбором, остаются историческими и не
пересчитываются. Они годятся для правил, не зависящих от каталога, но не
доказывают:

- качество выбора товара;
- правила 8 и 9 в части использования каталога;
- заземлённость ответа в выдаче, которую дал бы production-путь.

Новая схема доказывает паритет функции поиска на зафиксированном входе. Она не
доказывает, какой текст запроса сформировал бы LLM-инструмент в живом диалоге:
в этом стенде источником запроса остаётся замороженное первое сообщение, и это
обязательно записывается как `query_source=frozen_opening`.

## Нормативный поток

```text
защищённый снимок каталога + закреплённая BGE-M3 + frozen scenarios
                              |
                              v
              временный PostgreSQL/pgvector без ANN-индекса
                              |
                              v
                src.rag.pipeline.search_products
                              |
                              v
        защищённый retrieval-evidence.json + manifest/digests
                              |
                    строгая проверка идентичности
                              |
                              v
             measured generation preflight -> paid round
```

`catalog_matches` удаляется из измеряемого пути. Лексический подбор допустим
только как явно названная диагностика с маркировкой `unmeasured`; молчаливого
fallback при ошибке, отсутствии модели или базы быть не должно.

## Входной снимок каталога

Производитель принимает путь через обязательный `--catalog-snapshot`. Он сам
ничего не скачивает и не обращается к production. Снимок лежит вне рабочего
дерева с правами `0600` и содержит канонически отсортированные поля, нужные
модели `Product` и производственному тексту эмбеддинга:

- стабильный id, SKU, `name_en`, `name_ar`;
- `description_en`, `description_ar`, category и subcategory;
- price, currency, stock, `is_active`;
- служебную версию схемы и источник снимка.

Существующие `catalog-cache.json` измеренных раундов не подходят как
семантический снимок: в проверенном кэше 332 строки, но нет описаний и
эмбеддингов. Они остаются историческими входами и не переименовываются так,
будто получили новую силу доказательства.

Digest снимка — SHA-256 канонического JSON после сортировки по стабильному id и
SKU. Производитель не стартует, если обязательных полей нет или SKU/id
дублируются.

## Закрепление модели и точного поиска

- Model id: `BAAI/bge-m3`.
- Revision: полный commit hash Hugging Face, обязательный аргумент и поле
  manifest. На машине планирования найден локальный snapshot
  `5617a9f61b028005a4858fdac845db406aefb181`; это кандидат для воспроизводимого
  запуска, но не доказанная идентичность текущего production-кэша.
- Размерность: 1024; нормализация включена, как в `EmbeddingEngine`.
- pgvector: версия из lockfile, сейчас 0.4.2.
- Distance: cosine (`<=>` через `cosine_distance`).
- Search mode: exact. Во временной таблице запрещены HNSW и IVFFlat индексы.

pgvector выполняет точный nearest-neighbor поиск по умолчанию; HNSW и IVFFlat
дают приближённый результат. Поэтому производитель проверяет схему базы, а
manifest пишет `search_mode=exact` и `ann_indexes=[]`.

## Артефакт поиска

Артефакт защищён, неизменяем после публикации и не попадает в Git. Минимальная
схема:

```json
{
  "schema_version": 1,
  "catalog": {"sha256": "...", "rows": 0},
  "embedding": {
    "model": "BAAI/bge-m3",
    "revision": "full-commit-hash",
    "dimensions": 1024,
    "normalized": true
  },
  "retrieval": {
    "entrypoint": "src.rag.pipeline.search_products",
    "code_sha": "...",
    "pgvector_python": "0.4.2",
    "pgvector_extension": "0.8.5",
    "distance": "cosine",
    "search_mode": "exact",
    "limit": 3,
    "query_source": "frozen_opening"
  },
  "query_set": {"sha256": "...", "count": 0},
  "results": [
    {
      "dialog_id": 0,
      "query_sha256": "...",
      "rows_present": true,
      "catalog_relevant": false,
      "relevant_skus": [],
      "products": []
    }
  ]
}
```

`products` хранит полную упорядоченную top-3 проекцию production retrieval:
стабильный id, SKU, название, категория, цена и остаток. `relevant_skus`
хранит пересечение этой выдачи с защищёнными qrels, не меняя порядок. Consumer
передаёт генератору только эту подтверждённую часть; полный top-3 остаётся в
артефакте для проверки качества и не становится подсказкой процитировать
ближайший неподходящий товар. Сырые сообщения в артефакте не дублируются;
соответствие проверяется по `dialog_id` и `query_sha256`. В tracked-файлы не
попадают ни строки корпуса, ни снимок, ни ответы.

`rows_present` означает только факт выдачи. `catalog_relevant` вычисляется по
защищённым qrels — ручным оценкам релевантности — и равен наличию хотя бы одного
`relevant_skus`, но никогда не `bool(products)` по умолчанию. При отсутствии
релевантных строк Noor вправе уточнить потребность или отказаться от
перечисления; плохая выдача в generation prompt не попадает.

## Отдельная оценка retrieval

Качество поиска оценивается до генерации и не смешивается с баллами ответа.
Защищённый golden set содержит:

- общий товарный запрос и известную форму дефекта 436;
- workstation-форму 442;
- опечатку и разговорную формулировку;
- английский и арабский варианты;
- запрос без релевантного товара.

Точный SKU сюда намеренно не входит. Репозиторий направляет такой запрос в
`get_stock` и `_find_catalog_product_by_sku`; semantic embedding строится из
name/category/description и SKU не содержит. Реальный discovery-run 2026-08-13
подтвердил: переданный как query SKU не попал в top-3 semantic search. Это
граница маршрута, а не основание менять production embedding в `tj-rcg5`.

Для каждого запроса хранятся релевантные и явно запрещённые product ids/SKU.
Отчёт печатает Precision@3, Recall@3, nDCG@3 и нарушения forbidden-набора.
Обязательные индивидуальные условия важнее среднего:

- ни один явно запрещённый товар не попадает в top-3;
- для 436 и 442 в top-3 есть хотя бы один вручную подтверждённый релевантный
  товар либо запрос честно отмечен как `no_relevant_result`;
- запрос без релевантного товара не превращает ближайшие строки в релевантные.

Если production-путь не выполняет эти условия, реализация `tj-rcg5` не меняет
ответы и не маскирует результат. Она закрывает дефект паритета стенда, а
дефект качества production retrieval заводится отдельно с защищённым отчётом.

## Проверка идентичности и отказ по умолчанию

Перед любым платным вызовом consumer пересчитывает и сравнивает:

- schema version;
- digest и число строк каталога;
- model id, revision, dimension и normalization;
- версии Python-пакета и PostgreSQL extension pgvector, distance, exact mode и
  top-k;
- SHA кода, владеющего retrieval-контрактом;
- digest и число frozen scenarios;
- по одному результату и совпадающему query digest на каждый dialog id.

Отсутствие, дубль, лишний результат, stale digest, floating revision,
приближённый индекс или неизвестное поле останавливают preflight. Лексический
fallback запрещён. Проверка идёт раньше provider preflight и оценки стоимости,
чтобы неверный ввод не мог породить оплачиваемый раунд.

## Файлы реализации

- новый `scripts/corpus_bridge/semantic_catalog_evidence.py` — схемы,
  канонические digests, загрузка временной БД, pinned embeddings, вызов
  `src.rag.pipeline.search_products`, retrieval-метрики и CLI;
- `scripts/corpus_bridge/real_opening_acceptance.py` — consumer артефакта,
  строгий fail-closed preflight, удаление keyword matcher из measured path;
- новый `tests/test_corpus_bridge_semantic_catalog_evidence.py` — unit и
  контейнерный integration slice;
- `tests/test_corpus_bridge_real_opening_acceptance.py` — stale/missing/mismatch,
  доказательство, что keyword fallback не вызывается, а неподтверждённый top-3
  не передаётся генератору;
- `docs/client/noor-opening-acceptance-2026-08-13.md` — явное ограничение всех
  исторических keyword-backed раундов;
- `.codex/handoff.md` и Bead — текущая идентичность и защищённые доказательства.

`src/rag/pipeline.py`, production model config и production БД не меняются.

## Приёмка

1. Измеряемый preflight невозможно запустить без валидного семантического
   артефакта; keyword matcher не достижим из measured path.
2. Производитель в integration-тесте использует реальный PostgreSQL/pgvector и
   вызывает `src.rag.pipeline.search_products`, а не копию SQL.
3. Exact mode, pinned revision и все digests присутствуют и проверяются
   fail-closed до любого provider call.
4. Наличие строк и релевантность разделены; известная плохая выдача не создаёт
   требования цитировать её.
5. Retrieval golden set печатает per-query и aggregate Precision@3, Recall@3,
   nDCG@3, forbidden violations; любой обязательный per-query провал блокирует
   публикацию артефакта.
6. Клиентский пакет прямо ограничивает старые раунды. Исторические оценки и
   baseline не меняются и не пересчитываются.
7. Защищённый реальный запуск записывает manifest, digest отчёта, команду и
   права `0600` в `tj-rcg5`; ни один закрытый текст не попадает в Git.
8. Полные repo gates, process verification и root slice acceptance зелёные.

## Не входит в работу

- изменение production retrieval, ranker, порога релевантности или tool-query;
- изменение model config или попытка объявить локальный snapshot фактической
  ревизией production;
- переобучение, новый промпт или правило «цитировать каждую строку»;
- re-baseline старых раундов;
- production/deploy-команда, paid call, real-customer message или CRM write.

## Премортем и восстановление

| Риск | Ранний сигнал | Предохранитель | Восстановление |
|---|---|---|---|
| Плавающая модель меняет порядок | revision отсутствует или короткий | полный hash, `local_files_only`, fail-closed | артефакт не публикуется |
| Старый кэш выдан за снимок | нет descriptions/manifest | строгая схема и отдельное имя | сохранить как historical only |
| ANN даёт нестабильный top-k | HNSW/IVFFlat в `pg_indexes` | временная таблица без ANN | пересоздать временную БД |
| Stale artifact попал в новый round | digest mismatch | consumer пересчитывает все digests | заново произвести artifact |
| Любые строки названы релевантными | `catalog_relevant=bool(rows)` | qrels и отдельные поля | round блокируется тестом |
| Один пример переобучил оценку | среднее зелёное, per-query красный | разнообразный set и hard constraints | новый production bug, без маскировки |
| Exact-SKU проверяется не тем route | semantic top-3 не содержит SKU | исключить из semantic qrels; оставить direct-SKU engine tests | исправлять отдельный route, не qrels |
| Закрытые данные попали в Git | raw query/product snapshot в diff | protected root, tracked allowlist test | остановить работу и удалить до commit |
| Локальной модели/БД нет | preflight dependency error | отдельный явный integration gate | не закрывать Bead и не подменять поиск |

Откат — обычный revert одного будущего commit `tj-rcg5`. Миграций и production
изменений нет; старые protected artifacts остаются запечатанными. После отката
измеряемый раунд должен оставаться заблокированным, а не возвращаться к
keyword fallback.

Вердикт: **GO WITH CONDITIONS**. Для закрытия нужны полный защищённый снимок,
доступная локально закреплённая ревизия модели и реальный pgvector integration
run. Без любого из трёх честный результат — остановка, не доставка.

## Внешние основания

- [pgvector: exact и approximate nearest-neighbor search](https://github.com/pgvector/pgvector)
- [Hugging Face Hub: загрузка по `revision`](https://huggingface.co/docs/huggingface_hub/en/guides/download)
- [Sentence Transformers: InformationRetrievalEvaluator](https://www.sbert.net/docs/package_reference/sentence_transformer/evaluation.html)
- [BEIR: corpus, queries, qrels и retrieval-метрики](https://github.com/beir-cellar/beir)
- [LangSmith: retrieval relevance отдельно от groundedness и answer quality](https://docs.langchain.com/langsmith/evaluate-rag-tutorial)
- [MLflow datasets: source, digest и metadata](https://mlflow.org/docs/latest/api_reference/python_api/mlflow.data.html)
