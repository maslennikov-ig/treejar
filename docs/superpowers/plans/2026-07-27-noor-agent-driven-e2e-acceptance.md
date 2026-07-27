# Noor Agent-Driven E2E Acceptance Implementation Plan

**Goal:** Execute a traceable, agent-driven acceptance of Noor against the
original Treejar requirements and accepted bot regressions, preserve every
question, answer, side effect, defect, fix, and retest, and deliver an honest
Russian client report for Viktor.

**Owning Beads:** `tj-ee5f.1` under epic `tj-ee5f`

**Approach:** Build one reproducible acceptance harness around the existing
production webhook, conversation readback, dialogue checks, and operator
evidence. Use isolated synthetic scenario capsules plus one longitudinal
journey. Keep captured acceptance evidence immutable; any defect is fixed and
deployed in a separate task/branch, then retested as a new release-bound
attempt. The orchestrator may use specialists or isolated workers when they
materially help, but this plan does not prescribe an agent count.

**Non-goals:** Real-customer testing; silently enabling disabled business
features; destructive cleanup; treating a model judge as the sole oracle;
rewriting failed evidence; presenting application-native webhook injection as
full provider-to-provider WhatsApp E2E.

## Entry gate

`tj-ee5f.1` is blocked by `tj-r1f3`. Preparation may proceed locally, but no
mutation-capable production scenario may start until:

- `tj-r1f3` is closed with a deployed release and fresh passing provider smoke;
- the exact target release, migrations, models, endpoint, test identities,
  quotas, allowed side effects, callbacks, readbacks, cleanup, and retention
  are bound in a current authorization manifest;
- the target release has no unresolved in-scope P0/P1.

Current evidence to recover, not assume:
`.codex/stages/tj-r1f3/results/postdeploy-verification.md`.

## Scope ledger

- Immutable original-requirement coverage -> Task 1 criterion snapshot and
  traceability manifest.
- Closed regression coverage and current precedence decisions -> Task 1
  traceability manifest and scenario set.
- Reproducible adaptive tester/judge configuration -> Task 1 run manifest and
  Task 2 dry run.
- Isolated customer outcomes and long-memory journey -> Task 3.
- Provider-originated English/Arabic ingress truth -> Task 3 separate canaries
  or explicit non-passing outcome.
- Exact questions, answers, timestamps, models, tools, audit/provider IDs,
  cost, and evaluator evidence -> Tasks 1 and 3.
- Quotations, CRM, escalation, follow-up, feedback, Telegram, and other
  side-effect safety -> Tasks 1 and 3 external disposition ledger.
- Failure -> Beads -> isolated fix -> deploy -> immutable retest chain ->
  Task 4.
- Coverage, execution, requirements, performance, defects, fixes, retests,
  limitations, and safe client evidence -> Task 5.
- Full repository and production release verification -> Tasks 2, 3, and 5.

### Task 1: Acceptance contracts, traceability, and scenario set

**Files:**

- `.codex/goals/tj-ee5f/scope-criterion-snapshot.json`
- `.codex/stages/tj-ee5f/stage-manifest.json`
- `.codex/stages/tj-ee5f/traceability-manifest.json`
- `.codex/stages/tj-ee5f/scenario-set.json`
- `.codex/stages/tj-ee5f/authorization-manifest.example.json`
- `scripts/e2e_acceptance/schemas.py`
- `scripts/e2e_acceptance/manifest.py`
- `tests/test_e2e_acceptance_manifests.py`

**Boundary:** Local preparation only. This task defines immutable identities
and validation contracts; it performs no provider call or production mutation.

**Interfaces:** Consumes the approved design, original requirements, closed
relevant Beads, current repo contracts, and `tj-r1f3` status. Produces stable
criterion IDs, precedence/oracles, evidence modes, scenarios, quotas, stop
conditions, and report ownership.

**Verification lane:** `tdd-required` — schema separation, immutable scope
identity, dependency freshness, and authorization drift are public test
contracts.

