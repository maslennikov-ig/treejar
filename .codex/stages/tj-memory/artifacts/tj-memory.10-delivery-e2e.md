---
schema_version: orchestration-artifact/v1
artifact_type: delivery-e2e
task_id: tj-memory.10
stage_id: tj-memory
agent_type: n/a
subagent_model: n/a
reasoning_effort: n/a
model_reasoning_rationale: local sequential delivery/E2E; no subagent used
repo: treejar
branch: main
base_branch: main
base_commit: cf3185f8ca9901e53fca1b938e7c39c49d637e10
worktree: /home/me/code/treejar
write_zone:
  - src/core/config.py
  - src/llm/pii.py
  - src/llm/context.py
  - src/llm/engine.py
  - tests/test_llm_pii.py
  - tests/test_llm_context.py
  - tests/test_dialogue_config.py
  - tests/test_llm_engine.py
  - docs/specs/customer-facts-layer.md
  - .env.example
  - .codex/stages/tj-memory
  - .codex/handoff.md
success_criteria:
  - PII masking disabled by default and remains opt-in
  - phones and emails remain extractable in runtime context
  - production deploy succeeds
  - production E2E proves no PII placeholders in customer details
  - name-gate resumes stored SKU request after receiving name plus details
selected_docs:
  - no dependency documentation lookup needed; delivery/E2E used repo scripts and runtime state
selected_skills:
  - /home/me/.agents/skills/orchestrator-stage/SKILL.md
  - /mnt/c/Users/masle/.codex/superpowers/skills/verification-before-completion/SKILL.md
  - /mnt/c/Users/masle/.codex/superpowers/skills/finishing-a-development-branch/SKILL.md
  - /home/me/.agents/skills/orchestration-closeout/SKILL.md
selected_agents:
  - none - local sequential delivery and production test resource
catalog_candidates:
  - none - installed repo orchestration assets fit
parallel_group: delivery
depends_on_streams:
  - tj-memory.9
parallel_decision: sequential
status: accepted
delivery_method: merge
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: synthetic E2E conversations were closed/resolved after evidence capture; no delegated worktree was created
risk_level: medium
docs_impact: behavior,ops-deploy
docs_reviewed: updated
docs_review_notes: stage summary and handoff updated with deployment and E2E evidence
verification:
  - "OPENROUTER_API_KEY=dummy uv run pytest tests/test_llm_engine.py::test_process_message_first_turn_with_name_contacts_and_sku_skips_name_gate tests/test_llm_engine.py::test_process_message_name_gate_resume_with_contacts_and_sku_stays_product_path -v --tb=short": passed
  - "OPENROUTER_API_KEY=dummy uv run pytest tests/test_llm_engine.py::test_process_message_name_gate_resume_accepts_name_plus_customer_type -v --tb=short": passed
  - "OPENROUTER_API_KEY=dummy uv run pytest tests/test_llm_engine.py -k 'name_gate or ch616_spaced_sku_with_details or first_turn_with_name_contacts or resume_with_contacts' -v --tb=short": passed
  - "OPENROUTER_API_KEY=dummy uv run pytest tests/test_llm_pii.py tests/test_llm_context.py tests/test_dialogue_config.py -v --tb=short": passed
  - "uv run ruff check src/ tests/": passed
  - "uv run ruff format --check src/ tests/": passed
  - "uv run mypy src/": passed
  - "env DYLD_FALLBACK_LIBRARY_PATH=\"${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}\" OPENROUTER_API_KEY=dummy uv run pytest tests/ -v --tb=short": passed
  - "scripts/orchestration/run_process_verification.sh": passed
  - "GitHub Actions run 26955440129": passed
  - "GitHub Actions run 26956067120": passed
  - "GitHub Actions run 26956771039": passed
  - "uv run python scripts/verify_api.py --base-url https://noor.starec.ai": passed
  - "production E2E on +79262810921#tj-pii-off-e2e-20260604170643": passed
  - "production E2E on +79262810921#tj-pii-off-e2e-resume-20260604170643": passed
changed_files:
  - src/core/config.py
  - src/llm/pii.py
  - src/llm/context.py
  - src/llm/engine.py
  - tests/test_llm_pii.py
  - tests/test_llm_context.py
  - tests/test_dialogue_config.py
  - tests/test_llm_engine.py
  - .env.example
  - docs/specs/customer-facts-layer.md
  - docs/dev-guide.md
  - docs/task-plan.md
  - docs/client/treejar-client-self-test-guide-2026-05-01.md
  - docs/session-stage2-parallel-prompt.md
  - .codex/stages/tj-memory/summary.md
  - .codex/handoff.md
explicit_defers:
  - tj-memory.7: global customer_facts_mode enable remains a separate config decision after evidence review
  - tj-gh21: production follow-up sends outside 24h remain blocked until approved Wazzup WABA EN/AR templates exist
