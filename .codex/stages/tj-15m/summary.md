# Stage tj-15m Summary

Updated: 2026-07-27
Status: accepted; bounded delivery-aware matrix complete
Branch: `main`
Beads: `tj-15m`

## Cohesive Boundary

This stage executed the authorized six-scenario production synthetic matrix
against `https://noor.starec.ai`. It measured customer-visible text latency
while checking FAQ, product, comparison, order, Arabic, and escalation behavior
under one approved recipient/channel and exact synthetic cleanup boundary.

Raw phone, channel, message, and conversation identifiers remain only in
protected VPS evidence under `/opt/noor/ops/latency` with mode `600`.

## Scope Ledger

- Acceptance owner: root orchestrator.
- Streams: one sequential implementation/production-verification stream.
- Preserved criteria:
  - repeatable six-scenario delivery-aware baseline;
  - catalog, Zoho stock, order, quote, Arabic, and escalation correctness;
  - no duplicate/error/pending synthetic state;
  - local regression and release gates;
  - `p50 <= 15s`, `p95 <= 25s`, maximum `<= 45s`, or an explicit
    external-model blocker.
- Excluded throughout: quotation creation/media, voice, payment, referral, and
  real-customer traffic.
- Replan history: none. Bounded defects were corrected inside the same shared
  acceptance, runtime, and rollback boundary.

## Accepted Corrections

- `e4959e0` preserves quantity before numeric, `CH`, and `CP` SKU references.
- `3ebb69c` respects explicit no-quotation requests.
- `cee1f7d` localizes the first-turn Arabic name gate.
- `cf23aef` captures Arabic `اسمي <name>` replies and resumes the pending
  request instead of escalating.
- `550fca3` respects an explicit request for one or two product options.
- `1ae6df1` reconciles deferred product media to products actually referenced
  by the final response.
- `292d82c` retains referenced media when English variant word `NEW` is
  translated in an Arabic response while still requiring stable model tokens.

GitHub Actions run `30251148113` passed lint, type-check, tests, and deployment
for exact code release `292d82cdbe7a041787093779173d3e051c052ccb`.
The latest local release gates passed Ruff, Ruff format, Mypy over `162` source
files, and Pytest with `1532 passed, 19 skipped`.

## Delivery-Aware Matrix

The matrix uses helper wall-clock time from webhook submission to a correlated
assistant reply, followed by exact outbound-audit readback.

| Scenario | Duration | Correctness and delivery proof |
| --- | ---: | --- |
| FAQ | `22.147s` | Truthful MOQ/process answer; one sent text audit; no error or escalation |
| Product | `24.411s` | Exactly two catalog-grounded alternatives; sent text plus two referenced media audits; no error or escalation |
| Compare | `37.775s` | Exactly two catalog-grounded chairs; sent text plus two referenced media audits; no error or escalation |
| Order | `8.703s` | Quantity `2` retained; current SKU/stock checked; no quotation created; one sent text audit |
| Arabic | `21.051s` | Arabic reply; Treejar prices and current Zoho stock confirmed for both requested SKUs; one sent text audit; no escalation |
| Escalation | `7.657s` | One manager/discount escalation created without a promise, then exactly resolved; one sent text audit |

All customer-visible text and media audit rows have provider message IDs,
status `sent`, and no error details. Four companion caption rows are also
`sent` and error-free; they intentionally have no separate provider ID because
the caption is attached to its media send. The escalation scenario created
exactly one pending row; the scoped cleanup resolved exactly that row, reduced
the global pending count by one, and left unrelated rows unchanged. Final
synthetic pending readback is zero.

Two final Arabic diagnostics are retained as protected evidence but are not
extra matrix samples:

- a broad search truthfully requested clarification when catalog matches were
  weak and sent no unrelated media;
- an exact-SKU comparison used the stock-verification route. Treejar prices
  (`557` and `295` AED) and direct Zoho stock (`94` and `74`) matched the
  response. This route is text-only by design; the translated media-reference
  invariant is covered by the accepted regression test.

## Latency Result

The project percentile implementation uses linear interpolation over the six
accepted samples:

- `p50 = 21.599s`;
- `p95 = 34.434s`;
- `max = 37.775s`.

The maximum passes the `45s` ceiling. The p50 and p95 targets do not pass.
The accepted external-model blocker is evidence-backed: on the slow product
trace, `model_tools` consumed `30.803s` of `37.462s` total, while outbound text
delivery work consumed `0.231s`. A later Arabic trace similarly recorded
`13.387s` in `model_tools` out of `15.057s` total processing. The remaining
reduction therefore crosses the core model/provider quality boundary rather
than the local transport boundary.

Follow-up Bead `tj-0j7o` owns model/provider benchmarking with the same
correctness contract. It does not authorize a production model switch.

## Production Readback

- Exact release marker and deploy run match `292d82c` / `30251148113`.
- Wazzup configured channel is present, transport `whatsapp`, state `active`.
- App, worker, nginx, Redis, and PostgreSQL containers are running.
- `/api/v1/health` returns `status=ok`, version `0.4.0`, Redis `ok`, and
  database `ok`.
- Protected credentials remained outside Git, Beads, chat, and public logs.

## Closeout

- `docs-reviewed: updated` — `docs/latency-evidence.md` and
  `.codex/handoff.md` now record the final matrix, source-specific factual
  checks, external-model blocker, and next bounded stage.
- `project-index: reviewed-no-change` — no entrypoint, route, directory,
  integration ownership, or verification-command boundary changed.
- `graph-reviewed: no-change-needed` — Graphify is not configured and
  `graphify-out/GRAPH_REPORT.md` is absent; no graph refresh is applicable.
- E2E/smoke: applicable and completed through the bounded production matrix,
  outbound audit readback, exact cleanup, release marker, channel state, and
  health checks.
- Explicit defer: only `tj-0j7o`, because choosing or routing to a different
  model/provider is a separate quality and release boundary.
