---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-av22/stage-manifest.json
stream_owner: latency-worker
orchestration_level: slice_acceptance
scope_kind: product_slice
immediate_consumer: root-orchestrator
public_facade: scripts/analyze_chat_latency.py
bounded_acceptance: privacy-safe phase evidence, summary-send ordering, and affected correctness matrix
non_goals:
  - live-provider-or-production-latency
  - deployment-or-runtime-mutation
  - model-prompt-or-catalog-behavior-changes
  - real-Wazzup-Zoho-Telegram-or-OpenRouter-calls
evidence:
  - none
task_id: tj-15m.6
epic_id: tj-av22
stage_id: tj-av22
session_id: tj-av22-latency
milestone: noor-latency-evidence-and-safe-local-reduction
milestone_status: accepted
agent_type: worker
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: cross-module performance evidence and customer-visible delivery ordering required inherited reasoning
repo: treejar
branch: codex/tj-av22-latency
base_branch: codex/tj-av22-stabilization
base_commit: f76fac2cba606482b969f360dd006b56cc4b1a2b
worktree: /home/me/code/treejar/.worktrees/tj-av22-stabilization/.worktrees/tj-av22-latency
write_zone:
  - src/llm/engine.py
  - src/services/chat.py
  - src/services/chat_latency.py
  - scripts/analyze_chat_latency.py
  - scripts/benchmark_chat_delivery_boundary.py
  - focused-latency-chat-llm-tests
  - docs/latency-evidence.md
  - .codex/stages/tj-av22/artifacts/tj-15m.6.md
success_criteria:
  - meaningful chat phases are recorded without message content or identifiers
  - current local and historical evidence identify the dominant remaining bucket
  - an independent future-turn summary enqueue is removed from text-delivery latency
  - catalog, quotation, escalation, language, media, and summary tests remain green
selected_docs:
  - AGENTS.md
  - .codex/orchestrator.toml
  - .codex/handoff.md
  - docs/superpowers/specs/2026-07-23-noor-stabilization-design.md
  - docs/superpowers/plans/2026-07-23-noor-stabilization.md
  - Beads tj-15m and tj-15m.1 through tj-15m.6
selected_skills:
  - systematic-debugging
  - test-driven-development
  - verification-before-completion
  - format-commit-message
selected_agents:
  - built-in-latency-reliability-worker
catalog_candidates:
  - none
parallel_group: runtime-latency
depends_on_streams:
  - none
parallel_decision: parallel
status: returned
delivery_method: merge
accepted_by_orchestrator: yes
cleanup_status: pending
cleanup_notes: isolated worktree retained for root-orchestrator review and integration
risk_level: medium
verification_tier: integration
risk_tags:
  - none
affected_surfaces:
  - backend
invariants:
  - test-matrix
docs_impact: behavior
docs_reviewed: updated
docs_review_notes: docs/latency-evidence.md records evidence classes, measurement commands, privacy limits, and the production gate
verification:
  - uv run python -m pytest focused latency chat escalation summary LLM dialogue and product suite - 385 passed: passed
  - uv run ruff check src tests and latency scripts: passed
  - uv run ruff format --check src tests and latency scripts: passed
  - uv run mypy src/: passed
  - uv run python scripts/benchmark_chat_delivery_boundary.py --samples 9: passed
  - uv run python scripts/analyze_chat_latency.py with allowlisted local samples: passed
changed_files:
  - src/llm/engine.py
  - src/services/chat.py
  - src/services/chat_latency.py
  - scripts/analyze_chat_latency.py
  - scripts/benchmark_chat_delivery_boundary.py
  - tests/test_chat_latency.py
  - tests/test_services_chat_batch.py
  - tests/test_llm_engine.py
  - docs/latency-evidence.md
  - .codex/stages/tj-av22/artifacts/tj-15m.6.md
explicit_defers:
  - tj-av22.3 - approved deployment and bounded live synthetic matrix are required for p50 p95 and maximum production claims
  - tj-av22.3 - if model_tools remains dominant, record the exact external provider blocker without weakening correctness
---

# Summary

Historical warmed-path evidence attributes the dominant remaining delay to the
LLM provider plus sequential tool turns: FAQ lookup was about `0.11s` while
`process_message` remained `21.29-41.75s`, and later product-heavy live turns
remained about `31-42s`. No current provider measurement was fabricated.

The returned implementation adds an allowlisted latency trace for queue wait,
pre-LLM work, LLM context, FAQ and behavior RAG, model/tools, persistence,
outbound text, summary enqueue, deferred media, time-to-text, and total time.
The parser rejects arbitrary keys, so the trace cannot accept message text,
phone numbers, conversation IDs, credentials, or raw tool data.

Current code inspection found a smaller local delay: two summary-decision SQL
reads and a possible Redis enqueue occurred after response persistence but
before Wazzup text delivery, although the summary is used only by future turns.
The operation now occurs after text send while retaining the same-job and
failure semantics.

# Scope / Routing

Work stayed within the assigned chat/LLM latency surface, focused scripts,
tests, documentation, and this artifact. The branch merged the current
stabilization head `ba15a2c` after implementation commit `b41bf0a`; there were
no write-zone conflicts. No external documentation was needed because the
decision depended on repository-owned sequencing and existing historical
Beads evidence.

# Verification

The red contract initially observed `summary_enqueued -> text_sent`; after the
change it proves `text_sent -> summary_enqueued`. The fresh affected matrix
passed all 385 tests covering latency schema, inbound batch handling,
escalation, conversation summaries, LLM engine behavior, dialogue scenarios,
and product images.

Ruff check, Ruff format check, and Mypy passed for the affected repository
surface. The controlled nine-sample boundary benchmark measured p50
time-to-text of `60.761ms` for the legacy ordering and `30.533ms` for the
current ordering with a configured `30ms` summary phase, a `30.228ms`
reduction. This proves the scheduling boundary only, not live dependency
latency.

# Delivery / Cleanup

Implementation commit `b41bf0a` is on `codex/tj-av22-latency`. The current
stabilization branch was merged into the worker branch as `0bbda35`. The
worker did not merge back into the integration branch, push, deploy, access
live services, or clean the isolated worktree.

# Risks / Follow-ups / Explicit Defers

Only successful LLM-backed or timeout paths currently emit the detailed trace;
static, manual-takeover, and early escalation paths remain covered by their
existing deterministic tests but need the approved bounded matrix for complete
runtime distribution evidence.

`tj-av22.3` owns deployment and the approval-gated live matrix across FAQ,
product search, comparison, quotation/order, Arabic, and escalation. It must
record `p50`, `p95`, maximum, provider/model configuration, and correctness.
If `model_tools` remains dominant while local phases stay small, the exact
external provider limitation is the bounded blocker.
