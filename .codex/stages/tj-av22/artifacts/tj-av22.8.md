---
schema_version: orchestration-artifact/v3
artifact_type: review-report
stage_manifest: .codex/stages/tj-av22/stage-manifest.json
stream_owner: docs-reviewer
orchestration_level: integration
scope_kind: product_slice
immediate_consumer: root-orchestrator
public_facade: n/a
bounded_acceptance: durable stabilization documentation and release-truth review
non_goals:
  - project or documentation edits
  - production or external-service checks
  - transient stage history copied into durable guides
evidence:
  - none
task_id: tj-av22.8
epic_id: tj-av22
stage_id: tj-av22
session_id: tj-av22-docs-review
milestone: noor-stabilization-documentation-review
milestone_status: replan-required
agent_type: worker
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: cross-contract review of public API, recovery, privacy, operations, and release boundaries
repo: treejar
branch: codex/tj-av22-docs-review
base_branch: codex/tj-av22-stabilization
base_commit: 3cf59b540f206102341ba16f4d11401a27d18b85
worktree: /home/me/code/treejar/.worktrees/tj-av22-docs-review
write_zone:
  - .codex/stages/tj-av22/artifacts/tj-av22.8.md
success_criteria:
  - changed stabilization contracts are checked against current code
  - stale durable documentation has exact references and suggested corrections
  - release rollback recovery and approval boundaries remain explicit
selected_docs:
  - AGENTS.md
  - .codex/orchestrator.toml
  - .codex/handoff.md
  - README.md
  - docs/admin-guide.md
  - docs/dev-guide.md
  - docs/operations-runbook.md
  - docs/architecture.md
  - docs/latency-evidence.md
  - docs/superpowers/specs/2026-07-23-noor-stabilization-design.md
  - docs/superpowers/plans/2026-07-23-noor-stabilization.md
selected_skills:
  - verification-before-completion
selected_agents:
  - docs-reviewer
catalog_candidates:
  - none
parallel_group: final-review
depends_on_streams:
  - api-health
  - zoho-inbound
  - ops
  - runtime-observability
  - latency
  - correction-review
parallel_decision: parallel
status: returned
delivery_method: merge
accepted_by_orchestrator: yes
cleanup_status: pending
cleanup_notes: read-only review worktree retained for root-orchestrator inspection
risk_level: high
verification_tier: integration
risk_tags:
  - public-api
  - rollback
  - security
affected_surfaces:
  - api
  - backend
invariants:
  - rollback
  - test-matrix
docs_impact: docs-only
docs_reviewed: needs-work
docs_review_notes: durable health deployment recovery and latency guidance remains stale
graph_reviewed: no-change-needed
graph_review_notes: Graphify is not configured and graphify-out/GRAPH_REPORT.md is absent
verification:
  - integrated diff and durable-doc contract inspection: passed
  - current OpenAPI removed-route inspection with local test configuration: passed
  - python3 scripts/orchestration/validate_artifact.py artifact: passed
  - git diff --check: passed
changed_files:
  - .codex/stages/tj-av22/artifacts/tj-av22.8.md
explicit_defers:
  - tj-av22.3 - deployment production readback alert delivery reconciliation apply cron installation and live latency matrix remain approval-gated
  - tj-av22.3 - durable documentation corrections below must be made and reviewed before release closeout
---

# Findings

No P0 documentation defect was identified. The documentation verdict is
**NEEDS WORK** because the general developer and administrator guides still
contradict current release, health, recovery, and latency contracts.

## P1 — the developer guide tells operators to deploy from a live git checkout

- **Evidence:** `docs/dev-guide.md:342-367` instructs an operator to SSH to the
  server, run `git pull origin main`, rebuild directly, and then run migrations.
  The actual delivery path packages a release archive with `.release-sha` and
  `.release-run-id` and invokes `scripts/vps-deploy.sh` from
  `.github/workflows/ci.yml:127-174`. The deploy script stages and backs up the
  release, preserves runtime state, rebuilds Compose, and verifies health at
  `scripts/vps-deploy.sh:113-188`. `docs/admin-guide.md:269-288` correctly says
  that `/opt/noor` is not a git checkout and documents archive rollback.