- [ ] Freeze the goal snapshot with only criterion ID, normalized exact text,
  text digest, and source-set digest; prove it remains byte-stable.
- [ ] Keep provenance, precedence, oracle, freshness, owner, and scenario
  mapping in the versioned traceability manifest.
- [ ] Define run outcomes independently from evidence mode:
  `PASS|FAIL|BLOCKED|EXCLUDED_BY_CLIENT` and
  `fresh|reused_exact|external_gate`.
- [ ] Normalize the original requirements and all relevant closed regressions,
  including the explicit `<10s`, `99%`, `100+`, backup/retention, CRM stage,
  pricing/total, catalog-coverage, and top-three-offer criteria.
- [ ] Define isolated EN/AR customer scenarios, high-risk paraphrase variants,
  one longitudinal journey, and separate admin/load/security/backup blocks.
- [ ] Validate exact release/model/target/quota/permission/expiry drift before
  any live step.
- [ ] Self-review that every scope criterion has an owner and observable
  oracle; record unresolved client inputs as non-passing external gates.

### Task 2: Reproducible harness, evidence, and report foundation

**Files:**

- `scripts/e2e_acceptance/runner.py`
- `scripts/e2e_acceptance/evidence.py`
- `scripts/e2e_acceptance/evaluators.py`
- `scripts/e2e_acceptance/report.py`
- `scripts/run_noor_e2e_acceptance.py`
- `tests/test_e2e_acceptance_runner.py`
- `tests/test_e2e_acceptance_evidence.py`
- `tests/test_e2e_acceptance_report.py`
- `docs/testing/noor-e2e-client-report-template.md`

**Boundary:** Local/dry-run implementation. Reuse the correlation and readback
patterns in `scripts/bot_test.py`; do not inherit the direct-DB deletion model
from the legacy test suite as production cleanup authority.

**Interfaces:** Consumes Task 1 manifests. Produces validated run directories,
per-turn records, checksums, redaction validation, side-effect ledger, defect
drafts, rollups, and the Markdown report source.

**Verification lane:** `tdd-required` — parsing, correlation, redaction,
evidence immutability, outcome calculation, and side-effect terminal states are
high-risk contracts.

- [ ] Capture planned and actual turns, adaptive deviations, original
  language, Russian translation provenance, tester/judge configuration,
  deterministic checks, and judge reasoning.
- [ ] Store protected raw evidence outside Git with mode `600`; store complete
  redacted evidence under
  `.codex/stages/tj-ee5f/results/<run_id>/`.
- [ ] Hash raw/redacted evidence and validate that credentials, full phone
  numbers, private manager data, and unrestricted logs cannot enter Git,
  Beads, or the client report.
- [ ] Require both deterministic oracles and bounded agent judgment; never let
  a judge override a hard commercial-safety failure.
- [ ] Track every local/external side effect from baseline to one verified safe
  terminal state: `voided`, `closed`, `resolved`, or pre-authorized
  `retained_as_test_evidence`.
- [ ] Make `cleanup_pending`, `cleanup_blocked`, `unknown`, missing readback, or
  unlisted artifacts block closeout.
- [ ] Dry-run the full harness with fixtures and prove failed attempts are
  append-only.

### Task 3: Authorized production execution

**Files:**

- `.codex/stages/tj-ee5f/results/<run_id>/authorization-manifest.json`
- `.codex/stages/tj-ee5f/results/<run_id>/run-manifest.json`
- `.codex/stages/tj-ee5f/results/<run_id>/transcripts/*.json`
- `.codex/stages/tj-ee5f/results/<run_id>/scenario-results.json`
- `.codex/stages/tj-ee5f/results/<run_id>/side-effect-ledger.json`

**Boundary:** Exact live authorization and release identity. Application-native
capsules may use disjoint synthetic identities. Quotation, manager, CRM,
follow-up, callbacks, and cleanup remain sequential where they share state.

