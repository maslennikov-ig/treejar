---
schema_version: orchestration-artifact/v3
artifact_type: review-report
stage_manifest: .codex/stages/tj-av22/stage-manifest.json
stream_owner: combined-release-reviewer
orchestration_level: release
scope_kind: product_slice
immediate_consumer: root-orchestrator
public_facade: n/a
bounded_acceptance: independent release review of the complete Noor stabilization range 89f9a560..75d610d against AC-1 through AC-10
non_goals:
  - product-code test configuration Beads or existing-document changes
  - production deployment mutation or external-service proof
  - branch ancestry remote or cleanup changes
evidence:
  - none
task_id: tj-av22.10
epic_id: tj-av22
stage_id: tj-av22
session_id: tj-av22-release-review-pass
milestone: noor-stabilization-combined-release-review
milestone_status: replan-required
agent_type: reviewer
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: independent high-risk release review across security retry idempotency observability public API deploy rollback and durable documentation
repo: treejar
branch: codex/tj-av22-review-pass
base_branch: codex/tj-av22-stabilization
base_commit: 75d610de4bcfd12ba952b9f80b00fe2a98256c8e
worktree: /home/me/code/treejar/.worktrees/tj-av22-review-pass
write_zone:
  - .codex/stages/tj-av22/artifacts/tj-av22.10.md
success_criteria:
  - implementation tests deploy rollback documentation and stage evidence are checked against AC-1 through AC-10
  - correctness compliance and quality improvement verdicts are separate
  - every finding has severity confidence file-line evidence impact and correction
  - local defects are distinguished from approval-gated production proof
selected_docs:
  - AGENTS.md
  - .codex/orchestrator.toml
  - .codex/handoff.md
  - .codex/project-index.md
  - docs/superpowers/specs/2026-07-23-noor-stabilization-design.md
  - docs/superpowers/plans/2026-07-23-noor-stabilization.md
  - .codex/stages/tj-av22/stage-manifest.json
  - .codex/stages/tj-av22/summary.md
  - .codex/stages/tj-av22/artifacts/tj-av22.5.md
  - .codex/stages/tj-av22/artifacts/tj-av22.7.md
  - .codex/stages/tj-av22/artifacts/tj-av22.8.md
  - .codex/stages/tj-av22/artifacts/tj-av22.9.md
selected_skills:
  - code-review
  - verification-before-completion
  - orchestrator-stage
  - format-commit-message
  - orchestration-closeout
selected_agents:
  - combined correctness compliance and quality improvement reviewer
catalog_candidates:
  - none
parallel_group: combined-release-review
depends_on_streams:
  - final-stabilization-review
parallel_decision: parallel
status: returned
delivery_method: not accepted
accepted_by_orchestrator: no
cleanup_status: pending
cleanup_notes: review artifact is committed for root triage; this reviewer did not close the stage or remove the isolated worktree
risk_level: high
verification_tier: release
risk_tags:
  - security
  - concurrency
  - retry
  - state-transition
  - idempotency
  - rollback
  - public-api
  - data
affected_surfaces:
  - backend
  - data
  - api
invariants:
  - state-transition
  - idempotency
  - rollback
  - test-matrix
docs_impact: docs-only
docs_reviewed: needs-work
docs_review_notes: two durable documents still describe the retired public SaleOrder routes as active or returning 501
graph_reviewed: no-change-needed
graph_review_notes: Graphify is not configured and graphify-out/GRAPH_REPORT.md is absent
verification:
  - git diff --check 89f9a560071302d16f53704870e7a508e9d05f28...HEAD: passed
  - focused AC release matrix - 517 passed: passed
  - uv run ruff check src/ tests/: passed
  - uv run ruff format --check src/ tests/ - 300 files: passed
  - uv run mypy src/ - 162 source files: passed
  - scripts/orchestration/run_process_verification.sh: passed
  - python3 scripts/orchestration/check_stage_ready.py tj-av22 before this finding artifact: passed
  - release-level stage-closeout dry-run before this finding artifact: passed
  - expired execution-guard read-only probe - old processing batch re-entered inner processing: failed invariant
  - durable-queue observability read-only probe - one raw list reported as zero queued jobs: failed invariant
changed_files:
  - .codex/stages/tj-av22/artifacts/tj-av22.10.md
