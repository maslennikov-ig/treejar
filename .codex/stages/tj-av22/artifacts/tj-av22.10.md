---
schema_version: orchestration-artifact/v3
artifact_type: review-report
stage_manifest: .codex/stages/tj-av22/stage-manifest.json
stream_owner: combined-release-reviewer
orchestration_level: release
scope_kind: product_slice
immediate_consumer: root-orchestrator
public_facade: n/a
bounded_acceptance: independent release review and correction delta review of the Noor stabilization range through 82a2bdb against AC-1 through AC-10
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
milestone_status: accepted
agent_type: reviewer
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: independent high-risk release review across security retry idempotency observability public API deploy rollback and durable documentation
repo: treejar
branch: codex/tj-av22-review-pass
base_branch: codex/tj-av22-stabilization
base_commit: 82a2bdb8897d845001e2b3b098a0c2032ae9f4d1
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
delivery_method: merge
accepted_by_orchestrator: yes
cleanup_status: blocked
cleanup_notes: root accepted and integrated the delta review; deleting the isolated review worktree remains explicitly approval-gated
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
docs_reviewed: updated
docs_review_notes: correction range marks the two historical documents accurately and removes current-tense promises of retired public SaleOrder routes
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
  - git diff --check 402ee45..82a2bdb: passed
  - correction delta matrix - 395 passed: passed
  - correction changed-file Ruff check: passed
  - correction changed-file Ruff format check - 4 files: passed
  - correction changed-source Mypy check - 2 files: passed
  - correction process verification: passed
  - bounded retired-route documentation search: passed
changed_files:
  - .codex/stages/tj-av22/artifacts/tj-av22.10.md
explicit_defers:
  - tj-av22.3 - deployment live traffic production readback and rollback proof remain approval-gated
  - tj-15m - live latency matrix remains approval-gated
  - tj-rt42 - destructive workspace cleanup remains approval-gated
---

# Summary

**PASS / LOCALLY RELEASE-READY.** Correction commits `cc22972` and `82a2bdb`
resolve the original P1 replay defect and both P2 acceptance gaps. The final
atomic transition was necessary: the first correction still expired a guard
before deleting its durable processing copy, while `82a2bdb` removes the copy
and starts terminal retention in one Redis script. No active P0/P1/P2/P3
finding remains. Deploy, live-service, production-readback, latency, and
cleanup evidence remains separately approval-gated rather than being counted
as a local defect.

# Correction Delta Review (`402ee45..82a2bdb`)

## Original P1 — resolved

- **Disposition:** resolved; no release-blocking P1 remains.
- **Evidence:** a `started` guard is now persisted without TTL before side
  effects at `src/services/chat.py:328-342`, and completion is also persistent
  until finalization at `src/services/chat.py:345-349`. The Lua transition at
  `src/services/chat.py:102-105` atomically deletes the processing list and
  starts the bounded guard TTL; both quarantine and successful acknowledgment
  use it at `src/services/chat.py:860-889`.
- **Failure-boundary review:** `cc22972` alone was insufficient because its
  terminal branch set `EXPIRE` before failure recording and processing-list
  deletion. A crash in that interval could still leave a recoverable list whose
  guard later disappeared. Follow-up `82a2bdb` removes that inter-command
  window. If quarantine, failure recording, or the Lua call fails before
  execution, both the durable copy and persistent guard remain recoverable; if
  the Lua call executes, Redis applies deletion and expiry atomically.
- **Regression evidence:** `tests/test_services_chat_batch.py:92-119` asserts
  non-expiring started/completed guards before terminal state, and
  `tests/test_services_chat_batch.py:330-393` verifies completed and uncertain
  replay paths use the single finalization call without replaying inner work.

## Original AC-6 P2 — resolved

- **Disposition:** resolved for local acceptance; production enablement/readback
  remains approval-gated.
- **Evidence:** monitoring scans only the two durable inbound key patterns at
  `src/services/runtime_monitoring.py:27-30`, reads `OBJECT IDLETIME` before
  `LLEN` without reading values at
  `src/services/runtime_monitoring.py:290-325`, and combines durable and ARQ
  depth/age at `src/services/runtime_monitoring.py:390-419`. Reading idle time
  first prevents the length read from masking the observed age.
