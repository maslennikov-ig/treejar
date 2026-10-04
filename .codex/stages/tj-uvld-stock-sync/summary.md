# tj-uvld stock optimization

Scope: AC01–AC12, one cohesive local candidate; Beads tj-uvld stays open.
Base36c86137a51d2e6485db92c28ec057fe26f03339, dedicated branch/worktree.
Implementation SHA:0b5c723eeb96c240d2c1654f6b570d951aa782eb.
Report:docs/reports/2026-10-03-zoho-stock-sync-optimization.md.
Local review and root final focused acceptance passed. External gates remain open.

Implementation includes gated hybrid scheduling, versioned48h stock retention,
cycle-start coverage, paged validation/overlap, owned lease and generation CAS,
legacy last-full mirror, selected-only HTTP bypass and bounded mapping,
truthful unknown/inactive/rename/removal behavior, shared cooldown/read slots,
shared actual attempt/status counters and quotation consumer adoption.
Shortfall stops creation and awaits a new customer decision, per owner reply.

Read-only provider preflight9GETs:8HTTP200,1HTTP400; +0000 sorted empty
modified-since accepted; bulk1/2/4/8 identities/numeric stock verified.
No transaction coverage/nonempty paged semantics proof. Mapping refreshed343
catalog rows,250 stored IDs,306 matches/2557 snapshot entries; scoping off.

API models under synthetic HTTP transport and real Redis:157 single-page;
589 two-page deltas including repeat validation;167 with10 fresh quote reads.
No customer full scans. These are conditional models, not production savings.

## Routing and review

| Stream | Ownership | Decision and benefit |
|---|---|---|
| Cohesive implementation/tests | root, stock modules + consumers | local: tightly coupled state/quote contract |
| Provider docs | provider_docs, read-only dedicated tree | parallel: authoritative docs isolated, role-default Luna |
| Correctness review | stock_correctness_review, read-only dedicated tree | parallel: independent concurrency/lifecycle/user-path review, role-default6.1 |

Read-only child outputs integrated into provider evidence and review regressions.
Review fixes: preserve exact SKU collisions, numeric alias precedence,
shortfall deferred-consent/guard, inactive direct-ID rejection, direct/bulk
mapping retirement, repeated-page/set detection, clean-runner Redis startup.
No child source edits, no paid reader. Auxiliary clean worktrees can be removed;
root candidate retained pending external authority.
Clean auxiliary docs/review worktrees and branches removed; disposable Redis
containers stopped/removed. Canonical Beads reread:in_progress, local_verified
true, provider_coverage_verified/live_activated/live_24h_verified false.
GitHub sync trigger enqueuedtj-uvld; completion not independently claimed.

## Verification and delivery

Root acceptance:241 passed in15.78s, no skipped tests.8 Redis integration
tests use a disposable Docker Redis; all provider/business/model/messaging
requests are synthetic/intercepted. Ruff/format passed432 files, mypy193
source files; process verification and canonical closeout passed.
Source digest:8f85dc2040fe8b80983f6a0a1233c493089942b94ab40c9a2a25133650fe8b09.
The first final attempt found two old retry-clock fixtures; corrected and
rerun. A handoff-only process failure was corrected; code evidence reused.
Owner authorized push/merge/deploy2026-10-03. Full canonical release now passed:
4458 tests,20 existing gated skips; Ruff/format/mypy/process passed. Code/tests
5f9e992 include b30096a clock/structure fixes. No provider business writes,
OAuth changes, flag activation or real outbound messages. Delivery completed in25a8c080e9b014333380b8e62be7d5e981daefe7;
provider coverage and optimized24h proof remain separate. Task stays in_progress.

## Explicit defers

- tj-uvld: AC02 operation/lifecycle/paging provider evidence.
- tj-uvld: provider-gated activation and actual24h optimized counters (AC10/AC12).
- tj-4kot outside account load and tj-535g monitoring remain separate.

docs-reviewed: updated - provider research/receipts, spec clarification, report,
entrypoints, current handoff and rollback instructions.
graph-reviewed: no-change-needed - no enabled task-owned graph; file navigation sufficient.

Owner authorized Push, Merge, Deploy2026-10-03. Full release checks run in an
ordinary isolated clone; linked-worktree corpus assumptions remain tj-bgwu.
project-index: reviewed-no-change - release evidence configuration only;
stock runtime and CLI entrypoints are already indexed.

Release quote-test stream accepted as5f9e992; delegated commitd773bf4 patch
equivalence and four file identities verified; clean worker tree/branch removed.
Root reviewed all test changes;747 focused checks preserved consent/idempotency.
Canonical release used ordinary clone; logs/release-acceptance.log and exact
release_commands sidecars carry the proof. Primary dirty work remains intact.

CI37130777663 success:4451 passed/27 gated skips, deploy completed.
Exact app+worker SHA, eight source hashes each, safety/.env invariants and
DB/Redis/nginx preservation verified;25 checks passed. Live counters prove
13HTTP200/13pages/2557items/1full in UTC[14:50:52,14:53:10). Delta remains
disabled; provider coverage, live quotation and optimized24h proof unverified.
Delivery receipt docs/reports/2026-10-03-zoho-stock-sync-delivery.md.
Root worktree stays for the open provider/activation boundary.

## 2026-10-04 read-only continuation

Owner requires working organization only; no warehouse mutations. Existing
push/merge/deploy authority retained. Source/deployed release25a8c080 unchanged;
24fresh live comparisons passed, safe channel/env/container invariants preserved.
UTC[03Oct14:50:52,04Oct06:00:00):2019attempts,2015HTTP200,4HTTP429/minute,
155successful full cycles,4failures,23local cooldown skips.15h9m8s full-mode
observation, not optimized24h evidence. No production savings claim.

Bounded read-only history diagnostic:5GET,4HTTP200+1HTTP401. Stopped on the
adjustment history endpoint without OAuth refresh, retry, writes or access
change.9returned timestamps precede the last24h filter boundary: semantics
need clarification; this is not causal proof of a missed stock operation.
No complete nonempty paging/lifecycle/operation evidence.6offline guard checks
and diagnostic Ruff/format passed; all business side effects intercepted.
Root kept this tightly coupled investigation local; no new delegation needed.

Report:docs/reports/2026-10-04-zoho-stock-sync-optimization.md.
Receipts and runnable guards:docs/research/2026-10-04-zoho-stock/.
Reuse exact existing code acceptance; only docs/research/current-state changed.
Remaining:read-only causal history/access data, then proven provider gate,
optimized activation and actual24h proof. Stage internal_ready/task in_progress.

## Separate read-only access preparation

Owner requested continuing through read-only access setup. One additional
cached-token GET at10:06UTC returned401/code57 (not_authorized), stopped.
Token cache TTL is metadata, not a guarantee of provider token validity.
Historical grant setup omitted history READ scopes; user role vs grant denial
remains unproved. Existing Inventory/CRM client must not be edited/revoked.

Root prepared history-access.py (EU, online, six exact READ scopes, local
password form, one state-bound code exchange, private600 token/no refresh)
and history-grant-probe.py (pinned audit source, SSH stdin only, organization/
API-host fencing before requests, <=16GET, existing cooldown/401/429 stops).
17 offline security checks passed; real Windows loopback form HTTP200.
Research README contains registration fields, commands and evidence limits.
No owner login/client consent/new token yet; no production credentials or data
changed. New root-selected source footprint binds diagnostics; release source
footprint/acceptance reused unchanged. No helper stage or redundant deployment.

Task remains in_progress/internal_ready. Next input is owner console login;
access alone cannot certify unobserved stock/lifecycle operations. Delta off.
