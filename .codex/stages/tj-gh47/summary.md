# Stage tj-gh47 Summary

Scope: fix GitHub #47, where Noor asked a product preference question
about LUMA/private vs NOVO/open workspaces, then escalated after the
customer answered `I prefer more open for team`.

Current state:
- Branch: `codex/tj-gh47-preference-context` from `origin/main`
  `23f504bc9f13781f93ed637a61075c1347a8497d`.
- Beads task: `tj-gh47`, external ref `gh-47`, status `in_progress`.
- GitHub #42/#43/#45/#46 were closed with prior `tj-m7wz` production
  evidence; GitHub #47 remains open until delivery and production evidence.

Implementation:
- Added a context-aware product preference answer route in
  `src/llm/engine.py`.
- If the last assistant message asked a product preference question and the
  customer gives a direct preference answer, the message now runs through the
  normal `full` product path with explicit runtime directives.
- The route has blockers for explicit human requests, complaints, refunds,
  discounts, payment terms, credit, warranty, and similar high-risk terms, so
  true escalation/commercial policy paths remain available.
- Added a low-level verified-policy guard in `src/llm/verified_answers.py` so
  short benign preference statements do not become manager handoff without
  context.

Verification:
- RED confirmed:
  `tests/test_llm_engine.py::test_process_message_product_preference_answer_continues_without_manager_handoff`
  initially failed with `mock-model|verified-policy`.
- RED confirmed:
  `tests/test_verified_answers.py::test_policy_treats_preference_statement_as_clarify_without_handoff`
  initially failed with `policy_action == handoff`.
- Targeted:
  `OPENROUTER_API_KEY=dummy uv run --extra dev pytest tests/test_llm_engine.py tests/test_verified_answers.py -v --tb=short`
  passed, 259 passed.
- Lint:
  `uv run ruff check src/ tests/` passed.
- Format:
  `uv run ruff format --check src/ tests/` passed after formatting the
  changed test file.
- Type check:
  `uv run mypy src/` passed.
- Full:
  `env DYLD_FALLBACK_LIBRARY_PATH="${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}" OPENROUTER_API_KEY=dummy uv run pytest tests/ -v --tb=short`
  passed, 1184 passed, 19 skipped.

Environment note:
- The first full pytest run failed only because fresh local frontend admin
  dependencies were missing (`esbuild`). `npm ci` in `frontend/admin` restored
  local test dependencies; npm warned that local Node `24.16.0` is outside the
  package's declared `>=22.12.0 <23` engine range, but the full test run passed.

Docs review:
- docs-reviewed: no-change-needed. This is a narrow routing bugfix covered by
  regression tests and does not change public API, deployment, or operator
  procedure.
- graph-reviewed: no-change-needed. No `graphify-out/GRAPH_REPORT.md` or
  `[knowledge_graph]` configuration is present in this worktree.

Open delivery:
- Not merged, pushed, deployed, or production-E2E verified yet.
- Do not close GitHub #47 until merged/deployed and production evidence is
  available.
