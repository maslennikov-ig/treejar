# Orchestrator Handoff

Updated: 2026-07-27
Current branch: `main`
Current stage id: `tj-15m`
Current stage status: accepted; delivery-aware matrix complete

## Current Truth

- Canonical runtime: `https://noor.starec.ai`.
- Stabilization epic `tj-av22` and production operations/cleanup stages are
  accepted and closed.
- Zoho CRM and Inventory EU refresh tokens were restored through the protected
  production path. Direct and application-native read-only probes pass, and
  later deployments preserved the credentials.
- Wazzup's configured WhatsApp channel is active.
- Stage `tj-15m` completed its authorized FAQ, product, comparison, order,
  Arabic, and escalation matrix on the approved synthetic recipient.
- Exact production code release
  `292d82cdbe7a041787093779173d3e051c052ccb` was delivered by GitHub Actions
  run `30251148113`; lint, type-check, tests, and deploy passed.
- Production health is `ok`, version `0.4.0`; Redis and PostgreSQL are `ok`;
  app, worker, nginx, Redis, and database containers are running.
- Accepted stage fixes:
  - quantity before numeric/`CH`/`CP` SKU references is retained;
  - explicit no-quotation requests do not enter quote routing;
  - first-turn Arabic and Arabic `اسمي <name>` replies are handled in Arabic;
  - explicit one/two product option limits are respected;
  - deferred product media is reconciled to final-response references;
  - translated `NEW` variants retain stable model-code media matching.
- Latest local release gates passed Ruff, format, Mypy over `162` source files,
  and Pytest (`1532 passed, 19 skipped`).
- Final six-scenario delivery-aware durations:
  - FAQ `22.147s`;
  - product `24.411s`;
  - comparison `37.775s`;
  - order `8.703s`;
  - Arabic `21.051s`;
  - escalation `7.657s`.
- Linear-interpolation summary: `p50 21.599s`, `p95 34.434s`, maximum
  `37.775s`.
- Maximum passes the `45s` ceiling. p50/p95 miss their targets. The explicit
  external-model blocker is supported by a product trace with `model_tools`
  `30.803s` of `37.462s` total versus outbound text `0.231s`.
- All customer-visible text/media audits are `sent`, have provider message
  IDs, and have no error details. Four attached-caption audit rows are also
  `sent` and error-free without separate provider IDs. The synthetic
  escalation was exactly resolved; no pending synthetic escalation remains.
- Raw recipient/channel/conversation evidence is protected on the VPS with mode
  `600` and is not stored in Git, Beads, handoff, or public logs.
- Graphify is not configured; `graphify-out/GRAPH_REPORT.md` is absent.

## Boundary and Scope Ledger

- One cohesive stage owned the shared recipient, provider channel, production
  queue, correctness contract, and exact cleanup boundary.
- Work remained root-owned and sequential; no subagent stream had a material
  parallel, specialist, context-isolation, or write-isolation benefit.
- No scope criterion was dropped and no v2.19 material split occurred.
- Excluded actions remained excluded: quotation creation/media, voice, payment,
  referral, and real-customer traffic.

## Next recommended

Next stage id: `tj-0j7o`

Recommended action: benchmark safe core-chat model/provider or routing
candidates against the same ordinary-text correctness contract. Do not switch
production model/provider until a candidate preserves catalog price source,
Zoho stock truth, order/quote/escalation behavior, Arabic quality, and
duplicate cleanup and receives explicit release authorization.

## Starter prompt for next orchestrator

Use $orchestrator-stage for `tj-0j7o`. Treat `tj-15m` as accepted immutable
history. Compare viable core-chat model/provider or routing candidates using
the existing six-scenario correctness contract and privacy-safe latency phases.
Keep the work local/read-only until a release candidate is evidence-backed;
ask before any production model/provider switch or new live matrix.

## Approval gates

- Existing authorization covered the completed bounded production matrix and
  exact synthetic cleanup.
- A production model/provider switch is a new release boundary and requires
  explicit current-task authorization.
- Preserve protected credentials and unrelated user files.

## Explicit defers

- `tj-0j7o`: model/provider benchmark; separate quality and release boundary
  created from the accepted external-model latency blocker.
- Referral launch `tj-final27.6`, WABA approval `tj-gh21`, catalog GH #54
  `tj-2pkk`, new soft/hard escalation policy `tj-g3f`, delivery-source policy
  `tj-9q0`, and Zoho UTM mapping `tj-hye` remain separate external gates.
