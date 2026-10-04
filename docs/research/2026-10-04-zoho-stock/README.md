# Read-only follow-up, tj-uvld

Owner boundary: working organization only, no warehouse mutations. No OAuth
refresh/access change, paid call or messaging. Runtime remains25a8c080; deltaOFF.

- runtime.json + health.json: fresh live metadata/hash checks.
- verification.json:24 checks comparing the deployed runtime with03Oct receipt
  and owned source hashes; no source/deployment changes.
- counters.json: exact UTC[03Oct14:50:52,04Oct06:00:00),15h9m8s fallback traffic.
 2019 attempts,2015 HTTP200,4 HTTP429/minute;155 successful full cycles,
 4 failed cycles,23 local cooldown skips. Not optimized24h proof.
- readonly-history.py + readonly-history.json:5 InventoryGETs,4HTTP200 +1HTTP401.
 Stops at inventoryadjustments, no OAuth/retry. Cached-token diagnostic requests
 are counted here, separately from instrumented runtime counters.
- history-analysis.json:9 returned item timestamps precede the delta boundary;
 filter/field semantics unclear, not proof of a missed stock operation.
- diagnostic-selftest.py + diagnostic-local-checks.json:6 offline guard checks
 with intercepted HTTP/Redis; no live provider evidence.
- source-evidence-reuse.json: exact configured runtime/test/script digest
 matches the existing passing release receipt. process-verification.txt:
 current contract, artifact, stage readiness and diff checks passed.

The bound is16 InventoryGETs, concurrency1, at most3 delta pages. History lists
are bounded samples; missing/incomplete results never certify coverage.
Only aggregates, dates, hashes/container metadata are retained. Provider/customer
payloads remain in memory; no item/customer IDs, SKU or credentials are emitted.

Reproduce offline guards from the owned worktree:

```sh
PYTHONDONTWRITEBYTECODE=1 UV_PROJECT_ENVIRONMENT=/home/me/code/treejar/.venv \
  uv run --no-sync python docs/research/2026-10-04-zoho-stock/diagnostic-selftest.py
```

Read-only history invocation used (do not retry a401/429 or refresh OAuth):

```sh
ssh noor-server 'cd /opt/noor && docker compose exec -T app python -' \
  < docs/research/2026-10-04-zoho-stock/readonly-history.py
```

Official interfaces revisited04Oct:

- [Items](https://www.zoho.com/inventory/api/v1/items/#list-all-the-items)
- [Adjustments](https://www.zoho.com/inventory/api/v1/inventoryadjustments/#list-all-the-inventory-adjustments)
- [Purchase receives](https://www.zoho.com/inventory/api/v1/purchasereceives/#list-all-purchase-receives)
- [Sales returns](https://www.zoho.com/inventory/api/v1/salesreturns/#list-all-sales-returns)
- [Transfers](https://www.zoho.com/inventory/api/v1/transferorders/#list-all-the-transfer-orders)
- [Packages](https://www.zoho.com/inventory/api/v1/packages/#list-all-packages)

These documents identify read interfaces. They do not establish causal
before/after stock coverage in the working organization. History operations
other than adjustments were not queried after the stop. No completeness or
operation-coverage claim is made.
