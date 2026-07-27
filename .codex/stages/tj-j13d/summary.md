# Stage tj-j13d Summary

Updated: 2026-07-27
Status: accepted, delivered, deployed, and production-smoked
Branch: `main`
Beads: `tj-j13d`

## Boundary

One release boundary owns the GLM-5.2 core switch, DeepSeek V4 Flash helper
switch, immutable grounding contract, capability registry, local/provider
verification, protected production environment update, deployment, rollback,
and post-deploy smoke.

## Streams

| Stream | Owner | Order | Reason |
| --- | --- | --- | --- |
| Configuration, grounding, and tests | root | first | Shared source and acceptance contract |
| Combined release review | context-isolated reviewer | after local gates | Deployment and customer-facing grounding risk |
| Production deploy and smoke | root | last | Hard dependency on accepted release evidence and exact rollback state |

No parallel write stream passes the material-benefit gate: implementation and
deployment share one configuration/prompt boundary, and deployment cannot begin
before the exact local release is accepted.

## Scope Ledger

- Main model GLM-5.2 and fast model V4 Flash.
- V4 Flash reasoning disabled where supported.
- Immutable source/action grounding rule and capability registry.
- Safe unknown/unconfirmed fallback.
- Local, provider, release-review, deploy, health, post-deploy, and rollback
  evidence.
- No customer data, outbound Wazzup, quotation/order creation, or Zoho
  mutation.

## State

- Core customer-facing paths use `z-ai/glm-5.2`.
- Default helper/background paths use `deepseek/deepseek-v4-flash`; the
  centralized OpenRouter policy disables reasoning for V4 Flash, including
  the customer fact extractor.
- The immutable prompt tail authorizes FAQ-backed showroom visits and
  conditional project samples while retaining tool/manager gates for stock,
  price, quotation, order state, discounts, and exceptional terms.
- The bounded verifier checks provider capabilities, four sales-grounding
  cases, and strict helper JSON without customer data or business mutations.
- Review P1 findings for fact-extractor settings and smoke false positives were
  fixed, regression-tested, and accepted by delta-review.

## Verification

- Focused review delta: `73 passed`; focused Ruff/format passed.
- Full local release gates: Ruff and format passed; Mypy passed over `162`
  source files; Pytest `1608 passed, 19 skipped`.
- Pre-deploy OpenRouter smoke: `5/5`, with auditable synthetic replies.
- Protected rollback snapshots preserve release
  `292d82cdbe7a041787093779173d3e051c052ccb`, GLM-5, Xiaomi V2 Flash, and the
  prior production `.env`; both archives are mode `600` with verified SHA-256.
- GitHub Actions run `30270308830` passed `changes`, `lint`, `type-check`,
  `test`, and `deploy`.
- Production release:
  `8ec2f71f3acb3ba37d514b2b220720c724c9f410`.
- Production readback confirmed GLM-5.2/V4 Flash and mode `600` for `.env`.
- App, worker, nginx, Redis, and PostgreSQL are running; public health reports
  Redis/database `ok`; direct Redis/PostgreSQL probes passed.
- Repo-owned production API probe: `8 passed, 0 failed`.
- Fresh app/worker logs contained no matching traceback/critical/unhandled/
  exception/error entries.
- Production-container model-route smoke: `5/5`; no outbound Wazzup, Zoho,
  quote, order, or customer mutation occurred.

## Closeout

- `docs-reviewed: updated` — project index, stage evidence, rollback manifest,
  review, artifact, and handoff document the durable behavior and operator
  proof. README requires no change because it does not pin runtime model IDs.
- `project-index: updated` — added the bounded model-route verifier entrypoint.
- `graph-reviewed: no-change-needed` — Graphify is not configured and
  `graphify-out/GRAPH_REPORT.md` is absent.
- `explicit-defer: tj-n8p6` — pre-existing Ruff drift in
  `scripts/orchestration/`; canonical gates and the new verifier are clean.
