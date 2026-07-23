# Stage tj-15m Summary

Updated: 2026-07-23
Status: in progress
Branch: `main`
Beads: `tj-15m`

## Cohesive Boundary

This stage executes the already-authorized bounded live synthetic matrix
against the canonical production release. It measures customer-visible text
latency while checking FAQ, catalog, comparison, order, Arabic, and escalation
correctness under one approved recipient/channel and exact synthetic cleanup
boundary.

## Exact Authorized Scope

- Recipient: the repository-approved synthetic WhatsApp test recipient; raw
  phone and channel identifiers stay only in protected VPS evidence.
- Identity: one unique `tj-15m-<scenario>-<UTC timestamp>` suffix per scenario;
  outbound delivery strips the suffix to the approved recipient.
- Scenarios:
  - `faq`: ordinary Treejar MOQ/process question;
  - `product`: catalog-grounded acoustic-pod recommendation;
  - `compare`: two ergonomic-chair options without invented facts;
  - `order`: exact known SKU order intent without creating a quote;
  - `arabic`: catalog-grounded Arabic chair request and Arabic reply;
  - `escalation`: explicit manager/discount request with exact post-test
    resolution.
- Evidence: protected raw helper output, wall-clock duration, privacy-safe
  `noor_chat_latency` records, response-quality checks, escalation state, and
  final no-pending/health readback.

## Stop Rules

Stop on health failure, wrong destination/channel, duplicate customer-visible
send, invented price/stock/discount/delivery/payment promise, non-Arabic Arabic
response, unresolved test escalation, or a helper timeout. Do not widen into
quotation media, voice, payment, referral, or real-customer traffic.

## Routing

- Skills: `orchestrator-stage`, `task-router`, `senior-devops`,
  `systematic-debugging` on failure, `verification-before-completion`, and
  `orchestration-closeout`.
- Documentation: repository E2E runbook and current latency evidence; no
  version-sensitive dependency research is needed for execution.
- Delegation: root-owned sequential execution because all scenarios share one
  real recipient, provider channel, production queue, and cleanup boundary.
- Graphify: not configured; live evidence does not require graph refresh.

## Evidence

Pending execution.

## Closeout

- `docs-reviewed: pending`
- `project-index: reviewed-no-change` — no entrypoint change is planned.
- `graph-reviewed: no-change-needed` — Graphify is not configured.
