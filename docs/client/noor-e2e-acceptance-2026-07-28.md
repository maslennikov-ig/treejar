# Приёмочное тестирование Noor — консервативный gate-only прогон

Идентификатор запуска: `tj-ee5f-live-20260728t165236z`
Сформирован: 2026-07-28T16:53:20.629626+00:00

## Итог

- Полнота покрытия: да
- Полнота исполнения: да
- Требования выполнены: нет

## Вывод для клиента

Production-среда Noor доступна и её техническая идентичность подтверждена:
health `ok`, версия `0.4.0`, актуальная миграция и ожидаемые модели. Однако
готовность продукта по приёмочным требованиям **не доказана**.

Все 29 запланированных единиц получили честный статус `BLOCKED`. Диалоги,
сообщения провайдеру, обращения к моделям и бизнес-операции не выполнялись.
Поэтому в отчёте нет вопросов/ответов и фактических задержек диалогов; нулевые
значения времени означают отсутствие выполненных диалогов, а не мгновенный
ответ Noor.

Причины блокировки:

- один тестовый номер не доказывает изоляцию нескольких независимых клиентов;
- WhatsApp canary нельзя считать provider-originated при отправке через
  application-native webhook;
- для CRM, КП, Telegram и других побочных эффектов не было одновременно
  доказано исходное состояние, независимый readback и безопасная очистка;
- для evidence-блоков отсутствовали независимые collectors, достаточные для
  результата `PASS` или `FAIL`.

Внешних действий, платных вызовов и изменений данных в ходе этого запуска не
было. Для полноценной приёмки нужен новый immutable run с раздельными
синтетическими идентичностями, настоящими provider-originated canary и
независимыми readback/cleanup-доказательствами.

## Идентичность среды

- Commit: `deab79b1134210a9d1fbb7691137363263e1cd98`
- Release: `0dd9615a16fdf4eb17abe156551c53fb77f39c21`
- CI: `github-actions-30379943318`
- Версия: `0.4.0`
- Миграция: `2026_06_04_customer_memory`
- Модели: z-ai/glm-5.2, deepseek/deepseek-v4-flash
- Сервисы: {"runtime": "preflight-verified"}

## Диалоги

## Критерии

- AC-01: BLOCKED (fresh); evidence=mode-01-AC-01, mode-02-AC-01, mode-19-AC-01, mode-20-AC-01, mode-21-AC-01; Derived from protected accepted producer facts.
- AC-02: BLOCKED (fresh); evidence=mode-01-AC-02, mode-02-AC-02, mode-09-AC-02, mode-18-AC-02; Derived from protected accepted producer facts.
- AC-03: BLOCKED (fresh); evidence=mode-01-AC-03, mode-02-AC-03, mode-11-AC-03, mode-13-AC-03, mode-18-AC-03, mode-19-AC-03, mode-20-AC-03; Derived from protected accepted producer facts.
- AC-04: BLOCKED (fresh); evidence=mode-03-AC-04, mode-04-AC-04; Derived from protected accepted producer facts.
- AC-05: BLOCKED (fresh); evidence=mode-05-AC-05, mode-06-AC-05, mode-17-AC-05, mode-18-AC-05; Derived from protected accepted producer facts.
- AC-06: BLOCKED (fresh); evidence=mode-01-AC-06, mode-05-AC-06, mode-18-AC-06; Derived from protected accepted producer facts.
- AC-07: BLOCKED (external_gate); evidence=mode-06-AC-07, mode-14-AC-07; Derived from protected accepted producer facts.
- AC-08: BLOCKED (external_gate); evidence=mode-07-AC-08; Derived from protected accepted producer facts.
- AC-09: BLOCKED (external_gate); evidence=mode-12-AC-09; Derived from protected accepted producer facts.
- AC-10: BLOCKED (external_gate); evidence=mode-08-AC-10, mode-18-AC-10; Derived from protected accepted producer facts.
- AC-11: BLOCKED (external_gate); evidence=mode-09-AC-11, mode-18-AC-11; Derived from protected accepted producer facts.
- AC-12: BLOCKED (external_gate); evidence=mode-09-AC-12; Derived from protected accepted producer facts.
- AC-13: BLOCKED (fresh); evidence=mode-13-AC-13, mode-15-AC-13, mode-18-AC-13; Derived from protected accepted producer facts.
- AC-14: BLOCKED (external_gate); evidence=mode-08-AC-14, mode-15-AC-14, mode-18-AC-14; Derived from protected accepted producer facts.
- AC-15: BLOCKED (external_gate); evidence=mode-10-AC-15, mode-11-AC-15, mode-16-AC-15; Derived from protected accepted producer facts.
- AC-16: BLOCKED (external_gate); evidence=mode-22-AC-16; Derived from protected accepted producer facts.
- AC-17: BLOCKED (fresh); evidence=mode-23-AC-17; Derived from protected accepted producer facts.
- AC-18: BLOCKED (fresh); evidence=mode-23-AC-18; Derived from protected accepted producer facts.
- AC-19: BLOCKED (external_gate); evidence=mode-22-AC-19, mode-23-AC-19; Derived from protected accepted producer facts.
- AC-20: BLOCKED (fresh); evidence=mode-05-AC-20, mode-18-AC-20; Derived from protected accepted producer facts.
- AC-21: BLOCKED (external_gate); evidence=mode-29-AC-21; Derived from protected accepted producer facts.
- AC-22: BLOCKED (reused_exact); evidence=mode-25-AC-22; Derived from protected accepted producer facts.
- AC-23: BLOCKED (fresh); evidence=mode-19-AC-23, mode-20-AC-23, mode-21-AC-23; Derived from protected accepted producer facts.
- AC-24: BLOCKED (external_gate); evidence=mode-27-AC-24; Derived from protected accepted producer facts.
- AC-25: BLOCKED (external_gate); evidence=mode-24-AC-25; Derived from protected accepted producer facts.
- AC-26: BLOCKED (external_gate); evidence=mode-26-AC-26; Derived from protected accepted producer facts.
- AC-27: BLOCKED (external_gate); evidence=mode-28-AC-27; Derived from protected accepted producer facts.
- AC-28: BLOCKED (external_gate); evidence=mode-28-AC-28; Derived from protected accepted producer facts.
- AC-29: BLOCKED (fresh); evidence=mode-05-AC-29, mode-17-AC-29; Derived from protected accepted producer facts.
- AC-30: BLOCKED (external_gate); evidence=mode-06-AC-30, mode-14-AC-30, mode-21-AC-30; Derived from protected accepted producer facts.

## Побочные эффекты


## Производительность

- p50: 0 ms
- p95: 0 ms
- max: 0 ms

## Ограничения и внешние условия

- Сценарии и внешние действия не выполнялись: все 29 единиц получили BLOCKED при отсутствии независимого доказательства.

## Дефекты
