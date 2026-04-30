---
task_id: tj-final27.4
stage_id: tj-final27
repo: treejar
branch: codex/tj-final27-4-voice-audio-acceptance
base_branch: main
base_commit: 10e128fab6958186dcfed079fa2e360129e5d43f
worktree: /home/me/code/treejar/.worktrees/codex-tj-final27-4-voice-audio-acceptance
status: returned
verification:
  - "uv run --extra dev python -m pytest -s tests/test_voxtral.py tests/test_webhook_audio.py tests/test_services_chat.py tests/test_llm_safety.py -q: failed before implementation, 8 failed, 41 passed"
  - "uv run --extra dev python -m pytest -s tests/test_voxtral.py tests/test_webhook_audio.py tests/test_services_chat.py tests/test_llm_safety.py -q: passed, 49 passed"
  - "uv run ruff check src/ tests/: passed"
  - "uv run ruff format --check src/ tests/: failed before formatting, 2 files would be reformatted"
  - "uv run ruff format src/integrations/voice/voxtral.py src/services/chat.py tests/test_voxtral.py tests/test_services_chat.py tests/test_webhook_audio.py tests/test_llm_safety.py src/llm/safety.py src/api/admin/views.py: passed, 2 files reformatted"
  - "uv run ruff format --check src/ tests/: passed"
  - "uv run mypy src/: passed"
  - "git diff --check: passed"
  - "uv run python scripts/orchestration/validate_artifact.py .codex/stages/tj-final27/artifacts/tj-final27.4.md: passed"
changed_files:
  - src/integrations/voice/voxtral.py
  - src/services/chat.py
  - src/llm/safety.py
  - src/api/admin/views.py
  - tests/test_voxtral.py
  - tests/test_webhook_audio.py
  - tests/test_services_chat.py
  - tests/test_llm_safety.py
  - docs/testing/manual-test-checklist.md
  - docs/prompts/2026-04-27-final-voice-e2e-agent.md
  - .codex/stages/tj-final27/artifacts/tj-final27.4.md
---

# Summary

Hardened voice/audio handling for `tj-final27.4` without running live media tests. The OpenRouter/OpenAI-compatible transcription path now uses the explicit non-core `voice_transcription` safety policy, per-request timeout, zero SDK retries, provider-side `max_tokens`, and OpenRouter usage inclusion.

`transcribe_audio_with_metadata()` returns transcription text plus model, token, total-token, and cost fields when the provider returns them. The webhook/chat path persists those fields on inbound voice/audio `messages` rows, alongside `audio_url` and `transcription`.

Audio-only oversized or unreadable messages now send a deterministic safe fallback and do not call the core sales LLM. Oversized audio is rejected before transcription. SQLAdmin `MessageAdmin` now exposes voice/audio URL, transcription, token, cost, and model fields in list/detail inspection.

# Docs Used

- Context7 `/openai/openai-python`: confirmed OpenAI Python client support for `base_url`, per-request `with_options(timeout=...)`, chat completion `max_tokens`, and `response.usage.total_tokens`.
- FastAPI/SQLAlchemy/API docs: not needed; no API route or SQLAlchemy persistence schema behavior changed.
- pytest docs: not needed; tests use existing repo pytest/monkeypatch/AsyncMock patterns.

# Verification

RED/GREEN:

- RED targeted suite failed before implementation: missing `PATH_VOICE_TRANSCRIPTION`, missing metadata transcriber, missing admin columns, legacy string-only chat transcription, and fallback still reaching LLM.
- GREEN targeted suite passed after implementation: `49 passed`.

Final local checks:

- `uv run --extra dev python -m pytest -s tests/test_voxtral.py tests/test_webhook_audio.py tests/test_services_chat.py tests/test_llm_safety.py -q` -> passed, `49 passed`.
- `uv run ruff check src/ tests/` -> passed.
- `uv run ruff format --check src/ tests/` -> passed after formatting two changed files.
- `uv run mypy src/` -> passed.
- `git diff --check` -> passed.
- `uv run python scripts/orchestration/validate_artifact.py .codex/stages/tj-final27/artifacts/tj-final27.4.md` -> passed.

# Risks / Follow-ups / Explicit Defers

- Live voice E2E is explicitly deferred pending approval for exact phone, channel, suffixes, EN/AR voice sample text, readback method, and stop conditions.
- No deploy, production/staging mutation, broad production suite, `scripts/verify_wazzup.py`, live voice/media/payment/referral test, or real customer number was used.
- Oversized/corrupted production audio was not sent and should not be sent as a live test; oversized/unreadable behavior is covered by local unit tests.
- The transcription path records usage/cost only when the provider returns those fields.
