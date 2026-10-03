# Оптимизация остатков Zoho — проверенный локальный результат

Дата:2026-10-03. Задача: **tj-uvld**, остаётся `in_progress`.
Основная реализация: **0b5c723eeb96c240d2c1654f6b570d951aa782eb**.
Release-код и тесты: **5f9e992** (включая b30096a и обновлённые legacy fixtures).
Ветка: `codex/tj-uvld-stock-sync`.
Worktree: `/home/me/code/treejar/.worktrees/tj-uvld-stock-sync`.
База main: `36c86137a51d2e6485db92c28ec057fe26f03339`.
После основной реализации release-проверки исправили тестовые часы, подмены
свежего чтения и повторную проверку уже подтверждённой строки в engine.py.

Локальная реализация и проверки завершены. Delta не активирована: полнота
изменений после складских операций ещё не доказана. Владелец разрешил
Push, Merge, Deploy 2026-10-03; release-проверки и доставка выполняются.
Складские изменения, OAuth и реальные сообщения не выполнялись.
Чужая работа в основном checkout сохранена.

## Что работает

- При подтверждённой полноте провайдера: delta каждые 600 с и ежедневная полная
  сверка 03:17 UTC (06:17 МСК), включая restore mode. Без доказательства остаётся
  прежний полный режим каждые 5 мин. Два задания зарегистрированы и разрешены
  deploy-проверкой. Повторный запуск с пригодным кэшем не скачивает каталог.
- Redis v2 хранит данные 48 ч; клиентский предел возраста остаётся 1 ч. Отдельны
  время фактического наблюдения строки и подтверждённое покрытие всего набора.
  Пустая delta не превращает остатки в 0 и не обновляет время чтения строки.
- Публикация данных и курсора атомарна. Полная/delta синхронизация используют
  один замок с владельцем и продлением; CAS защищает от позднего писателя и
  перезаписи более свежего критического чтения. Курсор привязан к началу цикла,
  overlap120 с. Ошибка страницы/лимит/неверный ответ/потеря замка сохраняет
  прежнее поколение. Многостраничная delta требует двух совпадающих полных
  проходов; повтор ID или сдвиг состава отклоняет цикл.
- КП читает только выбранные SKU заново, обходя оба кэша. ID проверяются,
  запросы объединяются и разбиваются на подтверждённые пакеты. По умолчанию
  неподтверждённый bulk заменён точечными ID GET. Неизвестный ID разрешается
  ограниченным точным поиском SKU. Неполный ответ не разрешает КП по старой цифре.
- По решению владельца: свежие 2 шт. против согласованных 5 останавливают КП,
  сообщают «в наличии только 2» и ждут нового решения клиента. Количество не
  уменьшается молча; старое согласие не используется автоматическим повтором.
  Проверен настоящий код фонового retry с перехваченными внешними эффектами.
- Сохранены guards согласия/реквизитов/уже отправленного КП и идемпотентность.
  429 сохраняет реквизиты и откладывает попытку; каждый реальный retry читает
  остаток заново. Inactive/unknown/0 различаются; rename/remap не возвращает
  старый alias. Stock-sync не пишет website products.is_active/цены/embeddings.
- Общий cooldown атомарно сохраняет максимальный срок, включая Retry-After1800.
  Два общих read-slot ограничивают параллелизм; GET имеет deadline 30 с, короткие
  inline retry ограничены бюджетом. Учитываются реальные HTTP-попытки/статусы,
  повторы, локальные skips, страницы/строки, missing mappings и fresh outcome.

`stock_as_of`: максимум наблюдения самой строки и последней полной сверки;
покрытие успешной delta учитывается только при совпадении доказательства
eligibility. Точечное fresh-чтение не передвигает общий курсор. v1 содержит
последний полный baseline для старого бинарника, с исходным `as_of`.

## Проверки AC01–AC12

