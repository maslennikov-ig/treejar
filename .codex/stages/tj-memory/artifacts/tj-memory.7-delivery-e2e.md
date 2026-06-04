---
schema_version: orchestration-artifact/v1
artifact_type: delivery-e2e
task_id: tj-memory.7
stage_id: tj-memory
agent_type: n/a
subagent_model: n/a
reasoning_effort: n/a
model_reasoning_rationale: local sequential delivery/E2E; no subagent used
repo: treejar
branch: main
base_branch: main
base_commit: d49abcfc0606102b2098880245723e6fda999193
worktree: /home/me/code/treejar
write_zone:
  - src/llm/engine.py
  - src/llm/fact_extractor.py
  - tests/test_llm_engine.py
  - tests/test_fact_extractor.py
  - .codex/stages/tj-memory
  - .codex/handoff.md
success_criteria:
  - customer facts layer deployed behind config
  - production E2E proves multi-fact first message keeps known details
  - CH 616 quantity remains 2, not 616
  - customer facts trace has no assistant-greeting name conflict
selected_docs:
  - no dependency documentation lookup needed; delivery/E2E used repo scripts and runtime state
selected_skills:
  - /home/me/.agents/skills/orchestrator-stage/SKILL.md
  - /mnt/c/Users/masle/.codex/superpowers/skills/verification-before-completion/SKILL.md
  - /home/me/.agents/skills/orchestration-closeout/SKILL.md
selected_agents:
  - none - local sequential delivery and production test resource
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
cleanup_status: not_applicable
cleanup_notes: no delegated worktree was created; customer_facts temporary production config was restored to UNSET
risk_level: medium
docs_impact: behavior,ops-deploy
docs_reviewed: updated
docs_review_notes: stage summary and handoff updated with production evidence and rollout state
verification:
  - "OPENROUTER_API_KEY=dummy uv run pytest tests/test_llm_engine.py::test_process_message_ch616_spaced_sku_with_details_uses_leading_quantity -v --tb=short": passed
  - "OPENROUTER_API_KEY=dummy uv run pytest tests/test_fact_extractor.py::test_deterministic_does_not_treat_spaced_sku_number_as_plain_quantity -v --tb=short": passed
  - "OPENROUTER_API_KEY=dummy uv run pytest tests/test_fact_extractor.py tests/test_llm_engine_customer_facts.py tests/test_dialogue_config.py -v --tb=short": passed
  - "OPENROUTER_API_KEY=dummy uv run pytest tests/test_llm_engine.py -k 'CH616 or ch616 or purchase_selection or quote_customer_details or delivery_address or pending_quote_selection' -v --tb=short": passed
  - "uv run ruff check src/ tests/": passed
  - "uv run ruff format --check src/ tests/": passed
  - "uv run mypy src/": passed
  - "env DYLD_FALLBACK_LIBRARY_PATH=\"${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}\" OPENROUTER_API_KEY=dummy uv run pytest tests/ -v --tb=short": passed
  - "scripts/orchestration/run_process_verification.sh": passed
  - "GitHub Actions run 26951658369": passed
  - "uv run python scripts/verify_api.py --base-url https://noor.starec.ai": passed
  - "production E2E on +79262810921#tj-memory-e2e-20260604-1231": passed
changed_files:
  - src/llm/engine.py
  - src/llm/fact_extractor.py
  - tests/test_llm_engine.py
  - tests/test_fact_extractor.py
  - .codex/stages/tj-memory/summary.md
  - .codex/handoff.md
explicit_defers:
  - tj-memory.7: global customer_facts_mode enable remains a separate config decision after evidence review
  - tj-gh21: production follow-up sends outside 24h remain blocked until approved Wazzup WABA EN/AR templates exist
---

# Summary

The customer facts layer was merged to `main`, deployed, and validated in
production under a temporary `customer_facts_mode=enforce` override. The
override was removed after the test, so global production behavior remains
config-gated.

# E2E Scenario

Test identity:
`+79262810921#tj-memory-e2e-20260604-1231`

Message:

```text
Hi Noor, I need 2 CH 616 chairs with delivery and assembly. My name is Victor, individual, delivery address Office 1905, JLT Dubai, email victor.memory.e2e@example.com.
```

Expected behavior:

- Confirm `2 x CH 616`, not `616 x chairs`.
- Resolve the active catalog item.
- Do not ask again for full name, email, customer type, or delivery address.
- Store quote details and customer facts.
- Do not escalate.

Observed assistant response:

```text
Hello, I'm Noor from Treejar.

Great, I can confirm the selected items from our catalog:

1. SkyLand  Workstation Chair CH 616 black
   Quantity: 2
   Availability: 3 available (Zoho-confirmed)
   Unit price: 220.00 AED
   Line total: 440.00 AED

Total: 440.00 AED

Would you like me to prepare a formal quotation for these selected items using the details you already shared?
```

# Verification

Local verification passed before deploy:

- Targeted regression tests for `CH 616`, quote details, and customer facts.
- `uv run ruff check src/ tests/`.
- `uv run ruff format --check src/ tests/`.
- `uv run mypy src/`.
- Full pytest: `1276 passed, 19 skipped`.
- `scripts/orchestration/run_process_verification.sh`.

Production verification passed after deploy:

- Runtime release: `ccd8b094b521ed7f899240feaf739c12d4e0ba83`.
- Deploy run: `26951658369`.
- Smoke: `8 passed, 0 failed`.
- Conversation: `0e1feaa8-5922-49b9-abb6-9ab111607d92`.
- `quote_customer_details`: Victor, `victor.memory.e2e@example.com`,
  `Office 1905, JLT Dubai`, `individual`.
- `pending_quote_selection`: `CH 616 black`, quantity `2`,
  `unresolved_items=[]`.
- Customer facts trace: `accepted_count=7`, `conflict_count=0`,
  `fast_model_called=false`.
- Escalations: `0`.
- Production config after test: `customer_facts_mode`,
  `customer_facts_trace_enabled`, and `customer_facts_fast_extractor_enabled`
  restored to `UNSET`; `dialogue_kernel_mode=enforce` remains only for
  `product_selection`.

# Delivery / Cleanup

Delivery used direct `main` pushes under current user authorization and the repo
main-only delivery policy. No delegated worktree was created. The only remaining
untracked file is the pre-existing local `.claude/settings.local.json`, which is
outside this stage.

# Fixes From E2E

The first production E2E found additional issues before the final pass:

- `2 CH 616 chairs` was parsed as `616 x chairs`.
- A PII placeholder could win over the real SKU.
- The selection confirmation asked for details that were already supplied in
  the same message.
- The fact extractor stored `Hi Noor` as a conflicting `customer.name`.

All four issues now have regression coverage and passed production E2E.

# Risks / Follow-ups / Explicit Defers

Global `customer_facts_mode=shadow|enforce` remains a rollout decision, not a
code blocker. The verified code is deployed and can be enabled by config.