- **Impact:** following the developer guide can bypass release identity,
  backup/readback behavior, and the established approval boundary. It also
  cannot work reliably against the canonical artifact-based runtime.
- **Suggested correction:** replace `docs/dev-guide.md:342-367` with the actual
  main-only CI contract: an approved push or manual dispatch runs Ruff, format,
  Mypy, and pytest; packages the commit plus release metadata; and deploys it
  through `scripts/vps-deploy.sh`. State explicitly that deploy and rollback
  require current approval, that no `git pull` is performed on the VPS, and
  link to `docs/admin-guide.md:269-288` for exact archive rollback. In
  `docs/admin-guide.md:222-233`, mark production restarts/rebuilds as
  approval-gated operational mutations and distinguish a service restart from
  establishing a new release.

## P1 — the documented health contract omits Redis and failure semantics

- **Evidence:** `docs/admin-guide.md:174-180` says the endpoint returns only
  `{"status": "ok"}` when the app and database are reachable. Current
  `src/api/v1/health.py:30-83` probes both Redis and PostgreSQL, returns package
  `version` plus structured `dependencies`, and sets HTTP `503` with
  `status="degraded"` when either required dependency fails. Failure messages
  are sanitized to `unavailable`. `tests/test_api_health.py:45-84` covers the
  healthy, Redis-failed, database-failed, and simultaneous-failure matrix.
- **Impact:** an operator cannot interpret maintenance/deploy health failure
  correctly from the guide and may mistake a Redis outage for a successful app
  check or look for sensitive dependency details that are intentionally
  withheld.
- **Suggested correction:** update `docs/admin-guide.md:174-180` with the
  response fields (`status`, installed-package `version`, `redis`, and
  `database` dependency entries), HTTP `200` only when both dependencies are
  healthy, and sanitized HTTP `503` otherwise. Note that
  `/api/v1/debug/redis` is intentionally absent; raw queue payloads are not a
  supported troubleshooting surface.

## P2 — recovery guidance names a nonexistent shared Zoho credential

- **Evidence:** `docs/admin-guide.md:214-220` tells operators to check
  `ZOHO_REFRESH_TOKEN`. The runtime has separate
  `ZOHO_CRM_REFRESH_TOKEN` and `ZOHO_INVENTORY_REFRESH_TOKEN` contracts in
  `.env.example:43-55` and `src/core/config.py:62-74`; the corrected lock
  behavior is already accurately summarized in `docs/dev-guide.md:429-432`.
- **Impact:** the stated recovery step cannot diagnose the failing integration
  and encourages credential regeneration without first identifying the
  sanitized OAuth failure class or the affected account.
- **Suggested correction:** replace the shared name with the two exact
  service-specific variables, tell the operator to inspect the sanitized
  `zoho_oauth_failed` signal/error class first, and state that token
  regeneration or scope changes require owner approval.

## P2 — slow-response guidance bypasses the new latency evidence path

- **Evidence:** `docs/admin-guide.md:214-220` recommends checking container
  resources and then restarting `app`. Inbound dialogue work runs in the ARQ
  worker, while `docs/latency-evidence.md:7-103` records that the dominant
  warmed bucket is the external model/tool path, defines the privacy-safe
  `noor_chat_latency` schema and analyzer, and explicitly leaves production
  targets to an approved live matrix. Current latency events contain no
  customer text, phone, conversation ID, credential, or arbitrary field.
- **Impact:** a restart can interrupt work without producing bottleneck
  evidence and cannot establish that the stabilization latency targets were
  met.
- **Suggested correction:** replace the `Slow responses` row with worker-log
  collection and the exact analyzer command from
  `docs/latency-evidence.md:82-87`, followed by resource inspection only when
  the measured phase supports it. Link the evidence note and retain its
  boundary: local controlled measurements are not production latency, and the
  live matrix remains separately approval-gated.

## P2 — README carries an unmaintainable API endpoint count

- **Evidence:** `README.md:59-62` labels `src/api/v1/` as having 25 endpoints.
  Current locally generated OpenAPI contains 73 paths and 89 HTTP operations.
  The four retired routes are correctly absent from OpenAPI and correctly
  described in `docs/architecture.md:207-229` and
  `docs/task-plan.md:120-124`.
- **Impact:** the count makes the high-level repository map false even though
  the durable API contract documentation correctly records the stabilization
  removals.
