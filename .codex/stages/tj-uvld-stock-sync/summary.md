# tj-uvld stock optimization

Scope: AC01–AC12, one cohesive local candidate; Beads tj-uvld stays open.
Base36c86137a51d2e6485db92c28ec057fe26f03339, dedicated branch/worktree.
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

## Verification and delivery

Root acceptance:241 passed in15.78s, no skipped tests.8 Redis integration
tests use a disposable Docker Redis; all provider/business/model/messaging
requests are synthetic/intercepted. Ruff/format passed432 files, mypy193
source files; process verification and canonical closeout passed.
Source digest:8f85dc2040fe8b80983f6a0a1233c493089942b94ab40c9a2a25133650fe8b09.
The first final attempt found two old retry-clock fixtures; corrected and
rerun. A handoff-only process failure was corrected; code evidence reused.
No main integration, push, deploy, flag activation, provider business writes,
OAuth changes or real outbound messages. Next external action: approved test
organization and bounded stock-operation coverage diagnostic, then separate
release/deployment approval and real24h measurement. Task remains in_progress.

## Explicit defers

- tj-uvld: AC02 operation/lifecycle/paging provider evidence.
- tj-uvld: authorized release/activation and actual24h counters (AC10/AC12).
- tj-4kot outside account load and tj-535g monitoring remain separate.

docs-reviewed: updated - provider research/receipts, spec clarification, report,
entrypoints, current handoff and rollback instructions.
graph-reviewed: no-change-needed - no enabled task-owned graph; file navigation sufficient.
