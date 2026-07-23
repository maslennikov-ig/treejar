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
| Legacy: summary before send | `60.671ms` |
| Current: summary after send | `30.481ms` |
| Measured reduction | `30.191ms` |

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