| Критерий | Локальное доказательство | Live-граница |
|---|---|---|
| AC01 | normal/restore schedule, UTC slot, регистрация/allowlist, повторный startup | Не выложено |
| AC02 | fixtures складских/lifecycle форм и закрытый gate | Интерфейс GET частично подтверждён; полнота операций отсутствует |
| AC03 | zero/empty/overlap/ties, длинное чтение, page2 error/cap/restart, move/delete page shift | Стабильность страниц/границ Zoho ещё требуется |
| AC04 | Настоящий Redis: параллельные full/delta, истёкшая lease, owner release, commit failure, fresh CAS | Production race не запускалась |
| AC05 | >24 ч idle, daily full, >1 ч degraded, legacy/corrupt/missing cursor, rollback baseline | Флаги не менялись |
| AC06 | Реальный вызов HTTP-адаптера через MockTransport: cached10/fresh2, bypass, chunking, aliases, partial/unknown | Bulk1/2/4/8 прочитан live; КП live не создавалось |
| AC07 | Consent/sent guards, 429, actual background retry, shortage wait/new decision, максимум одно создание | POST/PDF/send перехвачены; не live КП |
| AC08 | Inactive/removal/new/rename, direct/bulk remap retirement, numeric alias precedence | Lifecycle операции не выполнялись |
| AC09 | 1800s, short retry, max concurrent cooldown, shared read-slot/skip/recovery | Существующий внешний account-load incident открыт |
| AC10 | Суточные 157/589/167; HTTP-счётчики realRedis, UTC interval,0 customer full scans | Настоящие 24 ч после активации отсутствуют |
| AC11 | **241 passed**,0 skipped;8 специализированных Redis integration; Ruff/format, mypy193 файлов | Full release:4458 passed,20 gated skips; CI/доставка следуют |
| AC12 | SHA, отчёт/receipts, handoff/stage/Beads, rollback и конкретные оставшиеся действия | Полная приёмка задачи остаётся открытой |

Root acceptance выполнен через `run_stage_closeout.py --stage tj-uvld-stock-sync
--level slice_acceptance --command ...` с точными командами:

```sh
uv run --no-sync ruff check src/ tests/ scripts/zoho_stock_preflight.py scripts/zoho_stock_report.py scripts/orchestration/run_stage_closeout.py
uv run --no-sync ruff format --check src/ tests/ scripts/zoho_stock_preflight.py scripts/zoho_stock_report.py scripts/orchestration/run_stage_closeout.py
uv run --no-sync mypy src/
uv run --no-sync pytest tests/test_zoho_stock_incremental.py tests/test_zoho_stock_bulk.py tests/test_zoho_rate_limit.py tests/test_zoho_client.py tests/test_zoho_sync.py tests/test_worker.py tests/test_llm_quotation.py tests/test_quotation_inventory_deferral.py tests/test_quotation_retry.py tests/integrations/test_zoho_inventory.py tests/integrations/test_zoho_stock_sync_redis.py tests/test_customer_intent_tools.py tests/test_decision_state.py tests/test_dialogue_order_state.py -q --tb=short
git diff --check
scripts/orchestration/run_process_verification.sh --stage tj-uvld-stock-sync
```

Среда: Python 3.12.13, общий подготовленный venv с `UV_PROJECT_ENVIRONMENT`,
`PYTHONPATH` указывает на этот worktree, `PYTHONDONTWRITEBYTECODE=1`.
Тестовый Redis — отдельный Docker-контейнер с уникальным именем и loopback-port;
данные удаляются только в нём. Образ `redis:7.2-alpine` штатно загружается на
чистом runner; нет silent skip или fallback к production Redis.

Первая итоговая попытка нашла два старых retry-теста с неподвижными fake-часами.
Исправлены часы; итог **241 passed in15.78s**, без предупреждений/пропусков.
После этого исправлялись только поля handoff/artifact: кодовые доказательства
повторно использованы по совпадающему source/command/environment digest.
CLI closeout получил отсутствовавший `--command`, заявленный AGENTS/spec.