explicit_defers:
  - tj-av22.3 - deployment live traffic production readback and rollback proof remain approval-gated
  - tj-15m - live latency matrix remains approval-gated
  - tj-rt42 - destructive workspace cleanup remains approval-gated
---

# Summary

**NEEDS WORK / NOT LOCALLY READY FOR PRODUCTION AUTHORIZATION.** The complete
stabilization range has one confirmed P1 replay defect and two P2 acceptance
gaps. The P1 blocks release. No P0 was found. Missing deploy, live-service,
production-readback, latency, and cleanup evidence remains separately
approval-gated rather than being counted as an implementation failure.

# Findings

## P1 — an expired execution guard replays a durable processing batch

- **Type:** implementation defect; `AC-2`; release-blocking.
- **Confidence:** high. Code inspection and a read-only focused probe reproduced
  the replay path.
- **Evidence:** the configuration permits
  `inbound_batch_quarantine_ttl_seconds=60` at
  `src/core/config.py:103-107`, while the ARQ job timeout is 600 seconds at
  `src/worker.py:143`. Both the `started` and `completed` execution markers use
  that quarantine TTL at `src/services/chat.py:324-346`. The durable processing
  list has no matching expiry or terminal tombstone at
  `src/services/chat.py:265-282`. If its marker is absent, recovery calls
  `_process_batch_inner` again at `src/services/chat.py:777-792`.
- **Reproduction:** with an existing processing-list item and no execution
  marker, `process_incoming_batch` invoked `_process_batch_inner` once. A second
  probe set the allowed TTL to 60 and observed the guard written with
  `ex=60`, versus the configured 600-second worker timeout.
- **Impact:** under an allowed configuration, the guard can expire while LLM,
  transcription, CRM, Inventory, Telegram, or Wazzup work is still in flight.
  A timeout or worker loss after an external side effect but before the
  completed marker then treats the retained batch as new and can repeat the
  side effect. Even at the seven-day default, an orphaned processing list
  recovered after marker expiry has the same replay path. This violates the
  no-duplicate-replay invariant.
- **Correction:** separate execution-marker retention from quarantine
  retention. Make the started lease safely exceed the complete worker/lock
  lifetime and keep a completed tombstone for at least as long as any durable
  processing copy can survive; preferably bind processing-list and execution
  state lifecycle atomically. Reject unsafe configuration values. Add
  regressions for an allowed minimum setting, worker timeout/loss after a
  provider side effect, and delayed recovery after completed-marker expiry.
- **Promotion target:** create or attach a P1 correction child under
  `tj-av22`/`tj-av22.3`, link this finding, and require an invariant test plus
  focused delta-review before release authorization.

## P2 — runtime monitoring misses orphaned durable inbound lists

- **Type:** implementation/compliance defect; `AC-6`.
- **Confidence:** high. The collector's inspected sources and a read-only probe
  agree.
- **Evidence:** accepted payloads are appended to privacy-safe
  `wazzup_msgs:<batch_ref>` lists before job enqueue at
  `src/api/v1/webhook.py:187-200`, and claimed work can remain in
  `wazzup:inbound:processing:<batch_ref>` at
  `src/services/chat.py:265-282`. Monitoring derives queue depth and oldest age
  only from `redis.queued_jobs()` at
  `src/services/runtime_monitoring.py:348-368`; its only list read is the OAuth
  failure history at `src/services/runtime_monitoring.py:338-346`.
- **Reproduction:** a fake Redis state containing one raw inbound list but no
  ARQ job produced `queue_depth=0` and `oldest_queue_age_seconds=None`; the
  collector inspected only `zoho:oauth:failures`.
- **Impact:** a crash or enqueue gap can leave an accepted batch in a live or
  processing list without an ARQ job, while `inbound_queue_backlog` and
  `inbound_queue_stalled` remain healthy. The runtime contract therefore does
  not observe every stalled accepted batch.
- **Correction:** persist bounded privacy-safe queue metadata (count and oldest
  accepted timestamp) atomically with the raw list and update it across
  claim/ack/quarantine, or maintain a bounded registry of active batch
  references. Monitor both live and processing state without logging keys,
  chat identifiers, or payloads. Add tests for raw-list-without-job and
  processing-list-without-job cases.
- **Promotion target:** a P2 observability correction under `tj-av22.1` or
  `tj-av22.3`, plus runbook wording that names both ARQ and durable-list sources.

## P2 — durable documentation still promises retired SaleOrder routes