**Interfaces:** Consumes Tasks 1–2 and current authorization. Produces immutable
fresh production evidence only.

**Verification lane:** `no-new-test` for the run itself — harness behavior was
tested in Task 2; this task executes declared acceptance and performs exact
readbacks.

- [ ] Re-read release SHA, CI run, migration head, endpoint, app version,
  main/fast routes, health, channel, Telegram target, and authorization
  validity; abort on drift.
- [ ] Run isolated capsules in safe dependency order, then the longitudinal
  journey; preserve exact customer and Noor messages plus timing/audit data.
- [ ] Run provider-originated EN/AR canaries only when separately authorized
  and correlated. Otherwise mark provider ingress `BLOCKED`, never “passed”.
- [ ] Stop an affected branch before unsafe continuation; preserve independent
  safe evidence.
- [ ] Reconcile every expected and observed side effect and suppress follow-up
  or callbacks according to the manifest.
- [ ] Publish preliminary rollups without treating blocked, excluded, failed,
  or unexecuted criteria as passing.

### Task 4: Defect, fix, deployment, and retest chain

**Files:** Separate Beads child per defect; isolated fix worktree/branch;
append-only new attempt under the original scenario result.

**Boundary:** Acceptance execution remains immutable. Product fixes, deploys,
and retests are separate authorization and rollback boundaries.

**Interfaces:** Consumes failed evidence. Produces a Beads reproduction,
invariant test, verified fix, deployed release identity, and linked retest.

**Verification lane:** `tdd-required` for every behavior fix.

- [ ] Create each defect with exact evidence path, expected/actual behavior,
  impact, severity, reproduction, and acceptance criteria.
- [ ] P0/P1 blocks affected acceptance. P2/P3 continues only when safe.
- [ ] Diagnose and fix in isolation; run focused, affected, integration, and
  release checks proportional to risk.
- [ ] Ask for the required deploy/live authorization, deploy through the
  canonical workflow, and re-read exact runtime identity.
- [ ] Add a new retest attempt linked to the original failure, defect ID, fix
  commit, deploy run, and invariant proof. Never overwrite the failure.

### Task 5: Client report and closeout

**Files:**

- `.codex/stages/tj-ee5f/results/<run_id>/client-report.md`
- `.codex/stages/tj-ee5f/results/<run_id>/client-report.pdf` after content
  acceptance
- `.codex/stages/tj-ee5f/summary.md`
- `.codex/handoff.md`

**Boundary:** Evidence reconciliation and delivery. PDF generation follows
Markdown acceptance and uses the repository PDF workflow with visual
inspection.

**Interfaces:** Consumes all accepted structured evidence and linked defect
chains. Produces the Russian client deliverable and closeout state.

**Verification lane:** `no-new-test` for prose/PDF generation; run schema,
checksum, link, redaction, and visual checks.

- [ ] Report scope, methodology, exact runtime/model identity, every scenario's
  exact Q/A, expected/actual result, timings, safe media references, defects,
  failed attempts, fixes, retests, and limitations.
- [ ] Publish `coverage_complete`, `execution_complete`, and
  `requirements_met` independently.
- [ ] Reconcile structured results, report claims, Beads, and side-effect
  dispositions; zero unresolved in-scope P0/P1 is required for acceptance.
- [ ] Review docs impact and Graphify disposition, run canonical process/stage
  closeout, deliver tracked evidence, and clean only the stage-owned workspace.

## Verification commands

Focused commands should be added with the harness tests. The release boundary
must include the canonical repository commands:

```bash
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy src/
uv run pytest tests/ -v --tb=short
scripts/orchestration/run_process_verification.sh
scripts/orchestration/run_stage_closeout.py --stage tj-ee5f
```

Live verification is manifest-driven rather than a broad ad hoc command list.
Every paid, provider, customer-visible, mutation, callback, cleanup, deployment,
or destructive action needs the exact current-task authorization required by
the repository contract.