Доказательства: `.codex/stages/tj-uvld-stock-sync/evidence/`, `closeout-result.json`
и `logs/closeout.log`. `logs/code-acceptance.log` содержит успешные кодовые gates
и последовавшую исправленную ошибку оформления handoff; она не скрыта.
Source digest: `8f85dc2040fe8b80983f6a0a1233c493089942b94ab40c9a2a25133650fe8b09`.

## Расход API

| Сценарий | Вызовы/сутки | Статус |
|---|---:|---|
| Старый nominal:13 страниц ×288 | 3744 | Расчёт базового расписания |
| Старый measured UTC 02.10 08:00–03.10 08:00 / МСК 11:00–11:00 | 3459 (3445×200,14×429) | Ранее измеренные app+worker logs, JSON сохранён |
| 144 одностраничные delta +13 full | **157** | Проверенная синтетическая суточная модель;−95,8% к nominal |
| 144 двухстраничные delta, каждый цикл проверен повторно +13 full | **589** | Проверенный дополнительный расход защиты paging |
| Одностраничный вариант +10 fresh quotation reads | **167** | Проверенный дополнительный критический расход |
| Read-only preflight этой работы | **9 GET** (8×200,1×400) | Live; отдельно от модели и ещё не установленных новых счётчиков |

Модели исключают bootstrap/recovery, дополнительные страницы, retry и другие
потребители организации. Считаются запросы, а не запуски cron. Реальное снижение
production-нагрузки не измерено и не заявляется. Ошибка/отсутствие/expiry
счётчиков — пробел доказательств, не нулевой расход. Retention метрик 7 дней.

Для разрешённого 24 ч окна после rollout:

```sh
PYTHONPATH=. uv run python scripts/zoho_stock_report.py \
  --start '<UTC timestamp at whole seconds>' --end '<UTC timestamp at whole seconds>'
```

Скрипт возвращает `[start,end)`, МСК-конверсию, компоненты HTTP и возраст
текущего кэша. Другие клиенты организации и OAuth исключены; current state
измеряется в момент отчёта, а не реконструируется на конец окна.

## Что действительно проверено live

В 13:06–13:09 UTC (16:06–16:09 МСК) использован только cached token, Redis GET;
перед каждым запросом проверен cooldown. Literal trailingZ дал 400. Numeric UTC
`+0000` дал 200, включая `sort_column=last_modified_time`, `sort_order=A`.
Обе успешные delta пустые. Bulk1/2/4/8 вернул каждый запрошенный ID и числовой
stock_on_hand; **8 — подтверждённый безопасный размер, максимум не установлен**.
Результат не доказывает появление складских изменений в delta.

Mapping обновлён 13:40:23 UTC:343 active catalog rows,250 stored Zoho IDs,
306 SKU matches,2557 legacy snapshot entries. Optional scoping выключен;
непокрытые товары не исключались. Receipts: `docs/research/2026-10-03-zoho-stock/`.
Официальные интерфейсы/ограничения и точные варианты запросов — в README там.

## Следующий разрешаемый диагностический пакет

Сначала нужен утверждённый изолированный Zoho test organization и разрешение
на ограниченные операции над тестовыми товарами. Предлагаемый предел:
до 12 тестовых mutations, до 12 compensating rollback mutations и до 60 Inventory
GET, concurrency1. На 401/429/cooldown — остановка; OAuth/scopes не меняются.
Сначала согласовать конкретные тестовые item/warehouse и допустимые quantities,
без customer orders/messages и без правок каталога сайта. Секреты в чат не нужны.

Проверить fulfillment, receipt, adjustment, return/reversal и transfer, если
последний меняет consumed stock_on_hand; отдельно create/edit/rename/inactive
и удаление тестовой позиции. Для каждого: время/поле/old-new quantity,
ID-consistency full/delta/bulk и следующий modified-since с overlap. Операцию,
не меняющую stock_on_hand, отметить отдельно от потери delta coverage.
Проверить nonempty pagination, equal timestamps и изменения состава страниц;
не добавлять неподдерживаемую верхнюю границу/secondary sort. Hard deletion
может обнаруживаться полной сверкой, но нельзя пропускать другие строки.

