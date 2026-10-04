# Read-only follow-up, tj-uvld

Owner boundary: working organization only, no warehouse mutations. Diagnostics
so far used cached tokens, with no OAuth/access change, paid call or messaging.
Owner requested separate read-only access setup; no new grant issued yet.
Runtime remains25a8c080; deltaOFF.

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

## Separate read-only access, owner login pending

One additional GET on04Oct10:06UTC returned401/code57 (not_authorized).
history-error-readonly.json and history-error-readonly.source.txt retain only
safe metadata and the executed source. The existing cache TTL2632s does not
prove provider validity. Historical configuration requested no history READ
scopes; the response does not distinguish missing scopes from user-role limits.
No retry, refresh, token replacement or existing-client revocation was attempted.

The current Inventory/CRM client is shared. Create a NEW EU server-based client
through the owner's browser consent; preserve the existing client and tokens.
The preparation is locally tested; owner authorization in Zoho is not complete.

1. Start the bounded loopback server from this worktree:

   ```sh
   PYTHONDONTWRITEBYTECODE=1 UV_PROJECT_ENVIRONMENT=/home/me/code/treejar/.venv \
     uv run --no-sync python docs/research/2026-10-04-zoho-stock/history-access.py
   ```

2. In the Windows browser, sign in to [EU API Console](https://api-console.zoho.eu/).
   Add Client → Server-based Applications. Client Name: `Noor stock audit read-only`;
   Homepage URL: `https://noor.starec.ai`; exact Authorized Redirect URI:
   `http://127.0.0.1:8769/zoho-history/callback`.
3. Enter the NEW client ID/secret only in `http://127.0.0.1:8769/`, never chat.
   Inspect the Zoho consent screen before approving the six requested READ scopes:
   items, inventoryadjustments, purchasereceives, salesreturns, transferorders,
   packages. The flow uses `access_type=online`, no refresh token, <=1h lifetime.
   Local handler expires after15min; restart it if it expired before consent.
4. After the successful callback, run the bounded audit:

   ```sh
   PYTHONDONTWRITEBYTECODE=1 UV_PROJECT_ENVIRONMENT=/home/me/code/treejar/.venv \
     uv run --no-sync python docs/research/2026-10-04-zoho-stock/history-grant-probe.py
   ```

The token lives only in the user-owned700 directory
`/home/me/.local/state/treejar/tj-uvld/zoho-history/`, as a600 file outside Git.
The client secret/code remain in memory and are never logged. A pre-existing
token is not overwritten; an expired token requires exact-file local cleanup
after ownership/permissions verification before a fresh owner flow.
The wrapper sends the token only through encrypted SSH stdin, never process
arguments/environment or remote files. Before any GET, it verifies organization
fingerprint and the fixed EU API host. Redis is read only. <=16 sequential GETs,
no retries/refresh, existing cooldown and401/429 stops; no metrics/config writes.
The original executed audit source remains unchanged and SHA-pinned.

17 offline tests intercept OAuth/SSH/provider transport. Windows HTTP200 and
real loopback guard statuses establish local reachability, not live OAuth or
operation coverage. Safe source-bound receipts: history-access-checks.txt and
history-access-local-http.json. Scope fields label requested scopes separately
from provider-reported scopes; an absent scope response is not verified scope proof.

An API history sample still does not prove stock-change coverage, equal-time
paging, or otherwise unobserved lifecycle types. Need causal before/after
observations of ordinary owner operations. Keep deltaOFF until AC02 is met.

Official access contract:
[Inventory OAuth](https://www.zoho.com/inventory/api/v1/oauth/),
[Client registration](https://www.zoho.com/developer/oauth/register-app.html),
[Server-based flow](https://www.zoho.com/developer/oauth/web-server-apps/overview.html).
