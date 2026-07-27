# Orchestrator Handoff

Updated: 2026-07-27
Current branch: `main`
Current stage id: `tj-5e3k`
Current stage status: in progress; four-candidate model battle

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
- Model battle `tj-0j7o` is accepted. The core comparison was
  `z-ai/glm-5` versus `deepseek/deepseek-v4-flash`; the fast/system comparison
  was `nex-agi/nex-n2-mini` versus `deepseek/deepseek-v4-flash`.
- Comparative sales choice: keep GLM-5. It scored `92.879` versus `85.395`,
  had equivalent blind quality (`91.33%` versus `91.00%`), and led p95 latency
  (`11.229s` versus `21.962s`).
- Comparative fast/system choice: prefer DeepSeek V4 Flash with reasoning
  disabled and structured validation/fallback. It achieved `97.5%` first-pass
  JSON/schema versus Nex `72.5%` and higher semantic field accuracy (`71.84%`
  versus `64.08%`), while Nex led p95 latency (`5.553s` versus `14.804s`).
- Strict release-gate outcome is `no_safe_replacement` for both battles. Sales
  had one blind critical finding per candidate; both fast candidates missed
  the semantic threshold. Production routing remains unchanged.
- Durable report: `docs/reports/model-battle-2026-07-27.md`; raw and derived
  evidence: `.codex/stages/tj-0j7o/results/`.
- Stage `tj-5e3k` extends both routes with `z-ai/glm-5.2` and
  `deepseek/deepseek-v4-pro`. Both exact IDs and all required structured/tool
  parameters are present in the live OpenRouter catalog.
- The new stage reruns every baseline in the same provider window: four sales
  candidates and four fast/system candidates, using the accepted cases,
  two repetitions, anonymous sales review, and unchanged hard gates.

## Boundary and Scope Ledger

- One cohesive active stage owns the shared OpenRouter evaluation,
  correctness, blinding, and evidence boundary.
- Root owned implementation and sequential inference. One docs specialist
  reviewed provider/methodology risk, and one context-isolated QA reviewer
  scored anonymous A/B sales responses without reading the model key.
- No scope criterion was dropped and no v2.19 material split occurred.
- Excluded actions remained excluded: production routing, customer traffic,
  quotation/order creation, Zoho/Wazzup mutations, and real customer data.

## Next recommended

Next stage id: `tj-5e3k`

Recommended action: complete the four-candidate synthetic benchmark and use
its new route recommendations to re-evaluate `tj-j13d`. `tj-b93r` separately
owns the GLM-5 weak-catalog grounding guard. Deployment remains separately
gated.

## Starter prompt for next orchestrator

Use $orchestrator-stage for `tj-5e3k`. Preserve accepted `tj-0j7o` evidence,
rerun all four candidates per route under the same conditions, finish the
anonymous sales review before unblinding, and record strict and practical
rankings. Ask before deployment or live traffic.

## Approval gates

- Existing authorization covered the completed bounded production matrix and
  exact synthetic cleanup.
- A production model/provider switch is a new release boundary and requires
  explicit current-task authorization.
- Preserve protected credentials and unrelated user files.

## Explicit defers

- Model adoption and deployment remain outside accepted stage `tj-0j7o` and
  must use `tj-j13d` and a separately approved release boundary.
- GLM-5 weak-catalog grounding is tracked by `tj-b93r`.
- Referral launch `tj-final27.6`, WABA approval `tj-gh21`, catalog GH #54
  `tj-2pkk`, new soft/hard escalation policy `tj-g3f`, delivery-source policy
  `tj-9q0`, and Zoho UTM mapping `tj-hye` remain separate external gates.
