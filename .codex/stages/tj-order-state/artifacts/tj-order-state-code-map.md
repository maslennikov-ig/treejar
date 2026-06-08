---
schema_version: orchestration-artifact/v1
artifact_type: delegated-stream
task_id: tj-order-state.2/tj-order-state.5
stage_id: tj-order-state
agent_type: code_mapper
subagent_model: inherit_orchestrator
reasoning_effort: role_default
model_reasoning_rationale: read-only code path mapping for cross-module refactor
repo: treejar
branch: codex/tj-order-state-refactor
base_branch: main
base_commit: 5c85a5b46d28320a1790196b48651ad6bc01a41f
worktree: read-only spawned Codex workspace
write_zone:
  - none
success_criteria:
  - map product/quantity/quote-details execution paths and risks
selected_docs:
  - AGENTS.md
  - .codex/orchestrator.toml
  - .codex/handoff.md
  - docs/specs/dialogue-state-kernel.md
  - docs/specs/customer-facts-layer.md
selected_skills:
  - /home/me/.agents/skills/orchestrator-stage/SKILL.md
  - /home/me/.agents/skills/task-router/SKILL.md
selected_agents:
  - code_mapper
catalog_candidates:
  - none
parallel_group: mapping-sidecar
depends_on_streams:
  - none
parallel_decision: parallel
status: accepted
delivery_method: manual integration
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: read-only spawned stream changed no files
risk_level: medium
docs_impact: structural
docs_reviewed: updated
docs_review_notes: specs and project index updated for new order runtime
verification:
  - code mapping by rg/sed/nl: passed
changed_files:
  - none
explicit_defers:
  - none
---

# Summary

The code mapper identified the current product/quantity/quote path across
`process_message`, `run_dialogue_kernel`, legacy `pending_quote_selection`,
expected-answer frames, customer facts, and `create_quotation()`. The highest
risk is dual ownership of order state and quote details.

# Scope / Routing

Read-only project mapping stream. The orchestrator used the mapping to keep
this stage scoped to product/quantity/order-item state and avoid moving
Zoho/PDF/WhatsApp side effects in the same change.

# Verification

The stream inspected repo contracts, specs, `src/llm/engine.py`,
`src/dialogue/`, `src/llm/fact_extractor.py`, and
`src/services/customer_memory.py`.

# Delivery / Cleanup

Accepted by orchestrator as mapping input. Cleanup is not applicable.

# Risks / Follow-ups / Explicit Defers

No explicit defers.