- **Regression evidence:** the parameterized orphan test covers both
  `wazzup_msgs:*` and `wazzup:inbound:processing:*`, no ARQ job, nonzero depth,
  stale age, and the idle-before-length behavior at
  `tests/test_runtime_monitoring.py:204-255`. The runbook accurately names both
  sources and the payload-free method at `docs/operations-runbook.md:160-172`.

## Original AC-8 P2 — resolved

- **Disposition:** resolved.
- **Evidence:** `docs/pdf-generation-research.md:3-6,20-23,75-82` marks the
  document historical and maps quotation creation to the internal
  `ZohoInventoryClient.create_sale_order()` flow.
  `docs/specs/zoho-integration/spec.md:3-14` likewise states that the public
  SaleOrder routes were retired while stock routes remain. A bounded search
  found only explicit statements that `/api/v1/inventory/sale-orders/*` is
  removed, not a current-tense promise that it exists or returns `501`.

## Delta finding count and verdict

No genuinely new delta finding was identified. Active finding count:
`P0=0`, `P1=0`, `P2=0`, `P3=0`. Local correction verdict: **PASS**.

# Original Findings (Historical Record)

## P1 — an expired execution guard replays a durable processing batch — RESOLVED

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
- **Correction result:** resolved by `tj-av22.11` in `cc22972` plus the atomic
  terminal transition in `82a2bdb`; see the correction delta above.

## P2 — runtime monitoring misses orphaned durable inbound lists — RESOLVED

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
- **Correction result:** resolved by `tj-av22.12` in `cc22972`; see the
  correction delta above.

## P2 — durable documentation still promises retired SaleOrder routes — RESOLVED

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
- **Correction result:** resolved by `tj-av22.13` in `cc22972`; see the
  correction delta above.

# Verdicts

| Lens | Verdict | Reason |
| --- | --- | --- |
| Correctness / compliance | **PASS** | Atomic guard finalization closes the replay/retention window; durable-list monitoring and route documentation now meet the reviewed local contract. |
| Quality / improvement | **PASS** | Focused regressions cover both durable key families, idle-read ordering, and terminal finalization; no new delta finding was identified. |
| Overall release review | **PASS / LOCALLY RELEASE-READY** | No active P0/P1/P2/P3 remains; approval-gated live proof is still required before production claims. |

Active finding count: `P0=0`, `P1=0`, `P2=0`, `P3=0`. The historical count
before correction was `P0=0`, `P1=1`, `P2=2`, `P3=0`.

# AC-1 Through AC-10 Coverage

| Criterion | Local review disposition | Approval-gated proof still missing |
| --- | --- | --- |
| `AC-1` | Local pass: public debug route is removed and regression-covered. | Deploy/readback; current production baseline still returns `200`. |
| `AC-2` | Local pass: OAuth parsing, owned locks, durable claim, quarantine, replay handling, persistent active guards, and atomic bounded terminal finalization pass. | Bounded deployed OAuth/inbound readback. |
| `AC-3` | Local pass: exact manifest, classifier recheck, transaction rollback, and idempotency are covered. | Approved production dry-run/apply/readback only if the exact mutation is authorized. |
| `AC-4` | Local pass: conservative dry-run/apply, cron idempotency/readback restore, heartbeat, and health failure behavior are covered. | Approved installation/first-run/readback. |
| `AC-5` | Local pass: installed version, Redis/database probes, sanitized `503`, and `200` matrix pass. | Deploy/version/dependency readback; production remains on the old contract. |
| `AC-6` | Local pass: safe signals/cooldown pass, and orphaned live/processing lists contribute payload-free depth and age without an ARQ job. | Enablement and runtime readback remain approval-gated. |
| `AC-7` | Local pass for bounded scope: privacy-safe phases and summary-after-text ordering are covered without quality-regression evidence loss. | Approved live scenario matrix for p50/p95/max or named provider blocker. |
| `AC-8` | Local pass: code/OpenAPI route retirement and durable documentation agree on the internal quotation flow and retired public routes. | Deploy/readback of retired routes. |
| `AC-9` | Local pass: Beads contains the exact nine-worktree inventory, handoff is current, inbox/process checks pass, and no destructive cleanup occurred. | Exact cleanup/final inventory only after destructive approval. |
| `AC-10` | Local canonical evidence, current correction verification, process verification, prior stage-ready check, deploy backup path, manual rollback procedure, and release closeout dry-run are present. Local review no longer has a finding blocker. | Merge/push, green CI, deployed SHA/version, smoke/readback, live E2E, and rollback evidence. |

