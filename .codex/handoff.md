# Orchestrator Handoff

Updated: 2026-07-27
Current branch: `main`
Current stage id: `tj-j13d`
Current stage status: in progress; grounded model adoption and authorized deployment

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
  and Pytest (`1588 passed, 19 skipped`).
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
- Extended model battle `tj-5e3k` is accepted. It compared four candidates per
  route with two repetitions: 96 sales and 192 fast/system calls using only
  fixed synthetic cases. Production routing remained unchanged.
- Sales strict winner: keep `z-ai/glm-5`. It scored `93.975`, passed every hard
  gate, achieved `93.50%` blind quality and `10.710s` p95. GLM-5.2, DeepSeek
  V4 Flash, and DeepSeek V4 Pro each had at least one blind critical finding.
- Fast/system strict outcome: `no_safe_replacement`; every candidate missed
  the `95%` semantic gate.
- Practical fast/system hardening target: `deepseek/deepseek-v4-pro`, weighted
  `85.353`, with `100%` first-pass JSON/schema, reliability, tool arguments,
  and reasoning-disable compliance, plus `12.168s` p95. It reached `72.82%`
  semantic accuracy and consistently failed `system-red-03`.
- DeepSeek V4 Flash remains the semantic reference at `73.79%`, weighted
  `84.133`, and consistently failed `system-red-01`.
- Nex-N2-Mini ignored reasoning disable in all 48 runs, returned seven
  first-attempt 502 errors, and achieved only `70%` JSON/schema. GLM-5.2 was
  not selected for either route.
- Review corrections and final hardening cover negated claims, exact
  suite/model/matrix provenance, punctuation normalization, explicit reasoning
  diagnostics, balanced anonymous labels, and both final P3 regressions.
- Durable report:
  `docs/reports/model-battle-glm52-v4pro-2026-07-27.md`; raw and derived
  evidence: `.codex/stages/tj-5e3k/results/`.
- Stage `tj-j13d` implements the approved product decision: GLM-5.2 for core
  sales and DeepSeek V4 Flash for default fast/helper routes, with one
  immutable evidence-grounding contract and capability registry.
- Repository FAQ truth confirms UAE showroom visits and conditional project
  samples. The new policy preserves those capabilities while keeping stock,
  operational price, quotation, order state, discounts, and exceptional terms
  behind their existing evidence/tool/manager gates.

## Boundary and Scope Ledger

- One cohesive active stage owns model routing, grounding policy, provider
  verification, deployment, rollback, and post-deploy smoke.
- Root owns the sequential implementation and deploy chain. One
  context-isolated combined reviewer is reserved for the release boundary.
- No scope criterion was dropped and no v2.19 material split occurred.
- Excluded actions remained excluded: production routing, customer traffic,
  quotation/order creation, Zoho/Wazzup mutations, and real customer data.

## Next recommended

Next stage id: `tj-j13d`

Recommended action: implement the approved GLM-5.2/V4 Flash routing and shared
grounding policy through TDD, release review, authorized deploy, rollback
capture, and bounded post-deploy smoke. `tj-b93r` remains separate historical
grounding evidence and must not duplicate this stage.

## Starter prompt for next orchestrator

Use $orchestrator-stage for `tj-j13d`. Execute
`docs/superpowers/plans/2026-07-27-noor-model-switch-grounding.md`, preserve the
accepted benchmark evidence, and deploy only the locally verified release.
Run bounded synthetic post-deploy tests without outbound customer messaging or
business-system mutations.

## Approval gates

- Existing authorization covered the completed bounded production matrix and
  exact synthetic cleanup.
- The user explicitly authorized this stage's production model switch, deploy,
  and bounded post-deploy tests.
- Outbound customer messaging, quotation/order creation, and Zoho mutations
  remain outside that authorization.
- Preserve protected credentials and unrelated user files.

## Explicit defers

- No adoption defer remains inside `tj-j13d`; deployment is gated by its local
  release, provider, review, rollback, and post-deploy acceptance checks.
- GLM-5 weak-catalog grounding is tracked by `tj-b93r`.
- Referral launch `tj-final27.6`, WABA approval `tj-gh21`, catalog GH #54
  `tj-2pkk`, new soft/hard escalation policy `tj-g3f`, delivery-source policy
  `tj-9q0`, and Zoho UTM mapping `tj-hye` remain separate external gates.
