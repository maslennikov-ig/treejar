# Stage tj-gh49: GitHub #48 Name Gate Duplicate Prompt

Updated: 2026-06-04
Status: delivered, production E2E verified, GitHub #48 closed
Branch: `codex/tj-gh49-name-gate-duplicate-fix` -> `main`
Base: fresh `origin/main` at `ac78d6a3b1f17d8ecd03a38201ddd2ab54b44933`
Beads: `tj-gh49`, `tj-gh49.1`, `tj-gh49.2`, and `tj-gh49.3` closed

docs-reviewed: updated - project index now names `src/llm/closed_question_guard.py`
as the shared closed-question repair module.
graph-reviewed: no-change-needed - Graphify is not configured; no
`graphify-out/GRAPH_REPORT.md` or `[knowledge_graph]` configuration exists.

## Goal

Fix GitHub #48 where Noor asks for the customer name, the customer replies with a
bare name such as `Lili`, and the next bot reply asks for the name again instead
of continuing the original workstation/storage/assembly request.

## Implementation

- Added a regression test for the exact #48 flow where the model returns a
  duplicate name question after the name slot was already captured.
- Strengthened the name-gate resume directive with the actual captured customer
  name and an explicit "do not ask for their name again" instruction.
- Replaced the narrow workstation/storage/assembly fallback with
  `src/llm/closed_question_guard.py`, a shared closed-question guard for
  already-known state-backed slots: customer name, company-or-individual status,
  and specific delivery address.
- Scoped the guard to standalone slot questions so it does not replace
  substantive product/quote confirmations that merely mention quote fields.
- Added coverage for the related case where the customer name is already known
  from prior context and for already-known quote details.

## Verification

Passed:

- `OPENROUTER_API_KEY=dummy uv run pytest tests/test_llm_engine.py::test_process_message_bare_name_resume_repairs_duplicate_name_prompt_generically -v --tb=short`
- `OPENROUTER_API_KEY=dummy uv run pytest tests/test_llm_engine.py::test_process_message_name_only_reply_resumes_pending_name_gate_request tests/test_llm_engine.py::test_process_message_bare_name_reply_resumes_pending_name_gate_request tests/test_llm_engine.py::test_process_message_bare_name_resume_repairs_duplicate_name_prompt_generically tests/test_llm_engine.py::test_process_message_repairs_name_question_whenever_name_is_known tests/test_llm_engine.py::test_extract_bare_name_gate_reply_accepts_only_likely_names -v --tb=short`
- `OPENROUTER_API_KEY=dummy uv run pytest tests/test_llm_engine.py -v --tb=short`
- `uv run ruff check src/llm/engine.py tests/test_llm_engine.py`
- `uv run ruff format --check src/llm/engine.py tests/test_llm_engine.py`
- `uv run ruff check src/ tests/`
- `uv run ruff format --check src/ tests/`
- `uv run mypy src/`
- `OPENROUTER_API_KEY=dummy uv run pytest tests/test_closed_question_guard.py tests/test_llm_engine.py -v --tb=short`
  -> `242 passed`
- `env DYLD_FALLBACK_LIBRARY_PATH="${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}" OPENROUTER_API_KEY=dummy uv run pytest tests/ -v --tb=short`
  -> `1233 passed, 19 skipped`

- `scripts/orchestration/run_process_verification.sh`
- `scripts/orchestration/run_stage_closeout.py --stage tj-gh49`

Local implementation closeout passed. Remaining work is external delivery and
production evidence under `tj-gh49.2`.

## Delivery

Delivered:

- Fast-forwarded `main` to
  `5bd91b9013cedcc7d3101f7a6c64d2c71b35ab7f`.
- Pushed `main` to GitHub.
- GitHub Actions deploy run `26942597892` passed.
- `/opt/noor/.release-sha` on the server matches
  `5bd91b9013cedcc7d3101f7a6c64d2c71b35ab7f`.
- Production smoke passed:
  `uv run python scripts/verify_api.py --base-url https://noor.starec.ai`
  -> `8 passed, 0 failed`.

Production E2E:

- Synthetic chat id:
  `+79262810921-tjgh49-20260604092424`.
- Conversation id: `25e10461-0121-4bc2-b259-df637d0ac64a`.
- Flow: customer asks for 4-person workstation, storage cabinets, and assembly;
  Noor asks for name; customer replies `Lili`; Noor stores `customer_name=Lili`
  and answers the original workstation/storage/assembly request.
- Result: no repeated name question, no generic opener, no pending escalation,
  `escalation_status=none`.

GitHub #48 was commented with this evidence and closed.
