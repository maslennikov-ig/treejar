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

### tj-rt7w.3 — accepted

- Change: `src/llm/money.py` now owns the amount token, the existing currency
  spellings, customer-output amount recognition, and the canonical decimal
  form. Engine budgets, fact extraction, grounding, and the opening guard use
  those shared definitions.
- Behaviour evidence: no existing test was edited. An exact before/after replay
  over all twenty stored raw outputs found zero mismatches separately in all
  four modules; no output interpretation changed.
- Regression evidence: ten new direct tests cover `290 == 290.00`, comma and
  trailing-zero normalization, both existing currency/amount orders, and the
  opening guard's currency-presence contract.
- Gate: the focused money-and-consumer set passed 986 tests. Ruff and format
  passed over `src/` and `tests/`; Mypy passed over 170 source files; Pytest
  passed with 3536 tests and 19 skips; process verification is recorded in the
  child artifact.

### tj-rt7w.4 — accepted

- Change: the first-turn opening, selling-turn, closed-question, and premature
  quote-detail guards are pure functions in `src/llm/response_policy.py` with
  explicit scalar and sequence state. None closes over `process_message`.
- Direct evidence: four new unit tests construct no conversation. The existing
  acceptance harness imports the production opening, deferral, and grounding
  guard objects; no guard implementation is copied into it.
- Behaviour evidence: no existing test was edited. An exact before/after replay
  over all twenty stored raw outputs found zero mismatches for each guard and
  for the complete chain. An AST check found zero target guard closures inside
  `process_message`.
- Gate: the focused guard-and-engine set passed 909 tests. Ruff and format
  passed over `src/` and `tests/`; Mypy passed over 170 source files; Pytest
  passed with 3540 tests and 19 skips; process verification is recorded in the
  child artifact.

### tj-rt7w.5 — accepted

- Change: `render_reply()` now applies one ordered text policy to model,
  repaired-model, deterministic-replacement, and deterministic-static replies.
  Provenance is metadata only; it never selects or skips a policy step.
- Exit evidence: every transport response is constructed from a
  `RenderedReply`. A new AST regression test finds no direct `LLMResponse`
  construction inside `process_message`, so a new customer-facing exit cannot
  quietly recreate an independent chain.
- Grounding evidence: deterministic catalog routes now pass their verified
  catalog and inventory state into the same policy. The no-evidence quantity
  prompt no longer promises a future inventory check, so the universal guard
  does not leave a useful question truncated.
- Output evidence: the former full chain changed 0 of 20 stored raw outputs.
  Each of the three former short chains changed only `dialog_id=789` and
  `dialog_id=819`; root read every complete old/new reply. `789` lost the
  unsupported customer-owned-furniture service offer at grounding. With the
  owner's explicit acceptance, `819` gained a commitment to resolve its stated
  assembly deferral; grounding then left it unchanged. No other stored output
  moved.
- Gate: six focused exit/policy tests and all 819 engine tests passed. Ruff and
  format passed over `src/` and `tests/`; Mypy passed over 170 source files;
  Pytest passed with 3546 tests and 19 skips; process verification is recorded
  in the child artifact.

### tj-rt7w.6 — accepted

- Change: the public `process_message` is now a 40-line facade and
  `engine.py` is 11,849 lines. Catalog planning and materialization moved to
  `catalog_planning.py`; response transport moved to `response_runtime.py`;
  text policy remains in `response_policy.py`; quote and order routing and its
  declared static routes remain in `order_quote_routes.py`; the orchestration
  sequence is isolated in `message_processor.py`.
- Structural evidence: a new AST test enforces both settled size limits and
  rejects a second public `process_message` implementation. The existing
  deterministic-route registry still discovers every customer-facing route.
- Behaviour evidence: no existing test was edited. Re-rendering all twenty
  protected raw outputs against commit `3199b1a` changed 0 outputs. The text
  policy and guard source files are identical to that commit.
- Gate: the focused engine and route set passed 917 tests. Ruff and format
  passed over `src/` and `tests/`; Mypy passed over 173 source files; Pytest
  passed with 3547 tests and 19 skips; process verification passed.

## Explicit defer

- `tj-rt7w.7` remains open and unstarted. Its separate paired round still
  requires current authority for exactly 20 Luna and 20 GLM calls.
