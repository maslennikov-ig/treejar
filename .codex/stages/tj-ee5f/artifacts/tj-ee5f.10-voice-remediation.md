---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-ee5f/stage-manifest.json
stream_owner: /root/voice_remediation
orchestration_level: inner_loop
scope_kind: product_slice
immediate_consumer: tj-ee5f.1
public_facade: OpenRouter dedicated STT adapter
bounded_acceptance: focused voice transcription and fallback regression tests
non_goals:
  - deployment and paid provider canary
  - LLM, Zoho, E2E harness, Beads, or manifest changes
evidence:
  - none
task_id: tj-ee5f.10
epic_id: tj-ee5f
stage_id: tj-ee5f
session_id: voice-remediation
milestone: cohesive-vertical-slice
milestone_status: in_progress
agent_type: worker
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: inherited for a bounded implementation stream
repo: treejar
branch: codex/tj-ee5f-voice-remediation
base_branch: main
base_commit: 844a3946f36070ca282b9fbe921fd9225cefeddc
worktree: /home/me/code/treejar/.worktrees/tj-ee5f-voice-remediation
write_zone:
  - src/core/config.py
  - src/integrations/voice
  - src/services/chat.py
  - focused voice tests
  - this artifact
success_criteria:
  - dedicated STT endpoint receives audio without a transcription prompt
  - MIME and magic-byte detection rejects unknown or conflicting formats
  - provider usage, cost, audio duration, and request duration remain available
  - provider generation identity remains available in the transcription result
  - fallback dedupe is stable per distinct inbound message set
selected_docs:
  - https://openrouter.ai/docs/guides/overview/multimodal/stt
selected_skills:
  - systematic-debugging
  - test-driven-development
selected_agents:
  - worker
catalog_candidates:
  - none
parallel_group: voice-remediation
depends_on_streams:
  - none
parallel_decision: parallel
status: returned
delivery_method: cherry-pick
accepted_by_orchestrator: no
cleanup_status: pending
cleanup_notes: parent must accept the commit before safe cleanup
risk_level: medium
verification_tier: inner_loop
risk_tags:
  - api
  - idempotency
  - retry
affected_surfaces:
  - backend
  - user-flow
invariants:
  - idempotency
  - test-matrix
docs_impact: ops-deploy
docs_reviewed: no-change-needed
docs_review_notes: parent stage plan owns environment rollout and live acceptance
verification:
  - focused RED reproduced old chat endpoint, mp3 fallback, missing config, and content-hash dedupe
  - correction RED reproduced the missing Python config alias and generation identity
  - uv run --extra dev python -m pytest tests/test_voxtral.py tests/test_webhook_audio.py tests/test_services_chat.py -q --tb=short: passed
  - git diff --check: passed
  - artifact validation: blocked until the parent registers this delegated artifact in the stage manifest
changed_files:
  - src/core/config.py
  - src/integrations/voice/voxtral.py
  - src/services/chat.py
  - tests/test_services_chat.py
  - tests/test_voxtral.py
  - tests/test_webhook_audio.py
  - .codex/stages/tj-ee5f/artifacts/tj-ee5f.10-voice-remediation.md
explicit_defers:
  - tj-ee5f.10 production model configuration and provider canary remain parent-stage acceptance
---

# Summary

Voice transcription now calls OpenRouter's dedicated speech-to-text endpoint
without a text prompt. The adapter detects the real audio format, keeps provider
usage, timing, and generation metadata, and keys safe fallback sends by inbound
message IDs. Legacy Python callsites can read `settings.voxtral_model` as a
read-only alias of the new setting.

# Scope / Routing

The stream changed only voice configuration, the voice adapter, the chat audio
boundary, and focused tests. It did not touch product LLM behavior, Zoho,
acceptance infrastructure, task truth, manifests, deployment, or live systems.

# Verification

Focused RED proved all four reported failure sources in the previous
implementation. A correction RED also proved both review findings before their
fixes. The final focused target passed 41 tests, and `git diff --check` passed.
No authenticated or paid provider call, deployment, or production mutation was
performed; the initial RED reached only the provider's unauthenticated 401
boundary before the corrected test isolation.

# Delivery / Cleanup

Return the isolated branch commit to the parent for review and cherry-pick.
Keep the worktree until the parent records acceptance.

# Risks / Follow-ups / Explicit Defers

Deployment must set `VOICE_TRANSCRIPTION_MODEL` to an active STT model.
`VOXTRAL_MODEL` remains a temporary lower-priority environment alias. A
provider-originated OGG/Opus and FLAC canary is still required before closing
`tj-ee5f.10`; that live proof was outside this stream's authority. The parent
must also register this v3 artifact in the stage manifest before validation.
