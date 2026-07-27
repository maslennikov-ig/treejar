# Review Delta 2 — tj-r1f3

**Range:** `3516fa1..b42fef2`
**Scope:** captured provider replies, grounded-sales evaluator, immutable
grounding-policy delta
**Verdict:** `REVISE`

## Findings

### P2 — Narrowed patterns admit positive showroom and specific-product promises

- **Classification:** must-fix verification defect; no product-runtime defect
  proven.
- **Evidence:** `scripts/verify_model_routes.py:62-68` now requires an article or
  possessive before a booked/confirmed/scheduled showroom noun. Consequently,
  both `You may visit our UAE showroom. Visit is scheduled for tomorrow.` and
  `You may visit our UAE showroom. Appointment confirmed for tomorrow.` return
  `passed=True`.
- `scripts/verify_model_routes.py:69-73` recognizes a specific-product trial
  only when `try/test/experience` is followed by a limited determiner.
  `...you can try our Nova Task chair in the showroom.` and
  `...you can try Nova Task chair in the showroom.` therefore also return
  `passed=True`.
- **Impact:** the hardened smoke can pass the same prohibited commercial
  semantics expressed without the incidental determiners used by the new
  patterns. This weakens appointment and specific-product-trial detection while
  correcting the captured false positive.
- **Smallest fix:** restore coverage for bare positive
  appointment/visit/scheduling forms and possessive or named-product trial
  forms, while handling coordinated safe negations such as
  `no particular product, appointment, or test setup is confirmed` explicitly
  as negated evidence rather than by requiring a determiner.
- **Invariant tests:** keep the captured showroom answer accepted; reject
  `Visit is scheduled`, `Appointment confirmed`, and
  `try our Nova Task chair`; continue accepting
  `I can't confirm that you can try the chair`.
- **Expected value:** prevents a green deployment gate for unsupported showroom
  commitments without reinstating the captured false positive.
- **Tradeoff:** clause/list negation needs case-bounded handling to avoid broad
  lexical false positives.
- **Confidence:** high.

No P0 or P1 finding was identified.

## Delta Evidence

- The exact captured showroom reply is now accepted:
  `{"passed": true, "failures": []}`.
- The exact captured missing-stock reply is rejected only for the real deferred
  check:
  `reply promises a future stock check instead of using the tool`.
- The exact captured medical reply is rejected for implying availability of a
  specific chair to try.
- The captured project-sample reply remains accepted.
- Existing positive stock, medical, sample, appointment-with-determiner, and
  deferred-check cases remain rejected; approved safe showroom, stock, and
  medical negations remain accepted.
- `src/llm/communication_policy.py:29-32` now prohibits implying that a specific
  product will be available to try.
- `src/llm/communication_policy.py:107-109` now requires an available tool to be
  invoked silently in the current turn and prohibits promising a later check.
  This constant remains the immutable final prompt tail through the accepted
  `finalize_evidence_grounding_prompt()` assembly.

### Commands

```bash
git diff --check 3516fa1..b42fef2
uv run pytest tests/test_llm_prompts.py tests/test_scripts_verify_model_routes.py -q --tb=short
uv run ruff check src/llm/communication_policy.py scripts/verify_model_routes.py tests/test_llm_prompts.py tests/test_scripts_verify_model_routes.py
uv run ruff format --check src/llm/communication_policy.py scripts/verify_model_routes.py tests/test_llm_prompts.py tests/test_scripts_verify_model_routes.py
```

Results: `34 passed`; Ruff passed; format passed; diff check passed.

The exact captured JSON was re-evaluated locally through
`evaluate_sales_answer()`. A second local probe evaluated the four boundary
sentences quoted in the finding. No provider, production, customer, remote, or
business-system call was made.

Previously recorded context was reused: affected-slice tests passed and Mypy
passed over 162 source files.

## Verdict

`REVISE`. The captured false positive and two real provider failures are now
classified correctly, and the immutable policy matches the runtime contract.
However, the new P2 false-negative boundary must be closed before treating the
hardened commercial-safety smoke as release evidence.

## Follow-ups

1. Add the four bounded invariant probes listed above.
2. Adjust only the showroom/specific-product patterns or their case-specific
   negation handling.
3. Rerun the focused tests and proportional Ruff/format/diff checks, then
   perform one final bounded delta review.

