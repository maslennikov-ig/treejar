# Stage tj-gh19: GitHub #40 Quotation Context Hardening

Updated: 2026-05-19
Status: delivered, deployed, live E2E verified, GitHub #40 closed
Branch: `codex/tj-gh19-quote-context-hardening`
Base: `origin/main@f268e17ea0cf`
Final main release: `b05422e1fb6647ffda7a10c337eef9c7c922273d`
Final deploy run: `26094670599`
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
- During deployed E2E, fixed one additional edge case where an exact product
  reference without quantities (`SKYLAND NOVO 2400 Meeting Table and CH 616`)
  could resume after name-gate into a generic LLM preference line. The final
  route now deterministically asks for item quantities and does not treat
  model number `2400` as a quantity.

## Documentation

No dependency documentation lookup was needed for implementation. This stage
changes deterministic repo-local routing and parser logic, not current
framework/API behavior.

## Verification

- RED tests were run before implementation for the new #40 cases and failed on
  the expected symptoms: `NOVO 2400` became quantity, terse details reset to the
  generic opener, and pending quote context was not preserved.
- Initial local implementation: `OPENROUTER_API_KEY=dummy uv run pytest tests/test_llm_engine.py tests/test_verified_answers.py -v --tb=short` -> `212 passed`.
- Final hotfix verification: `OPENROUTER_API_KEY=dummy uv run pytest tests/test_llm_engine.py tests/test_verified_answers.py -v --tb=short` -> `215 passed`.
- `uv run ruff check src/ tests/` -> passed.
- `uv run ruff format --check src/ tests/` -> passed.
- `git diff --check` -> passed.
- `uv run mypy src/` -> passed.
- Initial full pytest -> `1063 passed, 19 skipped`.
- Final full pytest -> `1066 passed, 19 skipped`.
- `uv run python scripts/orchestration/validate_artifact.py .codex/stages/tj-gh19/artifacts/tj-gh19.1-2.md` -> passed.
- `scripts/orchestration/run_process_verification.sh` -> passed.
- `OPENROUTER_API_KEY=dummy scripts/orchestration/run_stage_closeout.py --stage tj-gh19` -> passed; repeated `ruff`, format-check, `mypy`, full pytest `1063 passed, 19 skipped`, and process verification.
- Final `OPENROUTER_API_KEY=dummy scripts/orchestration/run_stage_closeout.py --stage tj-gh19` -> passed; repeated `ruff`, format-check, `mypy`, full pytest `1066 passed, 19 skipped`, and process verification.
- Read-only reviewer `Mendel` found no P0/P1 issues and recommended acceptance;
  the one residual test suggestion was addressed by adding direct `6 СН 616`
  coverage.

## Delivery And E2E Evidence

- Branch was pushed, fast-forwarded into `main`, and deployed through GitHub
  Actions.
- Initial deployed release `15785943804fff52a4c55259c1eb7785e33ebe46` passed
  CI/deploy but live E2E exposed a missing pending-quote recovery path when the
  assistant had produced an item table without persisting `pending_quote_selection`.
- Hotfix release `30d8975af45668d6039bc9fd9582efe337b0f25a` recovered quote
  selection from assistant tables, then live E2E exposed the generic exact-ref
  resume edge case after name-gate.
- Final release `b05422e1fb6647ffda7a10c337eef9c7c922273d`, GitHub Actions
  run `26094670599`, is deployed; `/opt/noor/.release-sha` matches.
- Production smoke: `uv run python scripts/verify_api.py --base-url https://noor.starec.ai`
  -> `7 passed, 0 failed`.
- Final live E2E conversation `640d0cfb-0460-4033-b6f0-7de84eadcc2a`:
  `I need SKYLAND NOVO 2400 Meeting Table and CH 616` -> name gate; `Lil` ->
  `product-quantity-clarify`, with no `2400` quantity and no escalation; `one
  Skyland Operative Chair CH 616 NEW black` -> `selection-confirmation`;
  `Lil, 1 dubay` -> `quote-resume-missing-details`, with name/address stored,
  pending quote preserved, and only company-or-individual requested.
- Synthetic failed E2E conversation `1ffc309a-287c-4b9b-903b-515f54829cd2`
  was resolved in production after the final fix so no manager action remains.
- GitHub #40 was commented with release/test/E2E evidence and closed.

## Project Index

project-index: reviewed-no-change. This stage changes LLM parser/routing logic
and regression tests only; no stable entrypoints, directories, integrations, or
verification commands changed.

## Remaining Defers

- `tj-b4n` / GitHub #24 remains provider-blocked pending an official Wazzup
  typing endpoint.
- GitHub #11 remains pending Lilia's answers.
