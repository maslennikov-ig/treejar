# Zoho stock-sync — Push, Merge, Deploy

Дата:2026-10-03. Beads:tj-uvld остаётся in_progress.
Разрешение владельца: «Push, Merge, Deploy».

В remote main выполнен fast-forward36c8613 → **25a8c080e9b014333380b8e62be7d5e981daefe7**.
Этот SHA установлен и независимо прочитан в live app и worker. Чужой dirty
primary checkout не изменён; его main остаётся на36c8613. Последующий коммит
только с receipts/docs будет в main, но не изменит установленный code SHA.

Полные проверки: локально **4458 passed,20 skipped in118.25s**;
[CI37130777663](https://github.com/maslennikov-ig/treejar/actions/runs/37130777663)
**4451 passed,27 skipped in96.50s**, lint/type-check/test/deploy success.
Разница — существующие gated DB/live/model tests; failing tests не отключались.
Semantic-evidence job пропущен по штатному paths gate: его источники не менялись.
Redis races выполнялись на отдельном настоящем Docker Redis, не production.

## Live-проверки

25 проверок прошли в14:51–14:52 UTC:

- host/app/worker release SHA совпадает с25a8c080e9b014333380b8e62be7d5e981daefe7;
- SHA256 восьми изменённых файлов совпадают с локальным проверенным кодом;
- app/worker running,0 restarts, без OOM;
- HTTPS health подтверждает релиз, DB и Redis healthy;
- SHA256 .env и safety fingerprint не изменились; restore mode=true,
  sender=outbound allowlist, Telegram test-phone ending0665 сохранён;
- контейнеры DB/Redis/nginx не пересозданы;
- restore functions/cron проверены: fallback full каждые5 мин, delta зарегистрирован
  как функция, но не запланирован при закрытом eligibility gate;
- новый v2 содержит2557 позиций с TTL48h, legacy last-full mirror совпадает.

В точном UTC **[14:50:52,14:53:10)** / МСК **[17:50:52,17:53:10)**
новые shared counters показали **13 HTTP attempts,13 HTTP200,13 страниц,
2557 строк,1 успешный full cycle**. Start — первая целая секунда запуска
новых app/worker. 429/retry в этом окне не зарегистрированы. Это реальная
ограниченная проверка fallback режима; результат нельзя переносить на сутки
или считать доказательством экономии. Старые binaries до этого окна и другие
потребители организации/OAuth не входят в новые счётчики.

Команда отчёта для текущего Docker image (CLI script хранится на host,
в образ копируется runtime src):

```sh
cd /opt/noor
docker compose exec -T -e PYTHONPATH=/app app python - \
  --start 2026-10-03T14:50:52Z --end 2026-10-03T14:53:10Z \
  < scripts/zoho_stock_report.py
```

Receipts: docs/research/2026-10-03-zoho-stock/delivery/. Они содержат только
aggregate stock state, fingerprints/hashes, container metadata и CI summaries;
credentials, SKU/customer payloads и номера отправителей не сохранены.

## Что ещё не принято

| Статус | Значение | Доказательство / условие |
|---|---|---|
| local_verified | true | Focused241 + release4458, realRedis races, review |
| live_deployed | true | Exact app+worker SHA,25 readback checks и live13GET cycle |
| provider_coverage_verified | false | AC02: stock-operation/lifecycle/nonempty paging coverage не доказано |
| live_activated | false | Оптимизированная delta выключена, coverage evidence пусто |
| live_24h_measured | false | После доказанного покрытия/активации ещё нужно24h окно |

Fresh selected-item проверка перед КП и правило shortage2 vs5 установлены,
локально проверены; live quotation POST/PDF/send не запускались. Bulk override
остаётся0: runtime использует точечные ID GET; live bulk8 — доказанный безопасный
нижний размер, не установленный максимум. Catalog scoping выключен.

Перед включением delta нужен согласованный Zoho test organization и отдельное
разрешение на диагностический пакет из основного отчёта: до12 тестовых
mutations +12 compensating rollback mutations и60 InventoryGET, concurrency1;
или достаточная redacted история реальных операций для read-only сверки.
На401/429/cooldown остановка; без OAuth/access expansion и real-user messages.
Тогда доказать AC02, отдельно активировать delta и измерить24h реальные расходы.
До этого tj-uvld открыт; tj-4kot account-load incident и tj-535g monitoring
остаются отдельными. Reused cooldown correction уже выложен в этом релизе.

## Восстановление

Delta сейчас выключена, поэтому отключение флага не требуется. При будущем
rollback оптимизированного режима отключить eligibility и пересоздать только
app/worker, сохранив env/allowlists/Redis/ARQ. Для rollback binary использовать
проверенный предыдущий36c8613 по обычной доставке с сохранением test worker;
не делать force-push и не удалять v2/legacy/held messages/business records.
v1 сохраняет исходный as_of последней полной сверки и прежний предел1h.

docs-reviewed: updated - delivery receipt, exact live state and pending provider gates.
graph-reviewed: no-change-needed - no enabled task-owned graph.
