---
schema_version: orchestration-artifact/v1
artifact_type: delivery-e2e
task_id: tj-memory.7
stage_id: tj-memory
agent_type: n/a
subagent_model: n/a
reasoning_effort: n/a
model_reasoning_rationale: local sequential rollout, production config, and E2E
repo: treejar
branch: main
base_branch: main
base_commit: db409cec01035425da3ac4e71d4213f88bdfcf8c
worktree: /home/me/code/treejar
write_zone:
  - src/llm/fact_extractor.py
  - src/llm/engine.py
  - tests/test_fact_extractor.py
  - tests/test_llm_engine_customer_facts.py
  - .codex/stages/tj-memory
  - .codex/handoff.md
success_criteria:
  - production customer facts mode is globally enabled in enforce
  - product delivery/assembly text is not stored as a delivery address
  - name-gate replies with extra customer details resume the pending request
  - production E2E passes with no escalation, no fact conflicts, and no PII placeholders
selected_docs:
  - no dependency documentation lookup needed; rollout used existing repo config and runtime state
selected_skills:
  - /home/me/.agents/skills/orchestrator-stage/SKILL.md
  - /mnt/c/Users/masle/.codex/superpowers/skills/test-driven-development/SKILL.md
  - /mnt/c/Users/masle/.codex/superpowers/skills/verification-before-completion/SKILL.md
selected_agents:
  - none - local sequential fix and production test resource
catalog_candidates:
  - none - installed repo orchestration assets fit
parallel_group: G
depends_on_streams:
  - tj-memory.1
  - tj-memory.2
  - tj-memory.3
  - tj-memory.4
  - tj-memory.5
  - tj-memory.6
parallel_decision: sequential
status: accepted
delivery_method: merge
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: synthetic production E2E conversations were closed after readback
risk_level: medium
docs_impact: behavior,ops-deploy
docs_reviewed: updated
docs_review_notes: handoff and stage summary record enforce rollout and final evidence
verification:
  - "OPENROUTER_API_KEY=dummy uv run pytest tests/test_fact_extractor.py::test_deterministic_does_not_treat_product_delivery_need_as_address -v --tb=short": failed before fix, passed after fix
  - "OPENROUTER_API_KEY=dummy uv run pytest tests/test_llm_engine_customer_facts.py::test_customer_facts_name_gate_details_reply_resumes_pending_request -v --tb=short": failed before fix, passed after fix
  - "OPENROUTER_API_KEY=dummy uv run pytest tests/test_fact_extractor.py tests/test_llm_engine_customer_facts.py tests/test_dialogue_config.py -v --tb=short": passed, 25 passed
  - "OPENROUTER_API_KEY=dummy uv run pytest tests/test_llm_engine.py -k \"name_gate or ch616_spaced_sku_with_details or customer_details\" -v --tb=short": passed, 29 passed
  - "uv run ruff check src/ tests/": passed
  - "uv run ruff format --check src/ tests/": passed
  - "uv run mypy src/": passed
  - "env DYLD_FALLBACK_LIBRARY_PATH=\"${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}\" OPENROUTER_API_KEY=dummy uv run pytest tests/ -v --tb=short": passed, 1283 passed, 19 skipped
  - "GitHub Actions run 26964467543": passed and deployed
  - "uv run python scripts/verify_api.py --base-url https://noor.starec.ai": passed, 8 passed, 0 failed
  - "production E2E on +79262810921#tj-memory-enforce-final-*": passed
changed_files:
  - src/llm/fact_extractor.py
  - src/llm/engine.py
  - tests/test_fact_extractor.py
  - tests/test_llm_engine_customer_facts.py
  - .codex/stages/tj-memory/summary.md
  - .codex/handoff.md
explicit_defers:
  - tj-gh21: production follow-up sends outside 24h remain blocked until approved Wazzup WABA EN/AR templates exist
---

# Summary

The customer facts layer is now globally enabled in production with
`customer_facts_mode=enforce`, `customer_facts_trace_enabled=true`, and
`customer_facts_fast_extractor_enabled=true`.

Runtime release:
`e70e1d8c7d9796ec9142cfe55b724e6ed524a1d1`.

Deploy run:
`26964467543`.

# Blockers Found During Rollout

The first enforce E2E found two blockers before final enablement:

- `I need 2 CH 616 chairs with delivery and assembly` was incorrectly stored as
  `delivery.address`.
- A reply like `Victor Memory Test, individual, delivery address ...` after
  name-gate could be handled as `detail-capture` before consuming
  `name_gate_pending_request`.

The production flag was temporarily returned to `disabled` while the fix was
implemented and deployed.

# Fixes

- Compact address extraction now rejects product/request phrases and generic
  SKU-like text before accepting an unlabeled value as a delivery address.
- Pending name-gate replies always get a chance to extract a compact name from
  `name + details`, even if the customer facts layer has already set
  `conversation.customer_name`.

# Verification

Local and CI verification passed before final production E2E:

- Targeted RED/GREEN tests for false address extraction and name-gate resume.
- `ruff`, `ruff format --check`, `mypy`, and full pytest.
- GitHub Actions run `26964467543` deployed the fix.
- Production smoke passed with 8 checks and 0 failures.

# Final E2E

Production config after deploy:

```json
{
  "dialogue_kernel_mode": "enforce",
  "dialogue_kernel_enforced_flows": "product_selection",
  "customer_facts_mode": "enforce",
  "customer_facts_trace_enabled": "true",
  "customer_facts_fast_extractor_enabled": "true"
}
```

Scenario 1:
`+79262810921#tj-memory-enforce-final-all-20260604162026`

- Conversation: `70838bd7-8f4c-4ee0-8a4a-a0dd5ab92d7c`.
- Message included SKU, quantity, name, individual status, address, email, and
  phone in one turn.
- Result: `z-ai/glm-5|selection-confirmation`.
- Readback: `2 x CH 616 black`, no unresolved items, `conflict_count=0`, no
  escalation, no PII placeholders.

Scenario 2:
`+79262810921#tj-memory-enforce-final-resume-20260604162026`

- Conversation: `89d614de-cd72-412c-9964-9554ed995ebc`.
- First turn without name returned `name-gate`.
- Second turn provided name, individual status, address, email, and phone.
- Result: `z-ai/glm-5|selection-confirmation`.
- Readback: `name_gate_pending=false`, `2 x CH 616 black`, no unresolved items,
  `conflict_count=0`, no escalation, no PII placeholders.

The synthetic conversations were closed after readback. The real unsuffixed
`+79262810921` thread was not mutated.

# Rollback

Rollback is config-only:

```text
customer_facts_mode=disabled
```

Trace and fast extractor flags can remain enabled because they have no effect
while mode is disabled.

# Risks / Follow-ups

- Monitor real customer conversations for unexpected customer facts trace
  conflicts while enforce mode is newly enabled.
- `tj-gh21` remains blocked until approved Wazzup WABA EN/AR templates exist.