- **Suggested correction:** remove the hard-coded count and describe the
  directory simply as FastAPI v1 routes. Do not add a stabilization changelog
  to README; route inventory belongs in generated OpenAPI and
  `docs/architecture.md`.

# Coverage

- **API removals:** current code/tests and OpenAPI confirm that
  `/api/v1/debug/redis`, both public Inventory SaleOrder stubs, and
  `/api/v1/quality/reports/` are absent. Architecture/task-plan wording is
  accurate; only README's aggregate count is stale.
- **Health:** code is truthful and sanitized, but the admin guide is stale as
  described above.
- **Inbound retry, quarantine, and privacy:** `docs/operations-runbook.md:158-184`
  matches the three-attempt bounded retry, stable quarantine key, seven-day TTL,
  bounded sanitized failure history, queue restoration on quarantine failure,
  and exact approval for inspection/replay. Current webhook/chat lifecycle logs
  use bounded types and hashed references rather than customer content.
- **Monitoring:** `docs/operations-runbook.md:158-225` matches the disabled
  default, five-minute ARQ schedule, thresholds, structured-log behavior,
  Telegram opt-in, and delivery-aware cooldown release.
- **Maintenance:** `docs/operations-runbook.md:86-156` matches conservative
  preview/apply, idempotent cron installation, atomic heartbeat, read-only
  worker mount, health readback, and the non-reversible cleanup boundary.
- **Escalation reconciliation:** `docs/operations-runbook.md:9-84` matches
  privacy-safe audit, classifier-limited exact actions, locked reclassification,
  transactional apply, repeat-run idempotency, and separate approved recovery.
- **Latency:** `docs/latency-evidence.md` accurately separates historical,
  controlled-local, and still-missing production evidence. It should be linked
  from incident guidance, not copied as transient measurements into README.
- **Release, rollback, and approvals:** the admin rollback and operations
  approval boundaries are accurate; the developer deploy path and general
  restart wording require the corrections above.

# Documentation Verdict

- `docs-reviewed: needs-work` — exact durable-doc corrections are listed above;
  no project documentation was edited by this read-only reviewer.
- `graph-reviewed: no-change-needed` — Graphify is not configured and
  `graphify-out/GRAPH_REPORT.md` is absent, so no graph query or refresh applies.
- Transient implementation history should remain in the stage artifacts,
  stabilization spec/plan, and latency evidence note. The suggested durable
  edits describe current contracts and operator decisions only.

# Summary

The stabilization-specific runbook, architecture note, task-plan route
decisions, and latency evidence are materially aligned with current code.
Release closeout is not documentation-ready because the broader administrator
and developer guides still direct operators toward obsolete deployment,
incomplete health interpretation, incorrect Zoho recovery, and unmeasured
latency remediation. These are bounded documentation corrections; they do not
require product-policy or production-state guesses.

# Scope / Routing

The review covered the integrated diff from
`main@89f9a560071302d16f53704870e7a508e9d05f28` through
`codex/tj-av22-stabilization@3cf59b540f206102341ba16f4d11401a27d18b85`,
the assigned durable docs, current implementation/tests, stage artifacts, and
Beads `tj-av22`/`tj-av22.8`. Repository contracts were sufficient; no external
documentation, production access, API call, credential change, Beads update, or
project-doc edit was needed.

# Verification

- Inspected the integrated changed-file set and current code for every assigned
  contract.
- Generated current OpenAPI locally with a non-secret test configuration:
  73 paths, 89 operations, and all four retired routes absent.
- Artifact validation and final diff/status checks are recorded after the
  artifact is finalized.

# Delivery / Cleanup

This review artifact is returned on `codex/tj-av22-docs-review` for
root-orchestrator triage. It does not accept, merge, deploy, or mutate
documentation/runtime state. The isolated worktree remains available for
review.

# Risks / Follow-ups / Explicit Defers

The root orchestrator should route the five bounded documentation corrections
before release closeout and re-review only those durable-doc edits. All
production evidence remains with `tj-av22.3`: deployment and release readback,
debug-route absence, Redis+DB health, inbound/OAuth recovery, escalation apply,
cron/heartbeat, optional Telegram delivery, and the live latency matrix. No
production outcome is inferred from local code or historical notes.
