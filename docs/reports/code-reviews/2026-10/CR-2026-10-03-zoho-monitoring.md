# Code Review: Zoho cooldown and runtime monitoring

Date: 2026-10-03. Scope: two isolated fixes based on live/main
`36c86137a51d2e6485db92c28ec057fe26f03339`; four changed Python files.
Reviewer: root agent, direct diff, callers and history review.

Verdict: PASS for the focused local acceptance. No blocking findings in the
selected changes. Integration and production delivery remain pending owner
approval; these commits are not in main or the running containers.

## Inventory: tj-4kot

Branch: `codex/tj-4kot-zoho-cooldown`.
Commit: `07591b8b1dba05c2124af0468a089adc26efa717`.

`src/integrations/inventory/zoho_inventory.py` truncated a provider's
`Retry-After: 1800` to 300 seconds when persisting the shared cooldown. The
warning still printed 1800, masking the early retry. The patch preserves the
provider pause up to a bounded one day and logs the effective stored pause.
Read retries, inline waiting budgets, stock refresh schedule, stale fallback
and quotation write safeguards retain their existing behavior.

Regression evidence: before the fix, the 1800-second test failed because the
Redis TTL was 300. After the fix, the tests prove shared suppression after 301
seconds and one successful HTTP call after expiration for 1800, 7200 and a
capped extreme value. Failure leaves the previous stock snapshot untouched.

Acceptance command, run from the inventory worktree with its path in
`PYTHONPATH` and `UV_PROJECT_ENVIRONMENT=/home/me/code/treejar/.venv`:

```sh
uv run --no-sync pytest tests/test_zoho_rate_limit.py tests/test_zoho_client.py tests/test_zoho_sync.py tests/test_quotation_retry.py tests/integrations/test_zoho_inventory.py -q --tb=short
```

Result: 67 passed. Ruff check/format of the two files and mypy of the changed
source passed. Process verification and `git diff --check` passed.

The original shared-account incident remains open: fixing Noor's early retry
does not identify other consumers or guarantee elimination of upstream 429s.

## Monitoring: tj-535g

Branch: `codex/tj-535g-monitoring`.
Commit: `a4cc1a7f532e8df25973e3e61250803594f10302`.

`src/services/runtime_monitoring.py` bound an aware datetime to
`Escalation.created_at`, a PostgreSQL timestamp without time zone. asyncpg
rejected that parameter, and the collector converted the unavailable count
to zero while reporting a dependency failure. The patch normalizes the cutoff
to naive UTC, preserves unavailable counts as null, and evaluates the stale
escalation threshold only for a measured count. No database migration or
monitoring activation is included.

Four regression cases failed before the fix and passed afterward: UTC and
UTC+3 observations at the actual naive timestamp boundary, count-query
failure, and database unavailability.

Acceptance command, run from the monitoring worktree with its path in
`PYTHONPATH` and the same virtual environment:

```sh
uv run --no-sync pytest tests/test_runtime_monitoring.py -q --tb=short
```

Result: 17 passed. Ruff check/format of the two files, mypy of the changed
source, process verification and `git diff --check` passed.

Actual production-schema proof at 2026-10-03T08:16:31Z: the candidate source
was loaded only into a temporary Python process in the worker container.
The database transaction was read-only and rolled back; no files, settings,
jobs, alerts or business records were written. The collector returned 45 old
pending escalations, matching independent SQL, and zero dependency errors.
Candidate source SHA256:
`4ff1ee1460b106d1db3907b7397d859c05abcd843b1f1a5bf0f95ef4a743fc08`.
Local proof: `/tmp/treejar-monitoring-candidate-proof-20261003.json`.

## Client statistics and delivery boundary

The bounded log measurement is stored in
`docs/reports/2026-10-03-zoho-api-statistics.json`; the client explanation and
questions are in the HTML of the same name. Window: 2026-10-02T08:00Z to
2026-10-03T08:00Z, end exclusive. Counts: 3459 Zoho API requests, 3445 HTTP200,
14 HTTP429, 265 completed refreshes, 23 unsuccessful refreshes including nine
local cooldown skips. Peak rolling 60 seconds: 13 requests. Runtime logs
redact URL paths; host-based measurement excludes OAuth token requests and
does not expose customer payloads.

The 100/minute organization limit and separate daily/concurrent limits are
documented by [Zoho](https://www.zoho.com/inventory/api/v1/introduction/#api-call-limit).
Noor's logs do not reveal organization-wide traffic or the precise 429 code.
Repeated four-hour windows suggest a scheduled exchange, not a proven owner.
The client page asks for the integrations and actual quota; no secret is
requested. Daily nominal refresh load is 13 × 288 = 3744 calls.

Client-page acceptance: zero lint errors/warnings; all six width/theme checks
(400, 800, 1440 px, light/dark) passed in a Windows Chrome browser; mobile and
desktop screenshots were inspected. The portal publication uses an existing
Treejar project. No answers were submitted and no client message was sent.

docs-reviewed: updated - readiness, fixes and client evidence recorded.
graph-reviewed: no-change-needed - isolated fixes, no graph used.
