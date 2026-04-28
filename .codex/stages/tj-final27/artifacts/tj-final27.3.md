---
task_id: tj-final27.3
stage_id: tj-final27
repo: treejar
branch: codex/tj-final27-payment-reminders
base_branch: codex/tj-final27-crm-completeness
base_commit: 8b7f9f8ff9b1d8d8609e9d2fd13f0cbfd0e72553
worktree: /home/me/code/treejar/.worktrees/codex-tj-final27-payment-reminders
status: returned
verification:
  - "uv run --extra dev python -m pytest -s tests/test_services_followup.py::test_run_payment_reminders_scans_past_first_page_non_candidates tests/test_services_followup_details.py::test_payment_reminder_closes_locally_created_wazzup_provider -q: failed before review fixes, 2 failed"
  - "uv run --extra dev python -m pytest -s tests/test_services_followup.py::test_run_payment_reminders_scans_past_first_page_non_candidates tests/test_services_followup_details.py::test_payment_reminder_closes_locally_created_wazzup_provider -q: passed after review fixes, 2 passed"
  - "uv run --extra dev python -m pytest -s tests/test_services_followup.py tests/test_services_followup_details.py tests/test_messaging_wazzup.py tests/test_api_admin.py -q: passed, 54 passed, 3 skipped"
  - "uv run ruff check src/ tests/: passed"
  - "uv run ruff format --check src/ tests/: passed"
  - "uv run mypy src/: passed"
  - "git diff --check: passed"
  - "uv run python scripts/orchestration/validate_artifact.py .codex/stages/tj-final27/artifacts/tj-final27.3.md: passed"
changed_files:
  - docs/admin-guide.md
  - src/api/v1/admin.py
  - src/services/followup.py
  - src/services/outbound_audit.py
  - tests/test_api_admin.py
  - tests/test_services_followup.py
  - tests/test_services_followup_details.py
  - .codex/stages/tj-final27/artifacts/tj-final27.3.md
---

# Summary

Implemented an acceptance-safe payment reminder flow around the existing follow-up worker. Default behavior is zero sends: `payment_reminder_controls.mode` defaults to `disabled`, and the old inactive-conversation LLM follow-up path is gated behind `legacy_automatic_followup_enabled=false`.

# Business defaults / client decisions

Client-specific reminder policy and Wazzup template IDs are still undecided. The default config therefore does not send reminders, does not generate reminder copy with the LLM, and blocks any >24h WhatsApp reminder unless `template_name` is explicitly configured.

Configured modes are `disabled`, `manual`, and `scheduled`. Scheduled cron sends only in `scheduled` mode; `manual` mode is reserved for explicit manual invocation.

Context7 docs-first check used current FastAPI examples for typed GET/PUT endpoints with Pydantic request/response models before adding the admin controls API.

# Changed files

- `src/services/followup.py`: added SystemConfig-backed `payment_reminder_controls`, candidate selection, stop conditions, 24h WhatsApp policy, deterministic `payment_reminder:{conversation_id}:{order_key}:{window}` crmMessageId, metadata duplicate state, and legacy follow-up gating.
- `src/services/outbound_audit.py`: added audited Wazzup template send helper with duplicate suppression by crmMessageId.
- `src/api/v1/admin.py`: added authenticated GET/PUT/PATCH endpoints for payment reminder controls.
- `docs/admin-guide.md`: documented disabled defaults, 24h template requirement, and old LLM follow-up opt-in.
- Tests: covered disabled/default zero-send behavior, active approved candidates, exclusion rules, template/no-template paths, duplicate state, within-24h configured text, and admin config validation.

# Review fixes

- Fixed P1 candidate selection: scheduled reminders now scan active conversations in deterministic `updated_at, id` order and filter candidate policy while paging until enough eligible approved orders are found or the active set is exhausted. This prevents eligible orders later in the table from being skipped behind non-order active conversations.
- Fixed P2 provider lifetime: `_process_payment_reminder_for_conversation()` now closes a locally created `WazzupProvider` in `finally`; injected providers remain caller-owned and are not closed.

# Behavior before/after

Before: `run_automatic_followups()` scanned inactive conversations at 24/72/168h and generated free-form LLM follow-up text, then sent it via Wazzup text messages.

After: `run_automatic_followups()` first evaluates disabled-by-default payment reminder controls and sends nothing unless explicitly configured. Outside the 24h customer-service window it can only use Wazzup templates. The old generic inactive LLM follow-up flow remains available only behind `legacy_automatic_followup_enabled`. Scheduled reminder candidate selection is deterministic and cannot miss an eligible order just because the first active batch contains non-candidates.

# Verification

Tests/verification:

Completed:

- Review RED: `uv run --extra dev python -m pytest -s tests/test_services_followup.py::test_run_payment_reminders_scans_past_first_page_non_candidates tests/test_services_followup_details.py::test_payment_reminder_closes_locally_created_wazzup_provider -q` -> failed before review fixes, `2 failed`.
- Review fix spot check: `uv run --extra dev python -m pytest -s tests/test_services_followup.py::test_run_payment_reminders_scans_past_first_page_non_candidates tests/test_services_followup_details.py::test_payment_reminder_closes_locally_created_wazzup_provider -q` -> passed, `2 passed`.
- `uv run --extra dev python -m pytest -s tests/test_services_followup.py tests/test_services_followup_details.py tests/test_messaging_wazzup.py tests/test_api_admin.py -q` -> passed, `54 passed, 3 skipped`.
- `uv run ruff check src/ tests/` -> passed.
- `uv run ruff format --check src/ tests/` -> passed.
- `uv run mypy src/` -> passed.

- `git diff --check` -> passed.
- `uv run python scripts/orchestration/validate_artifact.py .codex/stages/tj-final27/artifacts/tj-final27.3.md` -> passed after aligning headings with the repo artifact template.

# Risks / Follow-ups

Risks / explicit defers:

- No live Wazzup template was sent and no template ID/name was guessed.
- Client must still provide exact timing, tone/copy, stop-condition policy, and approved Wazzup template name/id before enabling scheduled sends.
- No dashboard UI controls were added; the authenticated admin API and SQLAdmin SystemConfig are available for configuration.

# Whether tj-final27.3 is ready for review

`tj-final27.3` is ready for local review.
