---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-final27-client-handoff/stage-manifest.json
stream_owner: tj-final27-client-handoff-root
orchestration_level: release
scope_kind: product_slice
immediate_consumer: client final-acceptance decision
public_facade: Noor opening reply and final client handoff pack
bounded_acceptance: remaining client-handoff code, measurement, controlled E2E, and delivery
non_goals:
  - no rubric, applicability-map, model, prompt, or retrieval-evidence change
  - no protected replay re-baseline
  - no second reader or tj-jlx4 work
evidence:
  - protected-round
  - github-actions-deploy
  - production-health
  - controlled-e2e
task_id: tj-final27.9
epic_id: tj-final27
stage_id: tj-final27-client-handoff
session_id: tj-final27
milestone: client-handoff-code-measurement-e2e-delivery
milestone_status: accepted
agent_type: n/a
subagent_model: n/a
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: root owned implementation, blind reading, acceptance, and delivery
repo: treejar
branch: main
base_branch: main
base_commit: 40357200c052d14c84c2c282cc6625457ae2122b
worktree: /home/me/code/treejar
write_zone:
  - src
  - tests
  - docs/client
  - .beads
  - .codex
success_criteria:
  - pinned English anchor is exactly AED 139 / AED 58 and preflight is 19 priced / 1 withheld
  - customer-facing output deterministically stays in the selected turn language
  - bare greetings deliver one literal question marker
  - all application log handlers redact HTTP access paths, query strings, and userinfo
  - blind openings-20 round is paired against the preceding round without a second reader
  - protected raw replay and release gates stay fixed
  - production health reports the delivered SHA
selected_docs:
  - AGENTS.md
  - .codex/orchestrator.toml
  - .codex/handoff.md
  - docs/root-reading-convention.md
selected_skills:
  - orchestrator-stage
  - technical-premortem
  - systematic-debugging
  - test-driven-development
  - orchestration-closeout
selected_agents:
  - none
catalog_candidates:
  - none
parallel_group: n/a
depends_on_streams:
  - none
parallel_decision: root acceptance and blind reading were non-delegable
status: accepted
delivery_method: manual integration
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: root used the authorized main worktree; no delegated workspace or branch exists to remove
risk_level: high
verification_tier: release
risk_tags:
  - state-transition
  - user-flow
  - rollback
  - security
affected_surfaces:
  - backend
  - user-flow
invariants:
  - state-transition
  - rollback
  - test-matrix
docs_impact: behavior
docs_reviewed: updated
docs_review_notes: handoff, client pack, reading convention, and stage evidence record current behavior and measurement
verification:
  - preflight AED 139 / 58 and 19 priced / 1 withheld: passed
  - blind root round 20/20 language and zero critical failures: passed
  - every measured reply had one literal question marker: passed
  - protected raw replay 1b425bd1 versus 1fc87c04 with seven expected differences: passed
  - safe production log scan found zero complete access URLs and zero query URLs: passed
  - synthetic deployed guard readback found one question and no second-language letters: passed
  - uv run ruff check src/ tests/: passed
  - uv run ruff format --check src/ tests/: passed
  - uv run mypy src/: passed
  - uv run pytest tests/ -v --tb=short: passed 3832 passed 20 skipped
  - scripts/orchestration/run_process_verification.sh: passed
  - first formal closeout exposed five documentation-maintenance failures; required handoff fields and the current-state traceability pin were updated
  - GitHub Actions run 31805222594: passed
  - production health returned f5be6a26b292b81da1288ca3c394ceac21eb57a3: passed
changed_files:
  - .beads/issues.jsonl
  - .codex/handoff.md
  - .codex/stages/tj-final27-client-handoff/stage-manifest.json
  - .codex/stages/tj-final27-client-handoff/summary.md
  - .codex/stages/tj-final27-client-handoff/artifacts/tj-final27.9.md
  - .codex/stages/tj-ee5f/traceability-manifest.json
  - docs/client/final-acceptance-pack-2026-04-29.md
  - src/core/safe_logging.py
  - src/integrations/messaging/wazzup.py
  - src/llm/engine.py
  - src/llm/language_guard.py
  - src/llm/message_processor.py
  - src/llm/opening_guard.py
  - src/llm/outbound_reply_guard.py
  - src/main.py
  - src/worker.py
  - tests/test_corpus_bridge_real_opening_acceptance.py
  - tests/test_llm_engine.py
  - tests/test_outbound_reply_guard.py
  - tests/test_safe_logging.py
explicit_defers:
  - tj-jlx4 is excluded from this task by owner instruction
  - reader-gap drift re-read remains separately tracked in tj-4q79; no second reader was authorized
---

# Summary

The final client-handoff stage is accepted. The logging, turn-language and
double-question blockers are closed, the paid confirmation round met 20/20
language with zero critical failures, release gates passed, and production
health returned the delivered code SHA.

The existing Telegram token was intentionally not rotated under the recorded
owner decision: the observed log copy stayed on the owner-controlled server and
was not exported, collected by CI, committed, documented, or placed in an
artifact. Protection is preventive and generic: a record-editing filter redacts
HTTP(S) paths, queries and userinfo on every active handler, independent of the
HTTP client or logger name.

The protected round remains only under the git-common runtime directory. Tracked
records contain ids, integers, scores and digests, never protected request or
reply bodies.

# Verification

The frontmatter lists the accepted round, replay, release gates, production
health and safe synthetic readbacks. The root-owned release closeout is the
final local acceptance boundary.

# Risks / Follow-ups

No in-scope blocker remains. `tj-jlx4` is excluded by owner instruction, and
reader-gap drift work remains independently tracked in `tj-4q79`; neither
changes this stage's acceptance.
