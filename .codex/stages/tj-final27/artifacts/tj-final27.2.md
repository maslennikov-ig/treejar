---
task_id: tj-final27.2
stage_id: tj-final27
repo: treejar
branch: codex/tj-final27-crm-completeness
base_branch: main
base_commit: c67341f3482a677a7ad71dc3969c7db018d14234
worktree: /home/me/code/treejar/.worktrees/codex-tj-final27-crm-completeness
status: returned
verification:
  - uv run --extra dev python -m pytest -s tests/test_zoho_crm.py tests/test_customer_identity.py tests/test_llm_context.py tests/test_llm_engine.py tests/test_api_crm.py tests/test_services_chat_batch.py -q: passed
  - uv run ruff check src/ tests/: passed
  - uv run ruff format --check src/ tests/: passed
  - uv run mypy src/: passed
  - git diff --check: passed
  - uv run python scripts/orchestration/validate_artifact.py .codex/stages/tj-final27/artifacts/tj-final27.2.md: passed
changed_files:
  - docs/admin-guide.md
  - src/api/v1/crm.py
  - src/integrations/crm/zoho_crm.py
  - src/llm/engine.py
  - src/schemas/crm.py
  - src/services/chat.py
  - src/services/customer_identity.py
  - tests/test_api_crm.py
  - tests/test_customer_identity.py
  - tests/test_llm_engine.py
  - tests/test_services_chat_batch.py
  - tests/test_zoho_crm.py
  - .codex/stages/tj-final27/artifacts/tj-final27.2.md
---

# Summary

Implemented CRM completeness guardrails for final acceptance:

- inbound source/UTM attribution is durably stored in `Conversation.metadata_`;
- original attribution is preserved and repeat contacts update `latest` only;
- Zoho outbound source/UTM fields are applied only through an explicit mapping helper;
- returning-customer CRM context is bounded to name, segment, one recent status, and returning flag;
- existing rejected-quotation order-status behavior remains covered: rejected quotations are not treated as active orders.

No migration was added because the existing conversation JSON metadata field is sufficient.

# Business defaults / client decisions

- No confirmed Zoho UTM/source custom-field mapping was found in the checked docs/config paths.
- Default attribution policy: preserve `source_attribution.original`, update `source_attribution.latest` on repeat contact.
- Default Zoho mapping policy: no invented custom fields. `apply_zoho_attribution_mapping()` is a no-op unless explicit `field_mapping` is provided.
- Context7 facts used:
  - SQLAlchemy JSON in-place mutation should not be relied on without mutable tracking; this change assigns a fresh metadata dict back to the ORM attribute.
  - FastAPI/Pydantic optional dict fields are safe as model fields with `None` defaults for request schemas.

# Changed files

- `src/services/customer_identity.py`: source/UTM extraction and metadata persistence; bounded returning-customer context helpers.
- `src/services/chat.py`: Wazzup batch path stores inbound attribution on the conversation.
- `src/integrations/crm/zoho_crm.py`: explicit-only Zoho attribution mapping helper.
- `src/api/v1/crm.py`, `src/schemas/crm.py`: optional attribution input accepted by local CRM API without guessed outbound fields.
- `src/llm/engine.py`: LLM prompt uses bounded CRM context; LLM deal/contact payloads pass through the same mapping guardrail.
- `docs/admin-guide.md`: documents attribution defaults and client-decision defer.
- Tests updated in `tests/test_zoho_crm.py`, `tests/test_customer_identity.py`, `tests/test_llm_engine.py`, `tests/test_api_crm.py`, `tests/test_services_chat_batch.py`.

# Behavior before/after

Before:

- CRM context injection included whatever keys were present in `crm_context`.
- Inbound source/UTM data had no durable local preservation policy.
- Zoho source/UTM mapping behavior was not explicit.

After:

- Wazzup inbound attribution is saved under `metadata_["source_attribution"]`.
- Original source/UTM is not silently overwritten; latest attribution is stored separately.
- Zoho payloads do not receive guessed UTM/source custom fields.
- Returning-customer context is compact and does not include full transcripts.

# Verification

- `uv run --extra dev python -m pytest -s tests/test_zoho_crm.py tests/test_customer_identity.py tests/test_llm_context.py tests/test_llm_engine.py tests/test_api_crm.py -q` -> passed, 87 tests.
- `uv run --extra dev python -m pytest -s tests/test_zoho_crm.py tests/test_customer_identity.py tests/test_llm_context.py tests/test_llm_engine.py tests/test_api_crm.py tests/test_services_chat_batch.py -q` -> passed, 93 tests.
- `uv run ruff check src/ tests/` -> passed.
- `uv run ruff format --check src/ tests/` -> passed.
- `uv run mypy src/` -> passed, no issues in 124 source files.
- `git diff --check` -> passed.
- `uv run python scripts/orchestration/validate_artifact.py .codex/stages/tj-final27/artifacts/tj-final27.2.md` -> passed.

# Risks / Follow-ups / Explicit Defers

- Zoho outbound UTM/source custom-field mapping is deferred until the client confirms exact Zoho API field names and update policy.
- The implementation stores attribution locally in metadata, not in dedicated columns, because existing durable metadata is sufficient for this acceptance slice.
- No production, staging, deploy, push, broad production E2E, Wazzup verification script, scheduled AI Quality Controls, or media/voice live tests were run.

# Any client decisions still pending

- Confirm Zoho CRM field API names for source/channel/UTM.
- Confirm whether repeated contacts should ever overwrite original attribution, and under which explicit business rule.
