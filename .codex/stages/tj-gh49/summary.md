# Stage tj-gh49: GitHub #48 Name Gate Duplicate Prompt

Updated: 2026-06-04
Status: local implementation complete; stage closeout passed; delivery pending
Branch: `codex/tj-gh49-name-gate-duplicate-fix`
Base: fresh `origin/main` at `ac78d6a3b1f17d8ecd03a38201ddd2ab54b44933`
Beads: `tj-gh49`, `tj-gh49.1` closed locally, `tj-gh49.2` open for delivery

docs-reviewed: no-change-needed - this is a narrow runtime guard and regression
test for name-gate resume; no public docs, API contract, deployment process, or
operator runbook changed.
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
- Added a narrow runtime repair guard: only after a pending name-gate request is
  consumed, if the generated response still asks for the customer name, Noor
  returns a safe continuation of the stored original request instead.

## Verification

Passed:

- `OPENROUTER_API_KEY=dummy uv run pytest tests/test_llm_engine.py::test_process_message_bare_name_resume_repairs_duplicate_name_prompt -v --tb=short`
- `OPENROUTER_API_KEY=dummy uv run pytest tests/test_llm_engine.py::test_process_message_name_only_reply_resumes_pending_name_gate_request tests/test_llm_engine.py::test_process_message_bare_name_reply_resumes_pending_name_gate_request tests/test_llm_engine.py::test_process_message_bare_name_resume_repairs_duplicate_name_prompt tests/test_llm_engine.py::test_extract_bare_name_gate_reply_accepts_only_likely_names -v --tb=short`
- `OPENROUTER_API_KEY=dummy uv run pytest tests/test_llm_engine.py -v --tb=short`
- `uv run ruff check src/llm/engine.py tests/test_llm_engine.py`
- `uv run ruff format --check src/llm/engine.py tests/test_llm_engine.py`

Full closeout passed after restoring ignored local frontend dependencies with
`npm ci --prefix frontend/admin`:

- `uv run ruff check src/ tests/`
- `uv run ruff format --check src/ tests/`
- `uv run mypy src/`
- `env DYLD_FALLBACK_LIBRARY_PATH="${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}" OPENROUTER_API_KEY=dummy uv run pytest tests/ -v --tb=short`
  -> `1225 passed, 19 skipped`
- `scripts/orchestration/run_process_verification.sh`
- `scripts/orchestration/run_stage_closeout.py --stage tj-gh49`

Remaining before GitHub closure:

- Beads `tj-gh49.2`: merge/deploy approval;
- production smoke;
- synthetic/live evidence for the #48 flow;
- comment on and close GitHub #48 only after production evidence.
