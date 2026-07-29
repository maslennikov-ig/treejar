# Noor E2E Remediation and Closeout Design

**Date:** 2026-07-29  
**Owning task:** `tj-ee5f.1` under epic `tj-ee5f`  
**Stage level:** release  
**Runtime:** `https://noor.starec.ai`

## Purpose

Remediate every unresolved defect from the 2026-07-28 live sales/tool run,
complete the real trusted production acceptance path, deploy one reviewed
release, and close the epic only after fresh production evidence.

The immutable acceptance boundary remains the existing `AC-01` through
`AC-30` snapshot with source digest
`12f0cc9c8c038f366096162dbac51e90746f38efb93b9f9feb29f1ea507cf732`.
The older “29 criteria” wording is stale; no criterion is added, renamed, or
renumbered.

## Design

### Trusted production execution (`tj-ee5f.5`)

- Implement the existing transport and collector protocols with real,
  permit-bound HTTP/SSH adapters; keep the local fake only for tests.
- Make `preflight -> execute/resume -> finalize` derive ordered turns, model and
  tool identities, duration, cost, readbacks, and side effects from protected
  production facts.
- Bind every mutation to the approved destination, permission, quota, payload
  digest, expiry, and reconciliation result.
- Fail closed on missing, reordered, caller-authored, unknown, or nonterminal
  evidence. Raw evidence remains protected outside Git; tracked projections are
  redacted and checksummed.

### Conversation routing (`tj-ee5f.6` and `tj-ee5f.7`)

- Persist a versioned pending-sales-intent envelope before the name gate. It
  retains the classified route, locale, original request, captured identity
  fields, and explicit quote signal.
- Resume the stored route after name capture instead of reclassifying a
  concatenated string.
- Route ordinary English and Arabic furniture discovery through the catalog.
  A genuine catalog no-match returns an honest bounded answer and relevant
  office alternatives; escalation is reserved for unsupported high-risk facts.

### Quote and CRM flow (`tj-ee5f.8` and `tj-ee5f.9`)

- Use explicit phases:
  `consultation -> quote_offered -> quote_requested -> collecting_details ->
  creating -> created`.
- Only explicit quote opt-in enters `quote_requested`. No-quote intent clears
  or suspends the quote frame. Objections, corrections, delivery/assembly
  questions, and CRM next-step requests take precedence over quote resume.
- Exact-SKU requests answer the requested SKU only while it is available.
  Alternatives appear only when unavailable/insufficient or explicitly asked
  for; no quote CTA follows an explicit no-quote request.
- Parse labeled customer data with delimiter-aware boundaries. Unlabeled
  digits in company/address text never become a phone number, and the full
  address is preserved.
- Build a typed Zoho contact/order payload, perform exact duplicate lookup on a
  duplicate conflict, and fail honestly on other validation errors. Idempotent
  retries must not duplicate contacts or sales orders.
- A quote passes only when SKU, quantity, unit price, total, PDF delivery, and
  terminal side-effect readbacks reconcile.

### Voice (`tj-ee5f.10`)

- Use OpenRouter's dedicated transcription endpoint; remove the transcription
  chat prompt.
- Detect audio format from validated MIME plus magic bytes. Never label unknown
  bytes as MP3.
- Add `VOICE_TRANSCRIPTION_MODEL`; retain `VOXTRAL_MODEL` as a temporary
  compatibility alias.
- Preserve provider model, generation identity, audio duration, token usage,
  cost, and request duration when returned.
- Key customer fallback idempotency by distinct inbound message identity and
  fallback type, not repeated fallback text.

## Compatibility and token budget

- No external REST/webhook contract or database schema changes.
- New Redis state is versioned and reads legacy state with safe defaults.
- Captured S01-S11 sentences exist only in regression fixtures. Production
  behavior uses typed state, catalog data, and compact configuration.
- The product system prompt has no net growth. If wording must change, replace
  an equivalent duplicated rule.
- Paid production acceptance runs only after local acceptance. Semantic
  failures rerun only affected scenarios after a fix; retries are reserved for
  transient infrastructure failures.

## Acceptance

- All focused regression cases pass, followed by one repository release gate.
- Canonical deploy and exact release/model/service readback pass.
- At least ten complete text scenarios plus provider EN/AR/voice canaries run
  against the protected test identity.
- Every text scenario scores at least `20/30`, the mean is at least `24/30`,
  and there are no functional failures, unresolved P0/P1, or zero scores on an
  applicable critical rule.
- Quote/PDF evidence and every test-only side effect reach a verified terminal
  state.
- The Russian client report preserves exact redacted Q/A, tool traces,
  failures, fixes, retests, limitations, and the final verdict.

