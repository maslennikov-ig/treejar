# Stage tj-15m Summary

Updated: 2026-07-24
Status: blocked on Wazzup WhatsApp channel reconnection
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

- Zoho restoration:
  - Viktor supplied fresh EU Self Client grants for CRM and Inventory;
  - both grants were exchanged before expiry and the resulting long-lived
    refresh tokens were installed through the protected production path;
  - direct and application-native CRM and Inventory read-only probes returned
    `HTTP 200`;
  - production OAuth caches were cleared and repopulated without exposing
    credentials;
  - subsequent canonical deployments preserved the rotated configuration.
- Accepted production corrections:
  - `e4959e0` preserves a quantity before numeric, `CH`, and `CP` SKU
    references and avoids asking for quantity again;
  - `3ebb69c` respects explicit no-quotation requests and cleans repeated
    `units of SKU` wrappers;
  - `cee1f7d` detects strongly Arabic first-turn text before the deterministic
    name gate so the Noor identity and name question are Arabic.
- Fresh release evidence:
  - GitHub Actions run `30098682854` passed lint, type-check, tests, and deploy;
  - production activated exact release
    `cee1f7d4ba05eba5107d38bd5388c2b5b4622d55`;
  - local release gates passed: Ruff check, Ruff format check, Mypy over `162`
    source files, and Pytest (`1528 passed, 19 skipped`);
  - production health is `ok`, version `0.4.0`, Redis `ok`, database `ok`.
- Protected internal-processing observations after Zoho restoration:
  - FAQ name gate `7.519s`, FAQ answer `14.818s`, product `20.748s`,
    comparison `18.684s`;
  - the corrected order processing path completed in `9.481s`, retained
    quantity `2`, used a current SKU verified through the local catalog and
    Zoho, and did not create a quotation;
  - the pre-correction Arabic path reproduced the English name gate in
    `6.285s`; the deployed correction is regression-covered but was not sent
    again after the provider blocker was identified.
- Delivery boundary:
  - the configured Wazzup WhatsApp channel was found by the read-only channels
    API, but reports state `qridle`;
  - production outbound audits return `MESSAGE_CHANNEL_UNAVAILABLE`;
  - the durations above therefore prove only assistant-response persistence,
    not customer-visible WhatsApp delivery;
  - no customer-visible `p50`, `p95`, or maximum is claimed.
- One malformed synthetic helper attempt accidentally captured a debug line
  instead of the intended SKU. It affected only the approved synthetic
  recipient and created no quotation, order, or escalation.
- Stop rule applied: no more live messages were sent after confirming the
  unavailable channel. The escalation scenario and post-fix Arabic delivery
  rerun remain unsent.
- External blocker `tj-15m.10`: the Wazzup account owner must reconnect the
  configured WhatsApp session, then one approved canary must prove successful
  provider delivery before the remaining matrix resumes.

## Closeout

- `docs-reviewed: updated` — `docs/latency-evidence.md` separates internal
  persistence timing from failed Wazzup delivery and records the exact external
  reconnection gate.
- `project-index: reviewed-no-change` — no entrypoint change is planned.
- `graph-reviewed: no-change-needed` — the optional graph report is absent and
  this localized correction does not change architecture or entrypoints.
