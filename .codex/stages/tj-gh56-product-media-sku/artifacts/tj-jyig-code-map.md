---
schema_version: orchestration-artifact/v1
artifact_type: delegated-stream
task_id: tj-jyig
stage_id: tj-gh56-product-media-sku
agent_type: code_mapper
subagent_model: inherit_orchestrator
reasoning_effort: role_default
model_reasoning_rationale: read-only path mapping; medium role default was sufficient
repo: treejar
branch: codex/tj-gh56-product-media-sku
base_branch: main
base_commit: b28c246af13db58cae921e4ff08705831c3ae8ad
worktree: /home/me/code/treejar/.worktrees/tj-gh56-product-media-sku
write_zone:
  - none
success_criteria:
  - identify product search to outbound media path
  - identify SKU/name/description/image_url divergence points
  - identify missing regression test
selected_docs:
  - AGENTS.md
  - .codex/orchestrator.toml
  - .codex/project-index.md
  - GitHub #56/#55/#9 context
selected_skills:
  - /home/me/.agents/skills/orchestrator-stage/SKILL.md
  - /home/me/.agents/skills/task-router/SKILL.md
  - /home/me/code/treejar/.agents/skills/process-issues/SKILL.md
selected_agents:
  - code_mapper
catalog_candidates:
  - none - installed agent fit
parallel_group: A-code-map
depends_on_streams:
  - none
parallel_decision: parallel
status: accepted
delivery_method: manual integration
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: read-only spawned agent; no branch/worktree cleanup required
risk_level: medium
docs_impact: none
docs_reviewed: no-change-needed
docs_review_notes: read-only mapping did not change stable docs
verification:
  - read-only code search and file inspection: passed
changed_files:
  - none
explicit_defers:
  - runtime read-only catalog/audit lookup can distinguish wrong source image from extra nearby result if live evidence is later authorized
---

# Summary

Mapped the product-media path from Wazzup inbound through `process_incoming_batch`,
`search_products`, `SalesDeps.pending_product_media`, and
`_send_deferred_product_media`.

# Scope / Routing

The strongest code-path finding was that `search_products` queues media for each
RAG top-3 result before the final assistant text exists. A second risk is catalog
data: Treejar sync trusts the first `images[].url` or `image` field for a product
without visual/SKU validation.

# Verification

Read-only inspection found existing product-media tests in
`tests/test_product_images.py` and `tests/test_services_chat_batch.py`. The
recommended missing regression was exact product plus nearby normal-chair result
with only exact media queued.

# Delivery / Cleanup

No files were changed by this stream.

# Risks / Follow-ups / Explicit Defers

Live read-only audit/catalog data could still prove that `CSC-01 beige` itself has
a wrong primary image. That is outside local code verification and was not needed
for the local guard.
