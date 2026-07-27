# Приёмочное тестирование Noor

> Этот Markdown — устойчивый источник клиентского отчёта. PDF создаётся
> только после содержательного утверждения и отдельной визуальной проверки.

## Идентичность запуска

- Run ID:
- UTC / Europe/Moscow:
- Репозиторий и релиз:
- CI run, версия приложения и migration head:
- Endpoint:
- Main / fast model:
- Авторизация, исполнитель, источник и точные квоты:

## Методика

- Версия набора сценариев и seed:
- Конфигурация tester / judge / translation:
- Детерминированные проверки и ограничение judge:
- Независимый readback: source, timestamp, authorization/scenario binding и digest:
- Защищённое raw evidence и immutable anchor: владелец, срок хранения и checksum (без locator):
- Полный редактированный evidence с проверенным evidence index:

## Покрытие требований

Для каждого критерия указываются владелец, режим доказательств, сценарий или
evidence block, outcome и точные ссылки на доказательства.

## Сценарии и точные диалоги

Для каждого хода:

- запланированный и фактический turn ID;
- объяснение ограниченного адаптивного отклонения;
- точный синтетический вопрос;
- точный ответ Noor и безопасные media/caption references;
- исходный язык и русский перевод с provenance;
- send / receive / first-visible / final-text / delivery timestamps;
- модель, route, tools, audit IDs, token/cost при наличии;
- ожидаемое и фактическое поведение;
- hard oracle, reasoning judge и outcome.

## Время и доставка

- first-visible, final-text, media и полная длительность;
- p50, p95, maximum, timeout и retry;
- отдельно model latency и local delivery latency, когда trace это позволяет;
- контракт `<10 секунд` остаётся строгим.

## Дефекты, исправления и ретесты

Историческое failed evidence не переписывается. Указываются исходная попытка,
Beads defect, root cause, invariant test, fix commit, deployed release и новая
append-only retest attempt.

## Побочные эффекты и закрытие

Каждый локальный и внешний artifact должен иметь subsystem и artifact type,
baseline, expected effect, creation path, owner/authority, suppression,
независимо наблюдаемый final readback и один terminal disposition:
`voided`, `closed`, `resolved` или заранее разрешённый
`retained_as_test_evidence`.

## Итог

- coverage_complete:
- execution_complete:
- requirements_met:
- открытые P0/P1:
- ограничения и внешние gates:
