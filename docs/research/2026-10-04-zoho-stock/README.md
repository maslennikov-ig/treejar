# Read-only follow-up, tj-uvld

Owner boundary: working organization only, no warehouse mutations. Read-only
access is now live-verified using the existing EU Self Client; no Viktor login
or new client/code is required. Temporary six-READ access tokens stay in app
memory, no refresh tokens or production token replacement. Runtime25a8c080;
deltaOFF. Earlier cached-token401 receipts are historical, not current access.

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

These documents identify read interfaces, not causal before/after stock coverage.
The cached-token session stopped at adjustments; later Self Client sessions
read adjustment/receive/return/transfer samples. No coverage claim is made.

## Current access: existing Self Client, owner action unnecessary

Prior client instructions are tracked in docs/client-answers/zoho-inventory-code-2026-09.html
(28Sep) and docs/client/zoho-token-renewal-victor.html (general recovery).
The28Sep EU Self Client scope list did not request history READ scopes.
Do not repeat permanent Generate Code/refresh token renewal for this diagnostic.

Three bounded live sessions:

| UTC04Oct | OAuth POST | Inventory GET | Proof |
|---|---:|---:|---|
|10:59:05|1 HTTP200|1 HTTP200|Transport feasibility only; payload shape/source binding not proven by this preliminary receipt|
|11:03:26|1 HTTP200|13 HTTP200|Adjustment list JSON validated; history samples and bounded incomplete delta|
|11:19:26|1 HTTP200|3 HTTP200|Applied quantity adjustment/detail/current-item identity validated|

All three:3600s token, exact six READ scopes reported, zero refresh tokens,
retries, Redis/config/warehouse writes; production cached token unchanged.
Total3 OAuth POST +17 Inventory GET, separately from runtime counters.
Safe receipts: self-client-feasibility-live.json, self-client-history-live.json,
adjustment-observation-live.json. The11:03 executed source is preserved as
self-client-history.executed-source.txt with receipt-matching SHAa92da3a3;
11:19 source SHA1cfb1a37 matches self-client-readonly-probe.py.

Adjustment statusadjusted/quantity, created04Oct06:12:25UTC; selected line+10.
Identity-matched item current stock24, item timestamp16Sep12:46:30UTC.
Old quantity and complete delta membership were not observed; do not derive
old quantity by subtraction. Delta gate stays closed. Packages response shape
was unexpected, not inferred empty. Read the full limits and primary sources
in self-client-access-findings.md.

Offline safeguards (21cases, never live proof):

```sh
PYTHONDONTWRITEBYTECODE=1 UV_PROJECT_ENVIRONMENT=/home/me/code/treejar/.venv \
  uv run --no-sync python docs/research/2026-10-04-zoho-stock/self-client-probe-selftest.py
```

Reviewed bounded history launcher (one token exchange, <=16 InventoryGET,
no retry/refresh/persistence; only for expressly authorized read-only work):

```sh
PYTHONDONTWRITEBYTECODE=1 UV_PROJECT_ENVIRONMENT=/home/me/code/treejar/.venv \
  uv run --no-sync python docs/research/2026-10-04-zoho-stock/self-client-history-run.py
```

The single-adjustment observation used reviewed self-client-readonly-probe.py
through SSH stdin with --examine-adjustment; <=3 InventoryGET. Extra GETs also
check current cooldown. History and adjustment modes are mutually exclusive.
Credentials never leave the production app; safe aggregates alone reach Git.

## Historical manual helper, superseded

history-error-readonly.json records10:06UTC cached-token401/code57; cache TTL
was not provider-validity proof. Existing grant vs user-role cause remains
unproved, but the later six-READ Self Client grant succeeds with the same owner.

history-access.py and history-grant-probe.py were locally prepared operator
prototypes: EU server-based online grant through a loopback callback.17offline
guards and real Windows HTTP200 proved local reachability, not owner consent.
The loopback callback is not usable directly by remote Viktor. No new client
or authorization-code grant was issued. This path is archived and unnecessary
for the current working organization; do not send it as a client instruction.
Safe historical receipts: history-access-checks.txt/history-access-local-http.json.

Current official temporary grant contract:
[Self Client client credentials](https://www.zoho.com/developer/oauth/self-client/client-credentials-flow.html).
Inventory support was established by the live receipts, not assumed from the
generic OAuth documentation. Historical manual code flow:
[Self Client authorization code](https://www.zoho.com/developer/oauth/self-client/authorization-code-flow.html).


## Bounded natural quantity observation, active run

snapshot-watch.py launched04Oct11:48:19UTC (14:48MSK). Stops after the first
quantity comparison or05Oct11:48:19UTC (14:48MSK). Initial full11:46UTC contains
2397 numeric quantity rows; unknown stock values are excluded, never zero.
SourceSHA10acc81d61428af7d497831f0671152b86d40762eae73d3c91c4c535fe8d9447
matches the exact code submitted to app through SSH stdin. Live startup receipt:
snapshot-watch-launch.json.13offline fixtures: snapshot-watch-offline-checks.json.

Current snapshots alone cannot reconstruct historical old quantities. Observer
keeps successive full snapshots in app memory and exports no identifiers/SKU.
Until a natural quantity change occurs, only Redis GET is used: zero Inventory
or OAuth requests. On the first change, reads cached token and executes a bounded
modified-since list (<=15pages, page_context/unique identities required) plus one
current-item identity/quantity confirmation. Total<=16InventoryGET, cooldown at
every request,401/429/other failures stop, no retries/refresh/config/data writes.

One comparison does not certify page stability, operation type coverage or
lifecycle completeness. Provider coverage always remains false in this tool.
Root must read the terminal event and correlate with ordinary operation history.
No automatic chat notification or feature activation is installed.

Read the active private events.jsonl in the runtime directory recorded in
snapshot-watch-launch.json. Check the exact recorded SSHPID and its /proc
command/start time before attributing liveness or terminating. Do not start a
second run while this one is active. No daemon or schedule/service was installed.

Reproduce offline guards:

```sh
PYTHONDONTWRITEBYTECODE=1 UV_PROJECT_ENVIRONMENT=/home/me/code/treejar/.venv PYTHONPATH=$PWD \
  uv run --no-sync python docs/research/2026-10-04-zoho-stock/snapshot-watch-selftest.py
```

After the existing run ends, an explicitly authorized fresh bounded run can use:

```sh
ssh -o ServerAliveInterval=30 -o ServerAliveCountMax=2 noor-server \
  'cd /opt/noor && docker compose exec -T -e PYTHONDONTWRITEBYTECODE=1 app python - --duration-seconds 86400 --interval-seconds 60' \
  < docs/research/2026-10-04-zoho-stock/snapshot-watch.py
```
