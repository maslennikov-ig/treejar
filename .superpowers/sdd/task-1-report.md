# Task 1 report — acceptance contracts, traceability, and scenario set

## Outcome

Task 1 is implemented locally. The immutable scope contains 30 stable
criteria; the traceability manifest maps each criterion to exact versioned
sources, precedence, observable oracle, freshness identity, owner, scenarios
or evidence blocks, and 103 unique accepted regression IDs.

Execution boundary:
`scripts/e2e_acceptance/manifest.py` loads local contracts, checks the scope
anchor against its first Git blob, verifies source content digests (including
only the named Beads records), validates reciprocal criterion ownership, and
rejects preflight drift before any future live step.

## Commits

- `b77cc34` — immutable scope snapshot and initial stage manifest only.
- Final Task 1 commit — the commit containing this report; its exact hash is
  returned in the completion event.

## TDD evidence

RED:

- Initial focused Pytest collected zero tests because
  `scripts.e2e_acceptance` did not exist (`ModuleNotFoundError`).
- Source-provenance test failed when the manifest used the whole Beads file
  digest instead of the canonical digest of only named regression records.
- Reciprocal ownership test failed because a trace entry could name a scenario
  that did not name the criterion back.
- Dependency-transition and unresolved-approval tests failed until the
  validator distinguished an unresolved hard gate from a closed but
  freshness-required gate and rejected approved placeholder identities.

GREEN:

- `uv run python -m pytest tests/test_e2e_acceptance_manifests.py -q --tb=short`
  — 19 passed.
- Focused Ruff and format — passed.
- Focused strict Mypy with `--explicit-package-bases` — passed.
- Stage sizing, artifact validation, and `git diff --check` — passed.

## Contract decisions

- Outcomes are exactly `PASS|FAIL|BLOCKED|EXCLUDED_BY_CLIENT`.
- Evidence modes are independently
  `fresh|reused_exact|external_gate`.
- The draft authorization has zero quotas, no permissions, placeholder
  release/target values, and an expired window. Approved preflight additionally
  requires exact 40-character Git identities and exact equality for runtime,
  targets, executor/source, quotas, permissions, callbacks, test identities,
  cleanup method, and readbacks.
- Original `<10s`, `99%`, `100+`, daily backup/30-day retention, CRM stages,
  personalized price/order total, catalog coverage, and top-three offer
  obligations remain explicit hard criteria.

## Residual risk and environment validation

`tj-r1f3` remains `in_progress`; grounding cannot contribute PASS until a fresh
deployed release and passing provider smoke are proven. After closure, the
versioned trace manifest must update the canonical named-Beads digest, change
the dependency disposition to `dependency_closed_freshness_required`, and
remove the open risk; closure alone still cannot produce PASS. Referral rules,
payment-reminder policy, personalized pricing inputs, CRM stage mapping,
availability window, load authorization, backup/restore access, and operator
identity remain explicit non-passing external gates.

Only local schema, provenance, and drift behavior was validated. Live runtime,
provider, model, Wazzup, Zoho, CRM, quotation/order, load, backup/restore,
security environment, and report evidence still require their separately
authorized integration boundaries.
