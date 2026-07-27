# Noor latency evidence

Date: 2026-07-23
Scope: `tj-15m.6`

This note separates three evidence classes: historical production observations,
current repository-path evidence, and controlled local measurements. No
OpenRouter, Zoho, Wazzup, Telegram, production, staging, or paid service was
called while producing this update.

## Current conclusion

The dominant warmed response-time bucket remains the LLM provider plus its
sequential tool turns. Historical in-container profiling showed FAQ lookup at
about `0.11s` while `process_message` still took `21.29–41.75s`. Later bounded
product-search work reduced one direct replay to about `15.25s`, but complete
webhook and product-heavy observations remained about `31–42s`.

Current code inspection found one smaller local delay after the answer was
already persisted: conversation-summary scheduling performed two SQL reads and
a possible Redis enqueue before Wazzup text delivery. The summary is consumed
only by future turns, so it does not belong on the current text-delivery
boundary.

## Change and local evidence

The normal text path now sends the persisted answer before it schedules a
conversation-summary refresh. Summary scheduling still runs in the same job and
retains its existing failure behavior. A focused async contract test proves the
observable order:

```text
text_sent -> summary_enqueued
```

The controlled benchmark models only that scheduling boundary:

```bash
uv run python scripts/benchmark_chat_delivery_boundary.py
```

It uses fixed local delays for both orderings. The expected reduction in
time-to-text is the measured summary-scheduling duration. It does not estimate
real database, Redis, provider, or network time and must not be cited as
production latency.

The 2026-07-23 worktree run used nine samples per ordering and a configured
`30ms` summary phase:

| Controlled boundary | p50 time-to-text |
|---|---:|
| Legacy: summary before send | `60.761ms` |
| Current: summary after send | `30.533ms` |
| Measured reduction | `30.228ms` |

The approximately `30ms` reduction validates the scheduling relationship, not
the real size of the summary phase.

## Privacy-safe runtime measurement

Successful LLM-backed inbound batches now emit one allowlisted
`noor_chat_latency` JSON record. It contains only a schema version, bounded
status, and millisecond durations:

- `queue_wait`
- `pre_llm`
- `llm` (coarse total)
- `llm_context`
- `faq_rag`
- `behavior_rag`
- `model_tools`
- `persist_response`
- `outbound_text`
- `summary_refresh_enqueue`
- `deferred_media`
- `to_text_delivery`
- `total`

The record has no message text, phone, conversation ID, credentials, raw tool
results, or arbitrary labels. The local analyzer rejects any field or phase
outside this allowlist:

```bash
rg 'noor_chat_latency ' /path/to/app.log \
  | uv run python scripts/analyze_chat_latency.py -
```

The report returns sample count, status counts, `p50`, `p95`, maximum, and the
dominant non-aggregate phase. `llm` is retained as the coarse boundary while
`llm_context`, RAG, and `model_tools` attribute its internal work.

## What remains external

Local tests and controlled delays cannot establish the target
`p50 <= 15s`, `p95 <= 25s`, and maximum `<= 45s`. After an approved deployment,
`tj-av22.3` must collect the bounded synthetic matrix for simple FAQ, product
search, multi-product comparison, quotation/order, Arabic, and escalation. The
same run must record provider/model configuration and correctness results.

If `model_tools` remains dominant with local RAG/context phases small, the
remaining blocker is the external model/provider turn path. That evidence
should be recorded rather than weakening catalog, quotation, escalation,
language, or answer-quality behavior.

## Approved live attempt on 2026-07-23

The authorized six-scenario matrix stopped after its first FAQ canary, as
required by the runbook stop rules. The webhook accepted the synthetic message,
but the protected helper observed no assistant reply within 120 seconds and
ended after `128.157s`. The remaining product, comparison, order, Arabic, and
escalation messages were not sent.

This was not a measured LLM latency failure. The worker reached the normal
message path, then both Zoho CRM and Inventory refresh diagnostics returned
`HTTP 200` with `error=invalid_code` and no access token. The durable execution
guard quarantined the batch before replay, so no duplicate external side
effect occurred. Exact aggregate readback found one synthetic conversation and
user message, zero assistant messages, zero pending escalations, and escalation
status `none`; production health remained green.

Zoho documents `invalid_code` for a refresh-token request as a revoked/deleted
refresh-token condition requiring token issuance again:
<https://www.zoho.com/books/api/v4/oauth/#possible-errors>. The application now
classifies this code as terminal `invalid_credentials` instead of scheduling a
misleading transient retry.

Beads `tj-15m.7` tracks the external owner action: issue new least-privilege CRM
and Inventory refresh tokens in the correct data center, update protected
production configuration, verify both refreshes, and rerun the exact matrix.
Until then, no p50, p95, maximum, provider/model, or response-quality target is
claimed from this attempt.

## Credential restoration and bounded rerun on 2026-07-24

