# Stage tj-gh19: GitHub #40 Quotation Context Hardening

Updated: 2026-05-19
Status: local implementation verified; delivery, deploy, live E2E, and GitHub #40 closure pending
Branch: `codex/tj-gh19-quote-context-hardening`
Base: `origin/main@f268e17ea0cf`
GitHub issues: `gh-40`
Beads: `tj-gh19`, `tj-gh19.1`, `tj-gh19.2`, `tj-gh19.3`

## Scope

- `tj-gh19.1` / #40 context: when a pending quotation exists and the customer
  replies tersely with details such as `Lil, 1 dubay`, preserve the quote
  context, store usable details, and ask only for missing required fields.
- `tj-gh19.2` / #40 quantity: do not treat model numbers such as
  `SKYLAND NOVO 2400` as a quantity for a later SKU such as `CH 616`.
- `tj-gh19.3`: merge, deploy, production smoke/E2E, GitHub #40 comment and
  closure after deployed evidence.
- GitHub #11 remains excluded until Lilia answers its separate clarification
  questions.

## Parallel Decomposition Matrix

| Stream | Goal | Agent | Write zone | Verification | Decision | Reason |
| --- | --- | --- | --- | --- | --- | --- |
| A `tj-gh19.1` | Preserve quote context during terse customer-detail replies | local orchestrator | `src/llm/engine.py`, `src/llm/prompts.py`, `tests/test_llm_engine.py` | LLM engine regression tests | sequential | Shared `process_message` quote-resume path overlaps the quantity fix and would create conflicts. |
| B `tj-gh19.2` | Reject model-number quantities while keeping SKU variants green | local orchestrator | `src/llm/engine.py`, `tests/test_llm_engine.py` | purchase selection and process flow tests | sequential | Same deterministic parser and routing code as stream A. |
| C review | Read-only edge-case review of the final diff | Codex explorer, inherited model/reasoning | read-only | targeted read-only tests and diff review | parallel after green | Independent review value without write conflicts. |
| D `tj-gh19.3` | Delivery and deployed E2E | future orchestrator | delivery scripts, prod runtime, GitHub | production smoke/live E2E | pending | Requires explicit delivery/deploy/prod authorization. |

## Implemented

- Added a model-number guard so purchase selection skips numeric matches whose
  immediate model prefix is a known family/model token such as `NOVO`.
- Kept existing SKU fixes green for `CH 616`, `CH-616`, `CH616`,
  repeated spaces, and Cyrillic homoglyph `СН 616`.
- Added active quote-context terse details parsing for replies like
  `Lil, 1 dubay`, gated by both a pending quote selection and an assistant
  prompt asking for quotation details.
- Pending quote resume now stores parsed details, keeps
  `pending_quote_selection`, checks missing required details before
  `create_quotation`, and returns a targeted missing-details prompt instead of
  falling back to the generic opener.
- Added runtime prompt policy that ambiguous/terse quotation details must
  preserve quote context and ask only for missing or unclear required details.

## Documentation

No dependency documentation lookup was needed for implementation. This stage
changes deterministic repo-local routing and parser logic, not current
framework/API behavior.

## Verification

- RED tests were run before implementation for the new #40 cases and failed on
  the expected symptoms: `NOVO 2400` became quantity, terse details reset to the
  generic opener, and pending quote context was not preserved.
- `OPENROUTER_API_KEY=dummy uv run pytest tests/test_llm_engine.py tests/test_verified_answers.py -v --tb=short` -> `212 passed`.
- `uv run ruff check src/ tests/` -> passed.
- `uv run ruff format --check src/ tests/` -> passed.
- `git diff --check` -> passed.
- `uv run mypy src/` -> passed.
- `env DYLD_FALLBACK_LIBRARY_PATH="${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}" OPENROUTER_API_KEY=dummy uv run pytest tests/ -v --tb=short` -> `1063 passed, 19 skipped`.
- `uv run python scripts/orchestration/validate_artifact.py .codex/stages/tj-gh19/artifacts/tj-gh19.1-2.md` -> passed.
- `scripts/orchestration/run_process_verification.sh` -> passed.
- `OPENROUTER_API_KEY=dummy scripts/orchestration/run_stage_closeout.py --stage tj-gh19` -> passed; repeated `ruff`, format-check, `mypy`, full pytest `1063 passed, 19 skipped`, and process verification.
- Read-only reviewer `Mendel` found no P0/P1 issues and recommended acceptance;
  the one residual test suggestion was addressed by adding direct `6 СН 616`
  coverage.

## Delivery And E2E Plan

Run only after explicit merge/deploy/production authorization:

1. Merge `codex/tj-gh19-quote-context-hardening` to `main` and deploy through
   the existing GitHub Actions path.
2. Run `scripts/verify_api.py --base-url https://noor.starec.ai`.
3. Run the #40 E2E conversation on a clean synthetic/live identity:
   `I need SKYLAND NOVO 2400 Meeting Table and CH 616` must lead to quantity
   clarification, not `2400 x CH 616`; then select/clarify a specific item and
   quantity; then send `Lil, 1 dubay`; the bot must preserve quote context and
   ask only for company name or explicit individual confirmation.
4. Continue with `individual`; quotation may proceed only when item, quantity,
   name, address, and individual/company requirement are satisfied.
5. Comment and close GitHub #40 only after deployed evidence is recorded.

## Project Index

project-index: reviewed-no-change. This stage changes LLM parser/routing logic
and regression tests only; no stable entrypoints, directories, integrations, or
verification commands changed.

## Remaining Defers

- `tj-gh19.3` tracks merge/deploy/production E2E/GitHub #40 closure.
- `tj-b4n` / GitHub #24 remains provider-blocked pending an official Wazzup
  typing endpoint.
- GitHub #11 remains pending Lilia's answers.
