# Stage tj-av22 Summary

Updated: 2026-07-23
Status: accepted and closed; bounded operational follow-ups remain separately approval-gated
Branch: `main`
Base: `main@89f9a560071302d16f53704870e7a508e9d05f28`
Planning commit: `9ee579b5391edf82d5fac9d70bc5c28c2116a40d`
Beads: `tj-av22`

## Cohesive Boundary

One production-stabilization acceptance boundary covers the audit's security,
reliability, operational, observability, latency, API-contract, repository, and
release evidence. The work converges on one Noor release and rollback boundary.
No scope split or preservation ledger is active.

## Scope Ledger State

- Goal anchor:
  `.codex/goals/tj-av22/scope-criterion-snapshot.json`
- Stage manifest:
  `.codex/stages/tj-av22/stage-manifest.json`
- Scope ledger: `none`
- Criteria: `AC-1` through `AC-10`, exact-set bound to the goal anchor

## Routing Result

- Documentation: first-party Zoho OAuth documentation for the token contract;
  repository contracts for all other initial work.
- Knowledge Graph: not configured; no Graphify hooks or refresh.
- Selected skills: `orchestrator-stage`, `task-router`,
  `systematic-debugging`, `test-driven-development`,
  `verification-before-completion`, `orchestration-closeout`.
- Candidate agents/personas: implementation worker for isolated changes;
  targeted correctness/security reviewer at the integration boundary.
- Catalog candidates: none; installed workflows cover the stage.

## Delivered

- Removed the unauthenticated Redis debug surface and made health report the
  installed version plus required Redis/PostgreSQL state with sanitized `503`
  degradation.
- Added typed Zoho OAuth parsing, owner-safe refresh locks, bounded failure
  handling, and privacy-safe operational records.
- Replaced destructive inbound `LPOP` processing with an immutable durable
  processing list, an owner-token lease longer than the worker timeout, and a
  started/completed replay guard. Active guards remain persistent while a
  durable copy exists; Redis atomically removes that copy and bounds terminal
  retention. Uncertain post-side-effect recovery is quarantined instead of
  replayed.
- Added exact-ID, classifier-limited, transactional escalation reconciliation
  and conservative Docker maintenance/cron/heartbeat tooling. Production apply
  remains approval-gated.
- Added privacy-safe runtime monitoring, including orphaned live/processing
  inbound lists without reading payloads, and delivery-aware optional Telegram
  cooldown behavior.
- Added bounded latency phase evidence and moved summary enqueue work after
  customer-facing text delivery. Controlled local evidence does not claim live
  latency targets.
- Retired the never-functional public SaleOrder and quality-report routes with
  contract tests and documentation.
- Aligned durable release, health, Zoho recovery, latency, and inbound recovery
  documentation with the current implementation.

## Parallel Decomposition Matrix

| Stream | Goal | Agent | Write zone | Dependencies | Verification | Decision | Reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| API | Close debug exposure and make health truthful | worker candidate | API health/schema/tests | shared health route | focused API tests | evaluate | Coherent shared API boundary |
| OAuth | Make token refresh and inbound batch failure safe | worker candidate | Zoho clients, chat/worker tests | first-party OAuth contract | Zoho/batch tests | evaluate | High-risk isolated context |
| Ops | Add safe escalation/maintenance controls | worker candidate | escalation and maintenance scripts/tests | no production apply | focused script/state tests | evaluate | Disjoint local write zone |
| Runtime | Add visibility and improve measured latency | root or later worker | worker/chat/LLM/monitoring tests | integrate adjacent contracts first | focused plus quality tests | sequential | Shared instrumentation and quality proof |
| Contracts | Resolve public `501` routes | root or worker | inventory/quality API/tests/docs | consumer evidence | API contract tests | evaluate | Stop if compatibility is ambiguous |
| Closeout | Integrate, review, verify, and prepare release | root | stage, Beads, docs, integration branch | accepted implementation | canonical gates | sequential | Single acceptance and rollback owner |

## Verification

- Initial clean baseline after orchestration guardrail repair:
  - `scripts/orchestration/run_process_verification.sh`: passed
  - `uv run ruff check src/ tests/`: passed
  - `uv run ruff format --check src/ tests/`: passed
  - `uv run mypy src/`: passed
  - `uv run pytest tests/ -q --tb=short`: `1431 passed, 19 skipped`
- Integrated pre-review gate at `3cf59b5`:
  - process verification, Ruff, format, and Mypy: passed
  - full pytest: `1499 passed, 19 skipped`
- Post-correction root gate after `fb52643`:
  - focused audio/inbound/webhook/worker matrix: `61 passed`
  - process verification, Ruff, format, and Mypy: passed
  - full pytest: `1507 passed, 19 skipped`
