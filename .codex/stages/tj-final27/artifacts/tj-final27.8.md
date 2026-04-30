---
task_id: tj-final27.8
stage_id: tj-final27
repo: treejar
branch: codex/tj-final27-8-nonfunctional-readiness
base_branch: main
base_commit: 10e128fab6958186dcfed079fa2e360129e5d43f
worktree: /home/me/code/treejar/.worktrees/codex-tj-final27-8-nonfunctional-readiness
status: returned
verification:
  - Context7 FastAPI docs for APIRouter dependencies and HTTPException guards: passed
  - Context7 pytest docs for focused tests, monkeypatch, pytest.raises: passed
  - RED uv run --extra dev python -m pytest -s tests/test_security_extended.py tests/test_scripts_verify_api.py tests/test_scripts_load_test_conversations.py -q: failed as expected
  - RED uv run --extra dev python -m pytest -s tests/test_infra_contract.py::test_final_readiness_nonfunctional_doc_records_required_posture -q: failed as expected
  - uv run python scripts/load_test_conversations.py --conversations 50 --messages-per-conversation 3 --concurrency 10 --processing-delay-ms 25 --ack-budget-ms 50 --p95-budget-ms 1000: passed
  - production public GET health/auth check via httpx: passed
  - tracked-secret scan with git ls-files and rg private-key/API-token patterns: passed
  - uv run --extra dev python -m pytest -s tests/test_security.py tests/test_security_extended.py tests/test_infra_contract.py tests/test_scripts_verify_api.py tests/test_scripts_load_test_conversations.py -q: passed
  - uv run ruff check changed files: passed
  - uv run ruff format --check changed files: passed
  - uv run ruff check src/ tests/ scripts/: failed outside write zone
  - uv run ruff format --check src/ tests/ scripts/: failed outside write zone
  - integration follow-up uv run ruff check src/ tests/ scripts/: passed after orchestrator fixed existing scripts/orchestration lint blockers
  - integration follow-up uv run ruff format --check src/ tests/ scripts/: passed after orchestrator formatted existing scripts/orchestration files
  - uv run mypy src/: passed
  - git diff --check: passed
changed_files:
  - .codex/stages/tj-final27/artifacts/tj-final27.8.md
  - docs/client/final-readiness-nonfunctional.md
  - scripts/load_test_conversations.py
  - scripts/verify_api.py
  - tests/test_infra_contract.py
  - tests/test_scripts_load_test_conversations.py
  - tests/test_scripts_verify_api.py
  - tests/test_security_extended.py
---

# Summary

Returned nonfunctional readiness evidence for `tj-final27.8` without backend
admin implementation changes and without production mutation.

Implemented a bounded local/mock conversation load harness in
`scripts/load_test_conversations.py`. The default and measured run are capped
to local synthetic batches only; they do not call HTTP, Wazzup, Zoho,
OpenRouter, customer conversations, or production queues. The measured run
processed 50 mocked conversations / 150 messages at concurrency 10 with
0 failures, p95 ack 0.177 ms, p95 total 125.917 ms, and max in-flight 10.

Extended `scripts/verify_api.py` with admin/dashboard auth-guard checks that do
not require secrets. The script still preserves local behavior where
conversation readiness can run without a configured API key.

Added fresh security tests for:

- `/dashboard/` and `/api/v1/admin/*` rejecting `X-API-Key` without SQLAdmin
  session;
- `/api/v1/products/sync` and `/api/v1/admin/products/sync` rejecting API-key
  bypass and not enqueueing sync work;
- `/api/v1/conversations/` requiring the internal API key in production mode;
- Wazzup IP allowlist rejecting disallowed origins before Redis/ARQ queueing.

Created `docs/client/final-readiness-nonfunctional.md` with load, security,
backup/restore, rollback, monitoring, no tracked secrets, and SLA-limit
evidence for client acceptance.

Docs used:

