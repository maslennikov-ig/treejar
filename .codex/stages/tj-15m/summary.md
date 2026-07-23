# Stage tj-15m Summary

Updated: 2026-07-23
Status: blocked on interactive Zoho credential renewal
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

- Production preflight:
  - exact release `aa0411db16fc4c128e154052729fdc2a24b7f2c6`;
  - health `ok`, Redis `ok`, database `ok`;
  - protected Wazzup channel and API polling key were configured.
- One FAQ canary was accepted by the webhook (`HTTP 200`) under a unique
  approved synthetic suffix. The helper stopped after `128.157s` with no
  correlated assistant reply; the remaining five scenarios were not sent.
- Worker evidence:
  - the durable batch started after about `5.14s`;
  - both direct CRM and Inventory OAuth diagnostics returned `HTTP 200`,
    `error=invalid_code`, and no `access_token`;
  - the first attempt recorded a retryable `oauth_error`; the execution guard
    then quarantined the retry as `uncertain_replay`, preventing duplicate
    external side effects;
  - no completed `noor_chat_latency` sample exists because processing stopped
    before an assistant response.
- Exact synthetic readback: `1` conversation, `1` user message, `0` assistant
  messages, `0` pending escalations, and escalation status `none`. Production
  health remained green.
- Official Zoho guidance for `invalid_code` with `grant_type=refresh_token`
  says the refresh token may have been deleted/revoked and must be issued
  again:
  <https://www.zoho.com/books/api/v4/oauth/#possible-errors>.
- Parser correction:
  - a red test proved `invalid_code` was incorrectly treated as retryable;
  - it is now classified as terminal `invalid_credentials`, avoiding a
    misleading retry before safe quarantine;
  - focused Zoho/CRM/durable-batch coverage passes (`60 passed`).
- External blocker: `tj-15m.7` requires the Zoho account owner to authorize new
  least-privilege CRM and Inventory refresh tokens in the correct data center,
  update protected production configuration, and rerun all six scenarios.
- Acceptance targets (`p50 <= 15s`, `p95 <= 25s`, maximum `<= 45s`) are not
  claimed; the matrix did not reach the model because Zoho OAuth failed first.

## Closeout

- `docs-reviewed: updated` — `docs/latency-evidence.md` records the attempted
  live canary, the non-latency credential blocker, stop decision, and rerun
  requirement.
- `project-index: reviewed-no-change` — no entrypoint change is planned.
- `graph-reviewed: no-change-needed` — Graphify is not configured.