Fresh EU Self Client grants for CRM and Inventory were exchanged before expiry.
The resulting long-lived refresh tokens were installed through the protected
production configuration path. Direct and application-native read-only probes
for both services returned `HTTP 200`; OAuth caches were repopulated, and later
canonical deployments preserved the rotated configuration.

The resumed bounded run exposed and accepted three product corrections:

- quantities in `N units of SKU <ref>` are retained for numeric, `CH`, and `CP`
  references;
- explicit instructions not to create a quotation no longer enter exact-quote
  routing, and repeated `units of SKU` wrappers are cleaned correctly;
- strongly Arabic first-turn text sets Arabic before the deterministic Noor
  identity/name gate.

Releases `e4959e0`, `3ebb69c`, and `cee1f7d` delivered these corrections.
GitHub Actions run `30098682854` passed lint, type-check, tests, and deployment.
The final local release suite passed Ruff check, Ruff format check, Mypy over
`162` source files, and Pytest (`1528 passed, 19 skipped`).

Protected processing observations were FAQ name gate `7.519s`, FAQ answer
`14.818s`, product `20.748s`, comparison `18.684s`, and corrected order
`9.481s`. The corrected order retained quantity `2`, used a current
catalog-and-Zoho-verified SKU, and created no quotation. The pre-correction
Arabic attempt reproduced the English name gate in `6.285s`; its deployed
correction is regression-covered.

These values are not customer-visible latency evidence. A read-only Wazzup
channel check found the configured WhatsApp channel in state `qridle`, and
outbound audits returned `MESSAGE_CHANNEL_UNAVAILABLE`. Assistant replies were
persisted but not delivered through WhatsApp. The stage therefore claims no
customer-visible `p50`, `p95`, or maximum.

The stop rule was applied as soon as the unavailable channel was confirmed.
No further live messages were sent. Beads `tj-15m.10` tracks the external owner
action: reconnect/re-authorize the configured WhatsApp session, prove one
approved synthetic canary is actually delivered, then rerun the post-fix Arabic
scenario, escalation/cleanup scenario, and delivery-aware matrix.

## Wazzup reconnection canary on 2026-07-27

The exact configured Wazzup channel now reports transport `whatsapp` and state
`active`. Production health is `ok`; Redis and database dependencies are `ok`,
and the application, worker, nginx, Redis, and database containers are running.

One previously approved synthetic text canary completed in `6.797s`. Exact
readback found one user message, one assistant message, and one text outbound
audit with status `sent`. The audit has a provider message ID and no outbound
error; the synthetic conversation has escalation status `none`.

Two launcher checks stopped before webhook while validating the protected test
identity and helper execution path. They created no external messages. Only the
successful canary created live traffic.

This closes the Wazzup reconnection gate but does not establish a latency
distribution. Customer-visible `p50`, `p95`, and maximum remain unclaimed until
the post-fix Arabic scenario, escalation/cleanup scenario, and complete
delivery-aware matrix are executed.

## Completed delivery-aware matrix on 2026-07-27

The authorized six-scenario matrix completed against production code release
`292d82cdbe7a041787093779173d3e051c052ccb`. Raw recipient, channel, message,
and conversation identifiers remain only in protected VPS evidence with mode
`600`.

| Scenario | Correlated wall time | Delivery/correctness result |
| --- | ---: | --- |
| FAQ | `22.147s` | One sent text audit; truthful process/MOQ answer; no escalation |
| Product | `24.411s` | Exactly two catalog alternatives; sent text plus two referenced media audits |
| Compare | `37.775s` | Exactly two catalog chairs; sent text plus two referenced media audits |
| Order | `8.703s` | Quantity `2` retained; no quotation created; one sent text audit |
| Arabic | `21.051s` | Arabic response; Treejar prices and current Zoho stock confirmed; one sent text audit |
| Escalation | `7.657s` | One sent text audit; exactly one pending row created and then exactly resolved |

All customer-visible text and media audits have provider message IDs, status
`sent`, and no error details. Four companion caption rows are also `sent` and
error-free; they have no separate provider ID because each caption belongs to
its media send. Exact escalation cleanup changed only the synthetic row and
left no pending synthetic escalation.

The summary uses the same linear-interpolation percentile calculation as
`src.services.chat_latency`:

- `p50 = 21.599s`;
- `p95 = 34.434s`;
- maximum `= 37.775s`.

The maximum meets the `45s` ceiling. The p50 and p95 targets do not. This is an
explicit external-model blocker rather than an unqualified latency success.
In the slow product trace, `model_tools` accounted for `30.803s` of `37.462s`
total, while outbound text work was `0.231s`. A later Arabic trace recorded
`13.387s` in `model_tools` out of `15.057s` total processing. Local delivery,
persistence, and queue changes cannot safely claim the remaining reduction.

Bead `tj-0j7o` tracks a separate model/provider benchmark under the same
catalog, Zoho stock, order/quote, Arabic, escalation, and duplicate-cleanup
contract. A production model switch remains a separate release decision.
