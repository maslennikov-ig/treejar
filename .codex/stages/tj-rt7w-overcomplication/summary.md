# Stage tj-rt7w-overcomplication

Status: in progress
Base: `main` at `3f9a719`
Acceptance owner: root orchestrator

## Scope

Deliver `tj-rt7w.1` through `tj-rt7w.6` in dependency order. Keep
`tj-rt7w.7` open and unstarted. Preserve the six rules in the measured audit.

## Child results

### tj-rt7w.1 — accepted

- Change: a specific prompt rule now withholds unsupported customer-owned
  furniture purchase, resale, brokerage, valuation, and assessment promises.
- Prompt evidence: exactly 3 authorized Luna calls for `dialog_id=789`; 1 of 3
  still implied the unsupported service, so Rule 5 admitted one bounded
  grounding violation for the measured phrasing family.
- Output evidence: replaying the twenty stored raw outputs against the base and
  candidate chains changes only `dialog_id=789`; root review confirmed the
  candidate reply makes no unsupported service offer and solicits no intake
  details for that service.
- Gate: Ruff and format passed over `src/` and `tests/`; Mypy passed over 168
  source files; Pytest passed with 3515 tests and 19 skips; process verification
  is recorded in the child artifact.

### tj-rt7w.2 — accepted

- Change: every existing text guard now runs through one shared reply bound. A
  guard that turns meaningful text into whitespace or punctuation cannot erase
  the reply; the previous text is kept and a text-free defect is logged.
- Owner clarification: character count is not a correctness signal. The bound
  does not reject short meaningful repairs; semantic validity remains with the
  existing guard-specific checks.
- Regression evidence: eleven new tests cover all seven current guard stages,
  accept short safe repairs, accept sentence deletion, and catch the historical
  typographic-apostrophe blanking behavior against the pre-fix guard.
- Behaviour evidence: no existing test was edited. Re-rendering all twenty
  stored raw outputs with and without the new bound changed 0 outputs.
- Gate: Ruff and format passed over `src/` and `tests/`; Mypy passed over 169
  source files; Pytest passed with 3526 tests and 19 skips; process verification
  passed.

### tj-rt7w.3 — pending

### tj-rt7w.4 — pending

### tj-rt7w.5 — pending

### tj-rt7w.6 — pending

## Explicit defer

- `tj-rt7w.7` remains open and unstarted. Its separate paired round still
  requires current authority for exactly 20 Luna and 20 GLM calls.
