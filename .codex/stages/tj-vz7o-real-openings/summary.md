# Stage tj-vz7o-real-openings Summary

Updated: 2026-08-10
Status: measured, not accepted

## Boundary

Run the 20 seed-20260810 natural customer openings through Luna and evaluate
each result with GLM 5.2 in an isolated paid-call harness. Transcript-bearing
evidence stays under git-common-dir; Git receives only identifiers, integers,
digests, intervals, costs, and failure codes.

No Haiku, live traffic, production mutation, real-user message, deploy, or push
belongs to this stage.

## Result

Exactly 20/20 openings received Luna replies and 20/20 replies received GLM
evaluations. After fixing a numeric-normalization defect in the deterministic
analyzer, 2 critical failures remain across 2/20 openings. Weighted score is
11.9/30 (stratified-bootstrap 95% CI 10.2–13.7); GLM `raw_total` is 11.0/30
(95% CI 10.4–11.6); Luna first-reply latency is 2.508 s median over 20/20 (95%
CI 2.310–2.948 s). The round did not pass.

The pre-registered 20.0/30 lower-bound gate is not a valid gate for this set:
11/20 openings have only two applicable blocks and a deterministic maximum of
9.6/30. It was not changed after the result. `tj-vz7o.10.2` owns the replacement
gate before any rerun; `tj-vz7o.10.1` owns the two remaining product failures.

Two protected responses were read manually. One was a strong, safe response to
a vague request; the other greeted and discovered well but listed products too
early, conflicted on stock certainty, and left assembly unresolved. No text was
copied into Git.

## Documentation

Documentation: `docs-resolve` — external model availability and pricing are
resolved from the provider's live preflight metadata; product behavior and
acceptance rules come from repository code and the frozen local specification.

## Delivery boundary

No Haiku, live traffic, production mutation, real-user message, deploy, or push
occurred. A second paid round is not authorized by this stage.
