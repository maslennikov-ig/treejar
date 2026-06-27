---
schema_version: orchestration-artifact/v1
artifact_type: local-implementation
task_id: tj-jyig
stage_id: tj-gh56-product-media-sku
agent_type: n/a
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: narrow customer-visible bugfix after read-only subagent diagnosis
repo: treejar
branch: codex/tj-gh56-product-media-sku
base_branch: main
base_commit: b28c246af13db58cae921e4ff08705831c3ae8ad
worktree: /home/me/code/treejar/.worktrees/tj-gh56-product-media-sku
write_zone:
  - src/llm/engine.py
  - tests/test_product_images.py
  - docs/superpowers/plans/2026-06-27-gh56-product-media-sku.md
  - .codex/stages/tj-gh56-product-media-sku
  - .codex/handoff.md
success_criteria:
  - exact convertible/sleeper product media is queued
  - nearby normal-chair media is not queued when exact media exists
  - suppressed nearby products do not claim an image will be sent
  - existing product-media and deferred-media flows stay green
selected_docs:
  - AGENTS.md
  - .codex/orchestrator.toml
  - .codex/handoff.md
  - .codex/project-index.md
  - GitHub #56/#55/#9 context
selected_skills:
  - /home/me/.agents/skills/orchestrator-stage/SKILL.md
  - /home/me/.agents/skills/task-router/SKILL.md
  - /home/me/code/treejar/.agents/skills/process-issues/SKILL.md
  - /mnt/c/Users/masle/.codex/superpowers/skills/systematic-debugging/SKILL.md
  - /mnt/c/Users/masle/.codex/superpowers/skills/test-driven-development/SKILL.md
  - /mnt/c/Users/masle/.codex/superpowers/skills/writing-plans/SKILL.md
  - /mnt/c/Users/masle/.codex/superpowers/skills/verification-before-completion/SKILL.md
  - /home/me/.agents/skills/orchestration-closeout/SKILL.md
selected_agents:
  - code_mapper
  - debugger
catalog_candidates:
  - none - installed assets covered the workflow
parallel_group: C-local-fix
depends_on_streams:
  - A-code-map
  - B-debugger
parallel_decision: sequential
status: accepted
delivery_method: manual integration
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: implementation remains in this stage worktree for user review; no child worktree cleanup needed
risk_level: medium
docs_impact: behavior
docs_reviewed: no-change-needed
docs_review_notes: narrow runtime bugfix covered by tests; no public API, operator workflow, deployment, or architecture contract changed
verification:
  - "OPENROUTER_API_KEY=dummy uv run --extra dev pytest tests/test_product_images.py::test_search_products_defers_only_exact_match_media_when_query_has_specific_modifier -q": failed before implementation, then passed
  - "OPENROUTER_API_KEY=dummy uv run --extra dev pytest tests/test_product_images.py tests/test_services_chat_batch.py::test_process_incoming_batch_sends_deferred_product_media_after_bot_reply -q": passed, 9 passed
  - "uv run --extra dev ruff check src/ tests/": passed
  - "uv run --extra dev ruff format --check src/ tests/": passed
  - "uv run --extra dev mypy src/": passed
  - "OPENROUTER_API_KEY=dummy env DYLD_FALLBACK_LIBRARY_PATH=\"${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}\" uv run --extra dev pytest tests/ -v --tb=short": initially failed due missing frontend/admin esbuild, then passed after npm ci, 1431 passed, 19 skipped
changed_files:
  - src/llm/engine.py
  - tests/test_product_images.py
  - docs/superpowers/plans/2026-06-27-gh56-product-media-sku.md
  - .codex/stages/tj-gh56-product-media-sku/artifacts/tj-jyig-code-map.md
  - .codex/stages/tj-gh56-product-media-sku/artifacts/tj-jyig-debugger.md
  - .codex/stages/tj-gh56-product-media-sku/artifacts/tj-jyig-local-implementation.md
  - .codex/stages/tj-gh56-product-media-sku/summary.md
  - .codex/handoff.md
explicit_defers:
  - no live/prod audit, catalog mutation, deploy, push, or GitHub issue mutation was performed
---

# Summary

Implemented a product-media guard in `search_products`: when the result set has
one or more exact product matches for the query, media is queued/sent only for
the exact-matching products. Nearby results can remain in the text contract as
alternatives, but their images are not sent as if they belonged to the exact
request.

# Scope / Routing

This stayed local because the fix is one shared code path. Docs L1/L2 was
attempted for `pydantic-ai` and `sqlalchemy` and returned `fallback-needed`; the
actual behavior was local deterministic product/media logic.

# Verification

The regression failed before the fix by queueing both
`convertible-sleeper.jpg` and `visitor-chair.jpg`. After the fix, only exact
media is queued and only exact products receive the "Image will be sent" tool
note. Targeted media tests, ruff, mypy, and full pytest passed.

# Delivery / Cleanup

No commit, push, deploy, production mutation, live WhatsApp test, or GitHub issue
mutation was performed.

# Risks / Follow-ups / Explicit Defers

The local fix does not validate whether the primary catalog image for
`CSC-01 beige` is itself correct. That requires read-only live/catalog evidence
or a catalog-data correction workflow.
