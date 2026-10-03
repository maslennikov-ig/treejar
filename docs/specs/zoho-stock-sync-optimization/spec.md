# Zoho stock synchronization: selective refresh and truthful quotation reads

Date: 2026-10-03. Status: local candidate implemented; provider coverage and delivery gates open.
Owner/task: **tj-uvld**, P1 feature. Beads owns status and remaining gates.
Executor: `docs/prompts/2026-10-03-zoho-stock-sync-optimization.md`.

## 1. Outcome and acceptance boundary

Reduce Noor's background Zoho Inventory traffic while keeping customer stock
figures grounded in Zoho. The approved design has three levels:

1. Poll changed items every **10 minutes**.
2. Perform **one complete reconciliation per day**.
3. Read the exact selected items freshly, in batches, before an actual
   quotation creation attempt, after existing consent, details and duplicate
   guards pass. Normal discovery continues to use the shared stock cache.

Implement and test the complete local path now. Live activation is a distinct
boundary: the provider's stock-change coverage must be proved and the owner
must approve merge/deployment and any external write-based diagnostic.
Preparing this specification does not activate the feature or start an agent.

## 2. Current evidence and sources

- Base/main/live at the readiness audit:
  `36c86137a51d2e6485db92c28ec057fe26f03339`; refresh before implementation.
- `src/worker.py::build_worker_cron_jobs` schedules a full stock refresh
  at minutes 1, 6,..., 56, including restore mode and startup.
- `src/integrations/inventory/zoho_inventory.py::_build_stock_snapshot`
  requests 200 records/page, all active items, with no end-product filter.
- Current full list: about 2557 SKUs / 13 pages. Nominal background load:
  13 × 288 = 3744 calls/day. Measured 24h: 3459 calls, 3445 HTTP 200, 14 HTTP 429,
  265 complete refreshes, 23 unsuccessful refreshes including 9 local skips.
  Evidence: `docs/reports/2026-10-03-zoho-api-statistics.json`.
- Current Redis snapshot has a 3600s retention TTL and one dataset-wide
  `as_of`; misses can initiate a full refresh in the customer path.
- `_create_quotation` calls `get_stock_bulk`, which can return the snapshot.
  A fresh critical read therefore needs an explicit cache bypass.
- Read-only mapping audit 2026-10-03T12:14:30Z: 343 active catalog products,
  250 stored Zoho IDs, 306 SKU matches in the snapshot. These counts can drift;
  refresh them. Do not assume 343 catalog rows are 343 uniquely mapped IDs.
  API capability probes were skipped because the shared cooldown was active;
  bulk size and live delta behavior were **not** verified.
- Related `tj-4kot`: provider Retry-After 1800 was persisted as 300 seconds.
  Local accepted fix:
  `07591b8b1dba05c2124af0468a089adc26efa717`, branch
  `codex/tj-4kot-zoho-cooldown`. Reuse that commit if absent from the new base;
  inspect ancestry and do not duplicate it. The external account-load incident
  stays open. `tj-535g` monitoring is a separate fix, outside this task.

Official sources checked 2026-10-03:

- [Items API](https://www.zoho.com/inventory/api/v1/items/#list-all-the-items):
  `last_modified_time` query filter, pagination and status filtering.
- [Bulk item details](https://www.zoho.com/inventory/api/v1/items/#bulk-fetch-item-details):
  `GET /itemdetails` with comma-separated `item_ids`; supported numeric stock
  fields and effective maximum batch size require account-side verification.
- [API limits](https://www.zoho.com/inventory/api/v1/introduction/#api-call-limit):
  organization minute limit, plan daily limits and concurrent limits.
- [Automation](https://www.zoho.com/us/inventory/help/settings/automation.html):
  workflow webhooks exist on selected plans. Webhooks are a future improvement,
  not part of this implementation.

Documentation confirms the request interfaces, not the completeness of
modification timestamps for every stock-affecting operation.

## 3. Scope and invariants

- Zoho remains the source of stock. Preserve the current stock quantity field
  and SKU matching rules; do not switch from stock_on_hand to available stock
  or import website quantities as a shortcut.
- Discovery catalog, prices, embeddings, prompt/model routing, customer
  records, consent, quotation fingerprint/idempotency and notifications retain
  their existing contracts.
- Missing, malformed, unavailable, inactive and a numeric zero are distinct.
  A successful empty delta means no changes, not zero stock or an empty cache.
- Existing full-cache consumers must keep working across the format change.
  No per-SKU polling of the whole catalog on each cycle.
- Use the existing application, worker and Redis. No new dependency, paid
  integration, event platform or mandatory second model reader.
- Mapping-aware scoping is optional within the optimization, after all needed
  mappings are verified. Do not lose the 37 currently unmatched catalog rows,
  alternative SKUs, direct item-ID reads or future products.
- Do not change `TEST_CHANNEL_RESTORE_MODE`, test 0665 allowlists, Telegram
  reconciliation, monitoring activation, CRM flows or customer data.

## 4. Provider preflight and eligibility

Implement an explicit eligibility gate for delta freshness. Before turning it
on, establish that the same item identity and numeric stock fields are
returned by full, delta and bulk reads in the target organization.

Prove that each supported operation changing the consumed stock field appears
in a subsequent modified-since read: sale/fulfillment, receipt, inventory
adjustment, return/reversal and warehouse transfer when it changes that field.
Also test item creation, edit, rename/SKU change, deactivation and deletion.
Document which lifecycle changes arrive in a delta and which require the daily
full comparison; do not require a hard-deleted row to appear in an item list.
Do not assume creating a sales order changes physical stock; measure the
actual operation and field semantics. Record operations which do not affect
that field separately from missing delta coverage.

Local fixtures must cover these shapes immediately. Provider completeness
needs an authorized test organization or owner-approved bounded transaction
diagnostic. Existing redacted production history may support a read-only
check but is not a substitute for otherwise unobserved operation coverage.
Record provenance, timestamps, operation and old/new quantities; avoid
customer payloads and secrets in tracked evidence.

Read-only provider preflight: reuse a cached token, honor an active cooldown,
stop on 429/401 and record unavailable evidence; do not refresh OAuth or expand
scopes as a convenience. Verify bulk boundaries with a small bounded series
of GETs and confirm that all requested IDs and stock fields are returned.
Never assume the list page size 200 is the bulk endpoint's limit.

If coverage is unknown or fails, keep the proven full mode operational and
finish the local implementation/tests behind the gate. Report exactly what
live evidence or alternative design needs owner input. Do not enable the
optimized mode, claim the 157-call result, or close the task as fully accepted.

## 5. Synchronization contract

### 5.1 Scheduling and startup

- Incremental mode: one delta job per 600s and one full reconciliation per 86400s.
  Use the repository's worker timezone explicitly; select a configurable daily
  slot offset from other full catalog jobs. Scheduling must be inspectable.
- Both stock jobs must remain registered and allowed in restore mode; update
  the deploy probe allowlist and its tests. Other restore-mode jobs are unchanged.
- A complete initial snapshot is required before delta consumption. Bootstrap
  under the shared lock when missing; an application/worker restart with valid
  state must not initiate another full download automatically.
- Customer cache misses enqueue/coalesce recovery or use a bounded direct read;
  they must not fan out complete catalog downloads.

### 5.2 Cursor, paging and atomic publication

- Store a UTC successful coverage watermark alongside the accepted cache
  generation, last successful full reconciliation and last successful delta.
  Query with a small configurable overlap, initially 120s, and merge by stable
  Zoho item_id. Preserve canonical SKU aliases and resolve renames explicitly.
- Bind a cycle to its start time, query boundary and generation. Do not advance
  the next watermark to response completion time: changes during a long read
  must remain eligible next time. Check provider sorting/paging semantics; do
  not invent an unsupported upper-bound or stable secondary-sort parameter.
- Consume every page until the provider says there is no next page. A failed
  page, cap reached, malformed response, expired lease or failed Redis
  publication must not advance the cursor or publish a partial cycle.
- Empty successful delta can advance coverage after validating the response.
  Existing items remain. Zero is applied only from an explicit numeric value.
  A valid item with unknown stock stays unknown; it is not a malformed response
  and must not be converted to zero or stamped as a newly verified old quantity.
- Publish data and watermark as one consistent generation. Full and delta
  share one owned lock, with renewal or bounded duration and a generation/owner
  check at publication. Hold ownership through publication, not only fetch.
  Late writers cannot overwrite newer data or delete another owner's lock.
- Repeated overlap items and a restarted cycle are idempotent. Test changes
  during multi-page reads, equal timestamps and concurrent full/delta cycles.

### 5.3 Cache lifecycle and compatibility

- Separate storage retention from permitted customer staleness. The current
  one-hour Redis TTL cannot support a once-daily full reconciliation. Choose a
  retention window of at least 48h without treating that retained data as fresh.
- Healthy sync interval: 10min. Preserve the existing one-hour degraded read
  ceiling unless an explicit owner decision changes it. Past that ceiling use
  bounded live resolution or the existing unavailable/deferred behavior.
- Track source observation for records separately from successful dataset
  coverage. A successful update of one item must not relabel unverified old
  data as newly read from Zoho. Successful complete delta coverage can establish
  that untouched records have not changed only after the eligibility gate passes.
- Document `stock_as_of` semantics. Keep as_of behavior truthful across v1/v2
  migration, empty deltas, API failures, a missing cursor and corrupt cache.
- Use versioned cache state or a compatible reader transition. Activation and
  rollback must preserve a usable full-mode snapshot; no broad Redis deletion.
- Successful full reconciliation replaces the complete set, handles inactive
  or removed items and refreshes identity mappings. It must not rewrite the
  website-owned `products.is_active`, prices or embeddings.

## 6. Fresh quotation verification

- Provide an explicit fresh/bypass read path, distinct from discovery reads.
  It bypasses the stock snapshot and any HTTP read-response cache.
- Resolve only selected SKUs to verified IDs, deduplicate requests and fetch
  chunks within the measured bulk limit. Unknown/ambiguous mappings require
  bounded exact-SKU resolution; no invented IDs or catalog-wide refresh.
- Run this check only after consent, required details and unchanged-sent quote
  checks pass. Every actual retry attempt also requires fresh stock evidence.
- Validate identity and numeric stock on every requested item. Partial results
  may update the successfully verified cache rows, but cannot authorize a quote
  using stale fallback for the missing rows.
  Any such cache update must respect generation/observation ordering; a late
  full or delta writer cannot overwrite a newer critical read.
- Owner decision2026-10-03: if fresh stock2 is below agreed quantity5, stop
  quotation creation, state only2 available and wait for a new customer
  decision. Do not silently reduce quantities. Defer consent and prevent the
  same turn or automatic retry from reusing pre-shortfall consent.
- On 429, unavailable or incomplete critical reads, preserve customer details
  and use the existing quotation deferral/retry path. Never blindly retry a
  POST/write, create a duplicate quote, report a quote as created before its
  external ID is persisted, or add a manager escalation outside existing policy.

## 7. Load control, metrics and budget

- Shared cooldown and owned sync lock apply across app and worker. Preserve
  the accepted long Retry-After fix; concurrent responses cannot shorten an
  already longer cooldown. Bound read concurrency and inline retry time.
- Record actual Inventory HTTP attempts by operation and status, retry attempts,
  locally skipped calls separately, pages/items processed, cache age/coverage,
  last successful full/delta, missing mappings and fresh quotation-read outcome.
  Parse provider limit reason where available; otherwise label it unknown.
  No credentials, customer text, raw URLs or business item IDs in metrics logs.
- Counters must be shared and reproducible for an explicit UTC interval, with
  Moscow conversion for user reports. Counting cron invocations is insufficient.
- Baseline nominal 3744/day. Reference scenario: 144 single-page delta checks
  + 13 full pages = 157 background attempts/day, excluding bootstrap, retries,
  additional delta pages and quotation verification. This is a conditional
  model, not a live promise. Report all these components and actual reductions.
- A script/fixture running a simulated 24h schedule must assert request counts
  and zero per-turn full downloads. A real 24h measurement is required after
  authorized activation to claim actual production savings. External account
  consumers remain outside Noor's counters and can still cause 429s.

## 8. Acceptance ledger and required tests

Every criterion belongs to **tj-uvld**; the live provider/delivery conditions
are explicit gates, not omitted acceptance. Tests use synthetic data and
intercept all model, business-write and messaging calls.

| ID | Observable requirement | Verification |
|---|---|---|
| AC01 | Delta 600s + daily full, normal/restore modes, controlled startup | Worker schedule/registration, deploy allowlist and repeated-start tests |
| AC02 | Eligible modified-since interface and stock-operation completeness | Local operation fixtures + named provider coverage evidence; gate remains closed when absent |
| AC03 | Complete paged merge and consistent data/cursor | Empty delta, zero, overlap, equal timestamps, page 2 failure, caps, restart/crash tests |
| AC04 | One valid writer, no stale overwrites | Concurrent full/delta, lease expiry, Redis commit failure and lock-owner tests using disposable local Redis |
| AC05 | Truthful retention, coverage age and cache compatibility | >24h synthetic idle catalog, failed sync, >1h degraded coverage, legacy/corrupt/missing state and rollback tests |
| AC06 | Selected-SKU fresh bulk reads before quote | Stale cached 10 vs live 2; actual HTTP bypass, chunking, identity, SKU aliases, unknown mapping and incomplete bulk tests |
| AC07 | Quote consent/idempotency/deferral unchanged | No-consent and already-sent turns make no critical read/write; 429 defers; retry freshly reads and creates at most once |
| AC08 | Inactive/removed/new/renamed items stay truthful | No false 0, no stale alias resurrection, new mapping discovered, no website product/price/embedding mutations |
| AC09 | Rate limits are respected across processes | Retry-After 1800, small inline retry, concurrent cooldown extension, skipped-job and recovery tests |
| AC10 | Reduction is measured, not guessed | Simulated 24h 157-call scenario and burst/multi-page scenarios, shared counters and no redundant customer full scans |
| AC11 | Local quality and user-path integration pass | Focused pytest acceptance, real local Redis race tests, Ruff/format, mypy; no provider writes or paid model calls |
| AC12 | Exact source and remaining live gates are reviewable | Commit-bound report, Beads/handoff, rollback instructions; provider coverage/activation/24h proof listed separately |

Representative Given/When/Then scenarios:

- Given cached A=10, B=5, when a complete delta returns A=0 only, then A=0, B=5;
  an empty delta changes neither; a page 2 failure changes neither cache nor cursor.
- Given discovery cached 10, when the fresh quote read returns 2 for selected
  quantity 5, then the existing stock-shortfall policy uses 2 and never cached 10.
  On 429, no quote/customer business POST or message is emitted by the test.
- Given consent missing or an unchanged already-sent quotation, then no new
  fresh inventory request and no external quotation creation occurs.
- Given an old writer's lease expired and another generation committed, then
  the old writer cannot publish or release the newer lease.

## 9. Cohesive implementation plan and owning files

One owner/branch/worktree implements the adapter, synchronization state,
worker schedule, quotation consumer adoption, metrics, tests and durable docs.
Do not split helpers/tests into standalone delivery tasks.

Main write zone:

- `src/integrations/inventory/zoho_inventory.py` and `sync.py`;
- a small stock-sync state/helper module there if separation is useful;
- `src/worker.py`, relevant `src/core/config.py` settings;
- scoped inventory call sites in `src/llm/engine.py` and retry adapters if needed;
- `scripts/vps-deploy.sh` registration probe; opt-in bounded diagnostics/report script;
- `tests/test_zoho_stock_incremental.py`, `tests/test_zoho_stock_bulk.py`,
  existing Zoho/worker/quotation tests;
  `tests/integrations/test_zoho_stock_sync_redis.py` for real local Redis;
- this spec, an acceptance report, Beads and current-state handoff/stage files.

Sequence:

1. Refresh repository/Beads/runtime evidence, inspect the prepared cooldown
   commit and record actual API/coverage gaps. Create a dedicated worktree.
2. Implement the complete gated hybrid state machine and the fresh quotation
   consumer path; add focused regressions and shared load counters.
3. Run local integration including Redis concurrency and intercept quotation
   side effects; run one root-owned final acceptance and review the diff.
4. Commit locally, report exact source and current task status. Prepare a
   concrete activation/rollback and provider diagnostic packet before asking
   for any required external authority. Do not stop at a plan or unit mocks.

Root-selected focused final acceptance (add the new test modules and the local
Redis integration module to this same set, rather than rerunning unrelated suites):

```sh
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy src/
uv run pytest tests/test_zoho_stock_incremental.py tests/test_zoho_stock_bulk.py tests/test_zoho_rate_limit.py tests/test_zoho_client.py tests/test_zoho_sync.py tests/test_worker.py tests/test_llm_quotation.py tests/test_quotation_inventory_deferral.py tests/test_quotation_retry.py tests/integrations/test_zoho_inventory.py tests/integrations/test_zoho_stock_sync_redis.py -q --tb=short
scripts/orchestration/run_process_verification.sh
git diff --check
```

Use isolated test service URLs; prevent real model calls, OAuth refresh,
business POSTs and outbound messages. Real Redis tests use a disposable local
instance or unique task-owned test namespace, never production Redis writes.
If a stage is opened, use `run_stage_closeout.py --stage <id> --level
slice_acceptance --command '<focused command>'` for the single root acceptance.
The full configured suite/CI belongs to release acceptance before a separately
approved deployment. Do not silently skip failing tests in linked worktrees.

## 10. Failure preflight and recovery

Technical premortem: **GO WITH CONDITIONS** for local implementation;
activation depends on AC02 and current delivery authority.
Blast radius: sync/API adapter -> shared Redis cache/cursor -> stock discovery
and quotation attempts -> app/worker schedules. Website catalog and CRM writes
are not part of the synchronization change.

| Failure symptom | Evidence/mechanism | Detection and mitigation |
|---|---|---|
| Quantity changed but delta missed it | Plausible; provider operation coverage unproved | AC02 named operation evidence blocks activation; preserve full mode |
| Daily cache disappears after 1h | Confirmed current 3600s TTL | AC05; separate retention and coverage freshness |
| Stale quote passes despite fresh-read feature | Confirmed current bulk path reads snapshot | AC06 HTTP interception proves explicit bypass |
| Partial cycle skips changes forever | Plausible cursor/page/commit ordering | AC03/04; atomic generation and replay same cursor |
| Lock released before publication permits old overwrite | Confirmed current refresh releases before Redis snapshot set | AC04; own lease through fenced publication |
| Scope filtering loses catalog rows | Confirmed 306/343 snapshot matches at audit | AC08; scoped mode requires verified mapping, bounded resolution |
| Executor invents bulk limit or treats mocks as provider proof | Plausible execution error | Source-linked preflight, measured chunk limit, explicit gated evidence |

Rollback: disable incremental activation and resume proven full mode with the
prepared long-cooldown fix. Preserve v1-compatible full snapshot or bootstrap
one under an owned lease; do not clear all Redis keys or reset customer state.
Treat increased full-mode request load as an explicit operational consequence.
Validate rollback reads and scheduling locally before requesting delivery.

## 11. Delivery, evidence and explicit defers

Reversible local implementation, tests, local commits and scoped read-only
checks are authorized by the current request. Merge, deployment, external
stock test transactions, new access, paid calls and real messages are not.
Follow current AGENTS.md rather than historical deployment permissions.

Report `local_verified`, `provider_coverage_verified`, `live_activated` and
`live_24h_measured` separately, each with evidence or a specific pending gate.
Write the implementation report to
`docs/reports/<completion-date>-zoho-stock-sync-optimization.md`; include exact
SHA, commands/results, provider coverage/chunk limit, API counts, normal/error
user behavior, and recovery. Keep Beads open when required acceptance is pending.

Explicit defers: workflow webhooks (plan/event coverage not established),
outside account consumer attribution (`tj-4kot`), separate monitoring fix
(`tj-535g`), production delivery and post-activation 24h proof until approved.
No scope reduction or substituted design without explaining the evidence and
obtaining a decision where the resulting stock freshness/coverage changes.