Альтернатива — уже существующая redacted история этих операций с доказанными
временами и количеством, достаточная для read-only сопоставления. Иначе gate
остаётся закрытым и решение по другой архитектуре требует владельца.

Доставка кода с закрытым delta gate разрешена владельцем 2026-10-03.
Перед включением оптимизированного расписания требуется AC02 и отдельное
разрешение активации; затем 24 ч реальных метрик. Флаги:
`ZOHO_STOCK_INCREMENTAL_ENABLED=true` и непустой `ZOHO_STOCK_COVERAGE_EVIDENCE`
со ссылкой на подтверждённое покрытие этой организации. Для измеренного bulk
можно явно задать `ZOHO_STOCK_BULK_SIZE=8` и `ZOHO_STOCK_BULK_EVIDENCE` со ссылкой
на receipt; любое расширение размера требует новой проверки. Эти значения
подготовлены, но нигде не активированы. Gate — операторское подтверждение,
не автоматический валидатор содержания evidence-файла.

Rollback: выключить incremental flag и убрать coverage evidence в app+worker,
пересоздать только их под разрешением. Полная сверка каждые 5 мин восстановит
больший расход; считать эту нагрузку при rollback. v1/v2, Redis/ARQ и бизнес-
данные не удалять. Старый бинарник использует последний полный v1 baseline с
исходным as_of; после 1 ч он требует bounded read/unavailable, не новую freshness.

Read-only correctness review завершён: все найденные substantive defects
исправлены с регрессиями; новых P0/P1/P2 must-fix не осталось. Provider coverage,
stable paging и live24 ч — явные внешние условия. tj-4kot внешний account-load
incident и tj-535g monitoring не закрывались и не объединялись с этой задачей.

Вспомогательные clean worktrees docs/review и task-owned Redis удалены.
Основной worktree с коммитами сохранён для продолжения; primary не изменён.

## Разрешённая доставка и полная проверка

Владелец разрешил Push, Merge, Deploy2026-10-03. Canonical release выполнен:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$PWD UV_PROJECT_ENVIRONMENT=/home/me/code/treejar/.venv uv run --no-sync python scripts/orchestration/run_stage_closeout.py --stage tj-uvld-stock-sync --level release
```

**4458 passed,20 skipped in118.25s**, Ruff/format/mypy193/process passed.
Пропуски — существующие явно включаемые live-интеграции/реальные модели,
отдельный semantic pgvector и три PostgreSQL admin-проверки; не новые skips.
Runner также выполнил настроенные risk groups concurrency/migration/API/e2e.
Release sidecars и logs/release-acceptance.log сохранены; старый
closeout-result.json относится к slice_acceptance, не к новой delivery-проверке.
Source digest1c4aeb8b8a8b9b5b38c43ef7fa7a46db62ab3c00b77068c4702732ca07a84a2b.

Среда — обычный isolated clone с basename treejar и каноническим HTTPS remote:
этого требуют существующие registry/corpus проверки. Первый запуск обнаружил
этот environmental gate и21 старый quote mock, retry clock и предел размера
engine; причины исправлены, тесты не отключались. Четыре legacy quote файла
прошли747 focused tests; root clock/structure checks —10.
Python3.12.13, Node24.19.0/npm11.17.0; CI использует Python3.13/Node22.
Release-environment.json фиксирует lock/image digests.

Перед выкладкой read-only runtime показал36c8613, здоровые app/worker/DB/Redis,
2557 legacy entries, отсутствие v2 и cooldown. SHA .env и safety fingerprint
сохранены для сравнения; UUID канала не интерпретируется как номер телефона.
Delta и bulk-size overrides не включаются этой доставкой.
