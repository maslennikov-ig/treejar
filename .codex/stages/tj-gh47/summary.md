# Stage tj-gh47 Summary

Scope: fix GitHub #47, where Noor asked a product preference question
about LUMA/private vs NOVO/open workspaces, then escalated after the
customer answered `I prefer more open for team`.

Current state:
- Branch `codex/tj-gh47-preference-context` was merged into `main`.
- Runtime commit: `70500e32e6206462b426b65dd8d7afc8e5ccda72`.
- GitHub Actions run `26771029593` passed `changes`, `lint`, `test`,
  `type-check`, and `deploy`; `/opt/noor/.release-sha` and
  `/opt/noor/.release-run-id` match that runtime.
- Beads task: `tj-gh47`, external ref `gh-47`, closed.
- GitHub #47 was commented with release/E2E evidence and closed.
- GitHub #42/#43/#45/#46 were closed with prior `tj-m7wz` production evidence.

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
- Delivery:
  branch pushed, fast-forward merged into `main`, and pushed to `origin/main`.
- CI/deploy:
  GitHub Actions run `26771029593` succeeded, including deploy.
- Runtime readback:
  `/opt/noor/.release-sha=70500e32e6206462b426b65dd8d7afc8e5ccda72`,
  `/opt/noor/.release-run-id=26771029593`.
- Production smoke:
  `uv run python scripts/verify_api.py --base-url https://noor.starec.ai`
  passed, 8 passed / 0 failed.
- Production E2E:
  seeded synthetic conversation
  `6e437d6d-e1b9-46e0-ad58-cfe7fe9e85ee` on
  `+79262810921#tj-gh47-pref-20260601173808` with the prior LUMA/NOVO
  preference question, then sent `I prefer more open for team` via the normal
  Wazzup webhook. Production replied with NOVO/open-team product options,
  model `z-ai/glm-5`, `escalation_status=none`, pending escalations `0`, no
  manager-handoff wording, and the synthetic conversation was closed after
  evidence capture.

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
- none.