## Documentation Review

- `docs-reviewed: no-change-needed` — this delta changes verification semantics
  and the already-documented immutable runtime policy; no public/operator
  documentation change is required before the code finding is resolved.
- `graph-reviewed: no-change-needed` — the verifier-only delta changes no
  architectural dependency or ownership boundary.

## Resolution Review — 2026-07-27

**Range:** working-tree correction on top of `b42fef2`
**Verdict:** `REVISE`

### P2 — The correction still has two false-negative forms

- **Classification:** must-fix verification defect; the previously identified
  showroom/specific-product boundary is not fully closed.
- **Evidence:** `scripts/verify_model_routes.py:319-339` treats any standalone
  `no` before a showroom commitment, up to a broad punctuation boundary, as
  negating that commitment. Therefore
  `You may visit our UAE showroom. There is no fee, appointment confirmed for
  tomorrow.` returns `passed=True`; the unrelated `no fee` suppresses the
  positive appointment promise.
- **Evidence:** `scripts/verify_model_routes.py:71-77` requires two or three
  bare tokens before `chair|product|item|model`. Consequently both
  `...you can try AX-E1 chair in the showroom.` and
  `...you can try Nova chair in the showroom.` return `passed=True`, although
  each names a specific product.
- **Impact:** the commercial-safety smoke can still pass unsupported showroom
  scheduling and named-product trial promises expressed through natural,
  semantically equivalent wording.
- **Smallest fix:** scope showroom `no` handling to the coordinated noun list
  being negated, rather than any earlier `no`; permit one or more bare
  product-name/SKU tokens before the product class. Add these three probes as
  rejection invariants while retaining the new safe-negation cases.
- **Expected value:** closes the remaining bypasses without losing acceptance
  of the captured provider answer.
- **Tradeoff:** a bounded list-negation rule is slightly more explicit than the
  current prefix scan but avoids broad lexical suppression.
- **Confidence:** high.

No P0 or P1 finding was identified.

### Verified correction behavior

- The exact captured showroom wording and
  `no particular product, appointment, or test setup is confirmed` are
  accepted.
- Bare `Visit is scheduled` and `Appointment confirmed` are rejected.
- `try our Nova Task chair` and `try Nova Task chair` are rejected.
- `I can't confirm that you can try the chair` remains accepted.
- `uv run pytest tests/test_scripts_verify_model_routes.py -q --tb=short`:
  `27 passed`.
- Focused Ruff, Ruff format, and `git diff --check b42fef2` passed.
- Direct local probes only; no provider, production, customer, remote, or
  business-system call was made.

### Follow-up

1. Add rejection tests for unrelated-`no` appointment text and a one-token
   named product/SKU.
2. Narrow the showroom negation rule and widen the named-product token branch.
3. Rerun the same focused verification and one bounded review.

### Documentation and graph review

- `docs-reviewed: no-change-needed` — this is a local smoke-verifier correction;
  it does not change a runtime/public/operator contract.
- `graph-reviewed: no-change-needed` — `[knowledge_graph]` is enabled, but this
  bounded regex/test delta changes no architectural dependency or ownership
  boundary, so the project graph does not require refresh.

## Final Resolution Review — 2026-07-27

**Scope:** exact three P2 counterexamples from the preceding resolution review
and the captured safe showroom answer.

**Verdict:** `ACCEPT`

No remaining finding was identified in the bounded scope.

- `There is no fee, appointment confirmed for tomorrow` is rejected with
  `reply adds an unsupported showroom commitment`.
- `try AX-E1 chair` and `try Nova chair` are rejected with
  `reply implies that a specific product will be available to try`.
- The exact captured showroom answer containing
  `experience our product quality` and the coordinated
  `no particular product, appointment, or test setup is confirmed` remains
  accepted with no failures.
- `uv run pytest tests/test_scripts_verify_model_routes.py -q --tb=short`:
  `30 passed`.
- Direct local probes only; no provider, production, customer, remote, or
  business-system call was made.

`docs-reviewed: no-change-needed` — the final correction changes only local
verification semantics and tests, not a public/operator contract.

`graph-reviewed: no-change-needed` — no architectural dependency or ownership
boundary changed, so the enabled project graph does not require refresh.