- Context7 `/fastapi/fastapi`: APIRouter router-level dependencies apply to
  all path operations, and dependencies can raise `HTTPException` before the
  endpoint body runs.
- Context7 `/pytest-dev/pytest`: focused tests, monkeypatch fixtures, and
  `pytest.raises` are canonical pytest patterns.
- SQLAlchemy behavior was not touched.

# Verification

RED/GREEN:

- Initial RED for the new verify/load tests failed as expected because
  `check_admin_auth_guards` and `scripts/load_test_conversations.py` did not
  exist.
- Initial RED for the doc contract failed as expected because
  `docs/client/final-readiness-nonfunctional.md` did not exist.
- GREEN targeted suite:
  `uv run --extra dev python -m pytest -s tests/test_security.py tests/test_security_extended.py tests/test_infra_contract.py tests/test_scripts_verify_api.py tests/test_scripts_load_test_conversations.py -q`
  -> `16 passed`.

Load evidence:

- `uv run python scripts/load_test_conversations.py --conversations 50 --messages-per-conversation 3 --concurrency 10 --processing-delay-ms 25 --ack-budget-ms 50 --p95-budget-ms 1000`
  -> passed with `failed=0`, `max_in_flight=10`, `p95_ack_ms=0.177`,
  `p95_total_ms=125.917`.

Read-only production evidence, public GET only:

- `/api/v1/health` -> `200`, `status=ok`, Redis `status=ok`,
  Redis latency `0.53 ms`.
- `/dashboard/` -> `401`, `Admin authentication required`.
- `/admin/` -> `302` to `/admin/login`.
- `/api/v1/admin/metrics/` -> `401`, `Admin authentication required`.
- `/api/v1/conversations/` -> `403`, `Invalid or missing API key`.

Tracked-secret evidence:

- `git ls-files -z | xargs -0 rg -n --pcre2 '(sk-[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9-]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN (RSA|OPENSSH|EC|DSA)? ?PRIVATE KEY-----)' || true`
  produced no matches.
- `git ls-files | rg '(^|/)\.env(\.|$)|(^|/)\.env$' || true`
  listed only `.env.example` and `frontend/landing/.env.example`.

Quality gates:

- `uv run ruff check scripts/load_test_conversations.py scripts/verify_api.py tests/test_security_extended.py tests/test_infra_contract.py tests/test_scripts_verify_api.py tests/test_scripts_load_test_conversations.py`
  -> passed.
- `uv run ruff format --check scripts/load_test_conversations.py scripts/verify_api.py tests/test_security_extended.py tests/test_infra_contract.py tests/test_scripts_verify_api.py tests/test_scripts_load_test_conversations.py`
  -> passed.
- `uv run mypy src/` -> passed.
- `git diff --check` -> passed.

Repo-wide requested gates:

- Worker run identified an outside-zone blocker in existing
  `scripts/orchestration/*` lint/format state.
- Integration follow-up fixed the bootstrap lint/format blockers without
  changing the `runtime_support.ensure_tomllib_runtime()` ordering semantics.
- `uv run ruff check src/ tests/ scripts/` -> passed.
- `uv run ruff format --check src/ tests/ scripts/` -> passed.

# Risks / Follow-ups / Explicit Defers

- The worker-level repo-wide ruff blockers were existing orchestration files
  outside the worker write zone; the orchestrator resolved them during
  integration.
- Load evidence is local and mocked. It proves a bounded concurrency envelope,
  not live Wazzup/OpenRouter/Zoho/PostgreSQL end-to-end latency.
- No production release SHA or Alembic head was fetched in this pass because
  those are not exposed through public health/auth endpoints, and SSH/database
  access was out of scope.
- Backup posture is documented from deploy scripts and existing operator docs;
  no Supabase backup setting readback or restore drill was run.
- Client decision remains needed: accept this bounded nonfunctional evidence
  for final readiness, or approve a separate controlled production load and
  restore drill with explicit traffic limits, timing window, and rollback owner.