# Approval-Gated Production Proof Is Not A Local Defect

No deploy, production mutation, live OAuth/provider call, real
Telegram/WhatsApp message, reconciliation apply, cron installation, or
destructive cleanup was performed. The current production debug/health state,
live latency targets, release SHA/readback, and exercised rollback remain
missing because they require explicit authorization. Those missing proofs are
not counted as additional findings; they remain blockers owned by
`tj-av22.3`, `tj-15m`, and `tj-rt42`.

# Scope / Routing

The review covered the full non-merge history from
`main@89f9a560071302d16f53704870e7a508e9d05f28` through the correction head
`codex/tj-av22-stabilization@82a2bdb8897d845001e2b3b098a0c2032ae9f4d1`.
It inspected the approved design/plan, stage manifest and summary, prior
review/correction/documentation artifacts, Beads release/latency/cleanup state,
implementation, tests, deploy/rollback scripts, CI, and durable documentation.

No dependency documentation lookup was decision-critical. Graphify is not
configured. The only repository write is this artifact.

# Verification

- Correction range `402ee45..82a2bdb`:
  - `git diff --check 402ee45..82a2bdb`: passed.
  - Focused correction/release matrix across chat batch, runtime monitoring,
    worker, webhook, inventory API, and LLM engine: `395 passed in 5.24s`.
  - `uv run ruff check` on the two changed source and two changed test files:
    passed.
  - `uv run ruff format --check` on the same four files: passed
    (`4 files already formatted`).
  - `uv run mypy src/services/chat.py src/services/runtime_monitoring.py`:
    passed.
  - `scripts/orchestration/run_process_verification.sh`: passed.
  - Bounded documentation search: no current-tense promise of the retired
    public SaleOrder routes or SaleOrder `501` behavior.
- The first correction `cc22972` was inspected independently and found to leave
  an ordering window in the terminal branch. The final verdict therefore relies
  on the atomic follow-up `82a2bdb`, not on the earlier commit message.
- No production, external service, live traffic, deploy, cleanup, or remote
  action was performed.

Historical pre-correction verification:

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
| Expired guard replays processing batch | **Resolved:** persistent active guard plus atomic processing deletion/terminal expiry. | High | Keep the focused regressions in release gates. | `tj-av22.11`; corrected in `cc22972`/`82a2bdb`. |
| Durable lists invisible to monitoring | **Resolved:** both durable list families contribute payload-free depth and age. | High | Validate signal readback after approved enablement. | `tj-av22.12`; corrected in `cc22972`. |
| Retired routes remain in durable docs | **Resolved:** historical status and internal client flow are explicit. | High | Keep the bounded retired-route search in documentation review. | `tj-av22.13`; corrected in `cc22972`. |

The strict write zone prohibited Beads, implementation, test, or durable
document mutation by this reviewer. The root orchestrator promoted and
corrected all three findings before this delta review.

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

- Preserve atomic processing deletion/terminal guard retention and the focused
  replay tests in future inbound changes.
- Treat durable-key idle age as an operational stall signal and validate its
  threshold behavior during the approval-gated production readback.
- Keep production deployment/readback, live latency, reconciliation apply,
  maintenance installation, external messaging, rollback exercise, and
  destructive cleanup behind their existing explicit approval gates.
- Root-orchestrator must accept the amended artifact and retain its existing
  stage-manifest registration; that file is outside this stream's strict write
  zone.

# Delivery / Cleanup

The amended artifact is returned on `codex/tj-av22-review-pass` for root
acceptance. This reviewer did not close the stage, modify Beads, change
implementation/tests/durable docs, push, deploy, contact production, or perform
cleanup.

- `docs-reviewed: updated` — `cc22972` corrects both durable route documents,
  and the bounded search found no remaining current-tense promise.
- `graph-reviewed: no-change-needed` — Graphify is not configured and
  `graphify-out/GRAPH_REPORT.md` is absent.
- E2E/smoke: deterministic local coverage was included in the focused matrix;
  production/live smoke remains explicitly approval-gated.