---

# Summary

PII masking is now disabled by default in runtime and production. It remains
available only as an explicit opt-in through `PII_MASKING_ENABLED=true`.

The first production E2E run caught two blocking regressions before closeout:

- A first-turn message that already contained name, email, phone, address, and
  SKU still triggered name-gate.
- A name-gate reply with extra customer details, for example
  `Victor PII Test, individual`, was saved as a detail update but did not
  resume the stored SKU request.

Both were fixed and covered by local regression tests before the final deploy.

# Delivery

Delivered commits:

- `1421cf91fe2e24a2fee0fd4ebb7c2eb826b1b335` -
  disable PII masking by default.
- `ae36633bad5f32fd6be0f1a9cebc96e2487f1c75` -
  honor customer details that arrive in the first turn.
- `e4e7ecff52d71434e5f0c179bc166c9e325f05bc` -
  resume name-gate requests when the customer sends name plus extra details.

Final deployment:

- GitHub Actions run `26956771039`: success.
- Production `/opt/noor/.release-sha`:
  `e4e7ecff52d71434e5f0c179bc166c9e325f05bc`.
- Production smoke for `https://noor.starec.ai`: `8 passed, 0 failed`.

# Final E2E

Scenario 1 identity:
`+79262810921#tj-pii-off-e2e-20260604170643`

Conversation:
`20bf6801-e24a-4474-a015-2c4be31bc50e`

Message:

```text
Hi Noor, I need 2 CH 616 black chairs with delivery and assembly. My name is Victor PII Test, individual, delivery address Office 1905, JLT Dubai, email victor.pii.e2e@example.com, phone +79262810921. Please confirm these selected items using these details.
```

Observed:

- Assistant model: `z-ai/glm-5|selection-confirmation`.
- Escalation: `none`.
- Customer name: `Victor PII Test`.
- Saved details: name, `individual`, email, phone, and `Office 1905, JLT Dubai`.
- Pending item: `2 x CH 616 black`.
- `contains_pii_placeholder=False`.

Scenario 2 identity:
`+79262810921#tj-pii-off-e2e-resume-20260604170643`

Conversation:
`f9e669ef-b46e-43cf-9096-bd0e50167819`

Messages:

```text
Hi Noor, I need 2 CH 616 black chairs with delivery to Office 1905, JLT Dubai, email victor.pii.e2e@example.com, phone +79262810921. Please confirm these selected items.
```

```text
Victor PII Test, individual
```

Observed:

- First assistant model: `name-gate`.
- Second assistant model: `z-ai/glm-5|selection-confirmation`.
- Escalation: `none`.
- `name_gate_pending_request_present=False`.
- Saved details: name, `individual`, email, phone, and `Office 1905, JLT Dubai`.
- Pending item: `2 x CH 616 black`.
- `contains_pii_placeholder=False`.

# Cleanup

Synthetic E2E conversations from this delivery were closed/resolved after
readback:

- `096bdf9d-d7b6-46b4-92eb-a674b65b04d3`
- `10796675-5219-4ebf-b247-75acc8dc7dd4`
- `a37d1129-d253-4c19-8d17-832d10e90a01`
- `20bf6801-e24a-4474-a015-2c4be31bc50e`
- `f9e669ef-b46e-43cf-9096-bd0e50167819`

The real unsuffixed `+79262810921` conversation was not mutated.

# Verification

Local verification:

- Targeted name-gate/SKU regressions passed, including
  `test_process_message_name_gate_resume_accepts_name_plus_customer_type`.
- PII/context/config tests passed.
- `uv run ruff check src/ tests/` passed.
- `uv run ruff format --check src/ tests/` passed.
- `uv run mypy src/` passed.
- Full pytest passed: `1281 passed, 19 skipped`.
- `scripts/orchestration/run_process_verification.sh` passed.

Production verification:

- GitHub Actions run `26956771039` passed, including deploy.
- Runtime release readback matched
  `e4e7ecff52d71434e5f0c179bc166c9e325f05bc`.
- Production smoke passed: `8 passed, 0 failed`.
- Both final E2E scenarios passed with no escalation and no `[PII-...]`
  placeholders.

# Risks / Follow-ups

- `tj-memory.7` remains open for the separate decision to enable
  `customer_facts_mode=shadow|enforce` globally.
- `tj-gh21` remains blocked until approved Wazzup WABA EN/AR templates are
  available for sends outside the free-form window.

# Documentation Review

docs-reviewed: updated - `.env.example`, customer facts spec, project docs,
handoff, stage summary, and this artifact now state that PII masking is default
off and opt-in only.

graph-reviewed: no-change-needed - Graphify is not configured; no
`graphify-out/GRAPH_REPORT.md` or `[knowledge_graph]` configuration exists.