- Internal-ready orchestration gate:
  - process-verification tests: `8 passed`
  - release-level stage-closeout dry-run: passed
  - the contract now defines every risk-based verification group and points to
    the exact `tj-av22` stage summary; regression tests cover both invariants
  - final canonical static gates: Ruff, format, and Mypy passed
  - final full pytest with pytest 9 deprecation warnings promoted to errors:
    `1509 passed, 19 skipped`
  - the global database-pool teardown no longer exposes sync tests to an
    unsupported async autouse fixture
- Independent review artifacts `tj-av22.5`, `tj-av22.7`, and `tj-av22.8`
  were accepted as findings reports. Their implementation and documentation
  corrections are integrated. Final correction review `tj-av22.9` passed after
  the audio-transcription guard correction; the branch is locally
  release-ready.
- Explicit combined release review `tj-av22.10` initially found one P1 replay
  lifecycle defect and two P2 acceptance gaps. Corrections `cc22972` and
  `82a2bdb` were independently delta-reviewed: `395 passed`, active
  `P0/P1/P2/P3=0`, verdict `PASS / LOCALLY RELEASE-READY`.
- Fresh root gate after the accepted delta:
  - focused inbound/runtime/worker/webhook matrix: `67 passed`
  - Ruff, format (`300 files`), Mypy (`162 source files`), process verification,
    and diff-check: passed
  - full pytest: `1513 passed, 19 skipped`
- Accepted-stage closeout after the final process-check correction:
  - binary untracked PDF/PNG files no longer produce false debt-marker
    findings; the focused regression first failed on the old scanner and then
    passed with all `9` process-verification tests
  - final release gate: Ruff passed, format passed (`300 files`), Mypy passed
    (`162 source files`), and full pytest passed (`1514 passed, 19 skipped`)
  - integration `132`, concurrency `96`, security `22`, and PostgreSQL `13`
    test groups passed
  - `check_stage_ready`, process verification, debt scan, review finding
    reconciliation, and non-dry-run release closeout passed
- Pre-delivery production/CI baseline:
  - `https://noor.starec.ai/api/v1/health` still reports version `0.1.0` and
    only Redis dependency state
  - `/api/v1/debug/redis` still returns HTTP `200`; its body was discarded
  - GitHub Actions run `30002801189` for `main@89f9a560` failed in four
    orchestration-runtime tests covering tomllib bootstrap and mandatory stage
    artifacts; lint and Mypy passed, and deploy was skipped
  - commits `e0b7ca8` and `00ec0cf` contain the root corrections; the integration
    branch passes the expanded process suite and full canonical local gate
- Delivery and production proof:
  - `main` fast-forwarded to
    `2213a06800a156f6d511af26072ea17f16178ef2` and ordinary push succeeded
  - GitHub Actions run `30028216974` passed changes, lint, type-check, tests,
    and deploy; deploy job `89278412590` activated the exact release SHA
  - the deploy created rollback backup
    `deploy-20260723T171150Z-from-6df39c72ef6d4b79de67b58a9c6f29a7771293ab.tar.gz`
  - production health returns `200`, version `0.4.0`, Redis `ok`, and database
    `ok`
  - `/api/v1/debug/redis` and the retired SaleOrder read route return `404`;
    anonymous conversations access returns `403`
  - production OpenAPI does not contain the debug, SaleOrder create/read, or
    legacy quality-report routes

## Approval Gates

- No escalation reconciliation apply or real Telegram/WhatsApp test without
  explicit approval.
- No maintenance cron installation/apply or live synthetic latency traffic
  without explicit approval.
- No credential/scope changes or destructive cleanup without explicit approval.
- Ambiguous public API compatibility decisions return to the user.

## Acceptance Audit