- **Type:** compliance/documentation defect; `AC-8`.
- **Confidence:** high. Repository search found direct current-tense
  contradictions.
- **Evidence:** `docs/pdf-generation-research.md:16` says the application sends
  `POST /api/v1/inventory/sale-orders/`, and line 71 maps
  `create_quotation` to that public route. Current
  `src/api/v1/inventory.py:1-61` exposes only stock endpoints, with absence
  covered at `tests/test_api_inventory.py:90-114`.
  `docs/specs/zoho-integration/spec.md:6-9` separately says SaleOrder routes
  currently return `501`. The stage summary instead claims durable
  documentation is aligned and `AC-8` documentation passes at
  `.codex/stages/tj-av22/summary.md:123-124`.
- **Impact:** maintainers can integrate against an endpoint that has been
  intentionally removed, and the release evidence overstates the completeness
  of the public-contract documentation review.
- **Correction:** mark the research/spec sections as historical, or update them
  to the actual internal `ZohoInventoryClient`/quotation flow and explicit
  public-route retirement. Add a repository documentation assertion or bounded
  release search for retired routes and unsupported `501` claims.
- **Promotion target:** durable documentation correction attached to
  `tj-av22.2`/`tj-av22.3`; update the stage summary only after the contradiction
  is removed and re-reviewed.

# Verdicts

| Lens | Verdict | Reason |
| --- | --- | --- |
| Correctness / compliance | **NEEDS WORK** | One P1 replay defect and two P2 acceptance gaps remain. |
| Quality / improvement | **PASS WITH NOTES** | No additional independent quality-only finding was identified; the P2 observability and documentation corrections also improve operability and maintainability. |
| Overall release review | **NEEDS WORK / NOT LOCALLY READY FOR PRODUCTION AUTHORIZATION** | The P1 must be corrected and delta-reviewed before authorization. |

Finding count: `P0=0`, `P1=1`, `P2=2`, `P3=0`. There is no P0. The one P1
blocks release under `.codex/orchestrator.toml`.

# AC-1 Through AC-10 Coverage

| Criterion | Local review disposition | Approval-gated proof still missing |
| --- | --- | --- |
| `AC-1` | Local pass: public debug route is removed and regression-covered. | Deploy/readback; current production baseline still returns `200`. |
| `AC-2` | **Needs work:** OAuth parsing, owned locks, durable claim, quarantine, and ordinary replay tests pass, but execution-marker expiry permits duplicate replay. | Bounded deployed OAuth/inbound readback after the P1 correction. |
| `AC-3` | Local pass: exact manifest, classifier recheck, transaction rollback, and idempotency are covered. | Approved production dry-run/apply/readback only if the exact mutation is authorized. |
| `AC-4` | Local pass: conservative dry-run/apply, cron idempotency/readback restore, heartbeat, and health failure behavior are covered. | Approved installation/first-run/readback. |
| `AC-5` | Local pass: installed version, Redis/database probes, sanitized `503`, and `200` matrix pass. | Deploy/version/dependency readback; production remains on the old contract. |
| `AC-6` | **Needs work:** safe signals and cooldown behavior pass, but orphaned live/processing lists are invisible without an ARQ job. | Enablement and runtime readback remain approval-gated after correction. |
| `AC-7` | Local pass for bounded scope: privacy-safe phases and summary-after-text ordering are covered without quality-regression evidence loss. | Approved live scenario matrix for p50/p95/max or named provider blocker. |
| `AC-8` | **Needs work:** code/OpenAPI route retirement passes, but two durable docs contradict it. | Deploy/readback of retired routes after documentation correction. |
| `AC-9` | Local pass: Beads contains the exact nine-worktree inventory, handoff is current, inbox/process checks pass, and no destructive cleanup occurred. | Exact cleanup/final inventory only after destructive approval. |
| `AC-10` | Local canonical evidence, process verification, stage-ready check, deploy backup path, manual rollback procedure, and release closeout dry-run are present. Overall acceptance is blocked by this P1. | Merge/push, green CI, deployed SHA/version, smoke/readback, live E2E, and rollback evidence. |

# Approval-Gated Production Proof Is Not A Local Defect

No deploy, production mutation, live OAuth/provider call, real
Telegram/WhatsApp message, reconciliation apply, cron installation, or
destructive cleanup was performed. The current production debug/health state,
live latency targets, release SHA/readback, and exercised rollback remain
missing because they require explicit authorization. Those missing proofs are
not counted as additional findings; they remain blockers owned by
`tj-av22.3`, `tj-15m`, and `tj-rt42`.