| Criterion | Local evidence | External evidence still required | State |
| --- | --- | --- | --- |
| `AC-1` debug exposure | Route-removal regression, security gates, and production `404` pass | None for the bounded release | passed |
| `AC-2` OAuth/inbound durability | Malformed OAuth, durable recovery, replay, cancellation, quarantine regressions, deployment, and dependency health pass | Real provider/message replay remains separately approval-gated | deployed; live proof deferred |
| `AC-3` escalation reconciliation | Exact-manifest, tamper, transaction, rollback, and idempotency tests pass | Production apply remains optional and requires explicit approval under `tj-5o9r` | passed; mutation deferred |
| `AC-4` Docker maintenance | Dry-run/apply safety, heartbeat, health-failure, and idempotent installer tests pass | Production installation/first-run remains optional and requires explicit approval under `tj-5o9r` | passed; mutation deferred |
| `AC-5` truthful health | Production reports version `0.4.0`, Redis `ok`, database `ok`, HTTP `200` | None | passed |
| `AC-6` failure visibility | Privacy-safe signals, thresholds, cooldown ownership, heartbeat coverage, and deployment pass | One real alert delivery test remains optional and approval-gated under `tj-5o9r` | passed; live delivery deferred |
| `AC-7` latency | Local phase instrumentation, delivery-boundary reduction, and catalog/quotation/escalation/language/quality regressions pass | Live p50/p95/max certification remains blocked under `tj-15m` until exact synthetic traffic is approved | accepted bounded evidence; SLA proof deferred |
| `AC-8` public `501` contracts | Removed-route/OpenAPI regressions, durable documentation, production `404`, and production OpenAPI pass | None | passed |
| `AC-9` repository reconciliation | Exact inventory, patch-equivalence check, handoff, inbox, and cleanup dry-run are complete; all retained items have an explicit safety reason | Destructive removal remains blocked under `tj-rt42` until explicitly approved | passed without unapproved cleanup |
| `AC-10` release closeout | Full local gate and local E2E, process verification, merge/push, green CI/deploy, exact active SHA, bounded production smoke/readback, and rollback backup pass | Live-message E2E and an exercised rollback were outside the approved release scope and remain tracked under `tj-15m`/`tj-5o9r` | passed for approved release boundary |

## Delivery Closeout

- `scripts/orchestration/check_stage_ready.py tj-av22`: passed.
- `scripts/orchestration/run_stage_closeout.py --stage tj-av22 --level release
  --dry-run`: passed without publishing or changing production. It selected
  the full release gate plus integration, concurrency, security, PostgreSQL,
  and process-verification groups.
- Completion inbox: `14` events reviewed, `0` pending; both the combined
  findings report and its resolving correction review are immutable.
- E2E/smoke: deterministic local coverage and bounded production health,
  auth, route, OpenAPI, and release-SHA readback passed. Real messaging and the
  live latency matrix remain approval-gated.
- Delivery: `main`, `origin/main`, and the deployed release all identify
  `2213a06800a156f6d511af26072ea17f16178ef2` before this docs-only closeout
  update.
- Rollback boundary: the workflow packages `.release-sha`/`.release-run-id`;
  `scripts/vps-deploy.sh` creates a pre-deploy archive and verifies health.
  The deployed production SHA is
  `2213a06800a156f6d511af26072ea17f16178ef2`; its predecessor backup is
  recorded above.
- Stage cleanup dry-run classified the accepted child worktrees and branches as
  cleanup candidates. Their artifacts record `cleanup_status: blocked` because
  deletion requires explicit user approval after delivery.
- `codex/tj-av22-review-pass` is not an ancestor of `main` by commit identity,
  but `git cherry main codex/tj-av22-review-pass` marks both review commits as
  patch-equivalent in `main`; it contains no unintegrated stage change.
- Completed-agent runtime-tail check found no stage-owned pytest, Ruff, Mypy,
  or child-agent process group to terminate. The Codex app server and code-mode
  host are shared session infrastructure and were left untouched.
- `docs-reviewed: updated` — README, developer/admin guides, operations
  runbook, historical Zoho research/specification, architecture/task-plan
  notes, latency evidence, handoff, stage records, and project index reflect
  the stabilized contracts and the accepted-stage/follow-up boundary.
- `project-index: updated` — added the durable deploy, reconciliation,
  maintenance, and latency operational entrypoints.
- `project-index: reviewed-no-change` — the final closeout correction only
  prevents binary untracked files from producing false debt-marker findings;
  no stable project entrypoint or ownership boundary changed.
- `graph-reviewed: no-change-needed` — Graphify is not configured and
  `graphify-out/GRAPH_REPORT.md` is absent.

## Explicit Defers

- Epic `tj-av22` and release task `tj-av22.3` are closed under their explicit
  acceptance rule permitting named external blockers. Closure does not certify
  live latency targets or imply any unapproved production operation.
- Live latency/message proof, production operational drills, and destructive
  repository/cache cleanup remain explicit approval gates in active Beads.
- Product-policy and vendor gates outside this stabilization stage remain
  recorded in `.codex/handoff.md`.

| Beads | Remaining proof | External blocker / owner |
| --- | --- | --- |
| `tj-15m` | Approved live FAQ/product/comparison/order/Arabic/escalation latency matrix or named provider blocker | Exact live-test identity/scenarios and real-traffic approval from the user |
| `tj-rt42` | Removal and final readback of stage plus nine legacy worktrees/branches and optional caches | Exact destructive-cleanup approval from the user |
| `tj-5o9r` | Any selected escalation apply, maintenance install/first run, real alert delivery test, or rollback exercise | Exact per-operation production approval from the user |

Escalation reconciliation apply, maintenance cron installation/cleanup, and real
Telegram/WhatsApp checks remain separately approval-gated after deployment;
none is implied by approval to merge and push.