# Scope / Routing

The review covered the full non-merge history and 94-file diff from
`main@89f9a560071302d16f53704870e7a508e9d05f28` through
`codex/tj-av22-stabilization@75d610de4bcfd12ba952b9f80b00fe2a98256c8e`.
It inspected the approved design/plan, stage manifest and summary, prior
review/correction/documentation artifacts, Beads release/latency/cleanup state,
implementation, tests, deploy/rollback scripts, CI, and durable documentation.

No dependency documentation lookup was decision-critical. Graphify is not
configured. The only repository write is this artifact.

# Verification

- `git diff --check 89f9a560071302d16f53704870e7a508e9d05f28...HEAD`:
  passed.
- Focused 20-file AC/release pytest matrix: `517 passed in 8.30s`.
- `uv run ruff check src/ tests/`: passed.
- `uv run ruff format --check src/ tests/`: passed (`300 files already
  formatted`).
- `uv run mypy src/`: passed (`162 source files`).
- `scripts/orchestration/run_process_verification.sh`: passed.
- `python3 scripts/orchestration/check_stage_ready.py tj-av22`: passed before
  this finding artifact existed.
- `python3 scripts/orchestration/run_stage_closeout.py --stage tj-av22 --level
  release --dry-run`: passed before this finding artifact and selected release,
  integration, concurrency, security, PostgreSQL, and process groups.
- Execution-guard probe: failed the invariant as described in P1.
- Durable-list monitoring probe: failed the invariant as described in P2.

The prior fresh full-suite evidence (`1509 passed, 19 skipped`) and release
static gates were audited in the stage summary and commit history rather than
duplicated wholesale. The focused probes used only dummy local configuration
and mocks; they contacted no external service.

# Significant Finding Capture

| Finding | Implication | Confidence | Next action | Promotion target |
| --- | --- | --- | --- | --- |
| Expired guard replays processing batch | Duplicate external side effects remain possible; release blocked. | High | Correct TTL/lifecycle, add invariant tests, run focused delta-review. | P1 Beads correction under `tj-av22`/`tj-av22.3`. |
| Durable lists invisible to monitoring | Accepted stalled work can appear healthy. | High | Add privacy-safe live/processing metadata and tests. | P2 under `tj-av22.1` or `tj-av22.3`, plus runbook. |
| Retired routes remain in durable docs | AC-8 documentation proof is overstated. | High | Correct or mark historical, then rerun bounded docs search. | `tj-av22.2`/`tj-av22.3` and durable docs. |

The strict write zone prohibited Beads or existing-document mutation. The root
orchestrator should promote the accepted findings before correction work.

# Positive Patterns

- Raw Redis debug access is removed and health failure detail is sanitized.
- OAuth parsing and owner-token lock release close the original malformed-200
  and stale-owner races.
- Escalation apply is classifier-limited, exact-ID, transactional, and
  idempotent.
- Maintenance defaults are conservative, heartbeat topology is explicit, and
  deploy preserves runtime state.
- Inbound raw payloads stay out of logs; quarantine is bounded; prior
  cancellation/voice replay findings have focused regressions.
- Local latency evidence clearly avoids claiming unperformed live results.

# Risks / Follow-ups

- Correct the execution-marker/processing-list lifecycle first and require a
  focused invariant test plus delta-review before any production authorization.
- Correct durable-list observability and the two stale route documents before
  restating `AC-6` or `AC-8` as complete.
- Keep production deployment/readback, live latency, reconciliation apply,
  maintenance installation, external messaging, rollback exercise, and
  destructive cleanup behind their existing explicit approval gates.
- Root-orchestrator must register this returned v3 artifact in
  `stage-manifest.json` when accepting it; that file is outside this stream's
  strict write zone.

# Delivery / Cleanup

The artifact is returned on `codex/tj-av22-review-pass` for root triage. This
reviewer did not accept or close the stage, modify Beads, change implementation,
push, deploy, contact production, or perform cleanup.

- `docs-reviewed: needs-work` — exact contradictions are the third finding.
- `graph-reviewed: no-change-needed` — Graphify is not configured and
  `graphify-out/GRAPH_REPORT.md` is absent.
- E2E/smoke: deterministic local coverage was included in the focused matrix;
  production/live smoke remains explicitly approval-gated.
