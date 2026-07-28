# Noor Task 3 Production Trust Repair Implementation Plan

**Goal:** Close `tj-ee5f.5` so the accepted Noor production run can execute
only exact authorized synthetic actions, preserve truthful multi-turn evidence,
materialize honest non-passing outcomes, and compute side-effect closeout from
independent observations.

**Approach:** Preserve the accepted 30-criterion / 29-execution scope and the
existing fail-closed policy compiler. Add a protected bridge from the exact
approved live manifest and preflight into authorization v2, make every external
permit request-bound and one-use, then add registry-owned production
materialization, capability adapters, collectors, and CLI commands. Production
execution remains sequential and begins only after local review, canonical CI,
and a fresh exact preflight.

**Non-goals:** Do not weaken canonical repository, immutable scope, evidence
producer, redaction, quota, readback, or report trust boundaries. Do not add a
public test endpoint, spoof Wazzup origin, use direct database deletion as
cleanup authority, contact a real customer, infer missing client-owned test
identities, or count `BLOCKED`/`EXCLUDED_BY_CLIENT` as passing.

## Scope ledger

- Exact protected live manifest and preflight binding -> Task 1.
- Recipient/channel/payload/permission/unit-bound one-use permits -> Task 1.
- Multi-turn transcript truth and zero-turn non-pass outcomes -> Task 1.
- Terminal side-effect reconciliation -> Task 1.
- Application-native webhook adapter and independent production readback ->
  Task 2.
- Runnable prepare/preflight/execute-resume/finalize path -> Task 2.
- Exact 20 scenario + 9 evidence-block terminal coverage -> Task 3.
- Exact Q/A, timing, runtime, model, tools, audits, effects, limitations,
  defects, fixes, and retests -> Tasks 1–4.
- One synthetic recipient cannot prove isolated disjoint identities or
  provider-originated ingress -> explicit Task 3 gate; never silently pass.
- Russian Markdown client report -> Task 4.
- PDF -> separate post-acceptance gate after the user accepts Markdown content.

## Technical premortem

Verdict: **GO WITH CONDITIONS**

Scope: protected authorization, preflight, action journal, production webhook,
SSH/read-only collector, transcript and side-effect schemas, trusted run
materialization, report projection, and CLI.

Reversibility: code is locally reversible before execution. After a reserved
or possibly sent external action, no automatic retry or rollback is allowed;
the run must perform independent readback, retain the consumed quota, and
append a terminal reconciliation or remain blocked.

### Blast radius

```text
approved live manifest
  -> protected preflight bridge
  -> authorization v2
  -> action reservation
  -> production capability adapter
  -> Wazzup / LLM / optional business subsystem
  -> DB, audit, provider and external side effects
  -> independent collector
  -> committed attempt + transcript
  -> trusted snapshot/finalizer
  -> criterion rollups and Russian client report
```

Shared state includes the one approved synthetic WhatsApp identity, Wazzup
channel, production conversation and memory, CRM/Zoho identities, Telegram
target, scheduled lifecycle work, protected evidence stores, and the
authorization-scoped quota ledger.

### Risk register

| Failure symptom | Evidence | Mechanism / affected surface | Detection | Mitigation | Disposition | Owner / check |
|---|---|---|---|---|---|---|
| A permit sends a different recipient or payload | confirmed | current permit lacks target, operation and payload binding | focused drift and one-use tests | bind digests, units, expiry and permission; validate immediately before I/O | block | Task 1 tests/reviewer |
| A formal PASS leaves active follow-up, CRM, quotation, order or Telegram state | confirmed | finalizer trusts caller `side_effect_closeout` | negative finalizer fixtures and final independent inventory | compute closeout from typed ledger; reject missing, active, pending, unknown and invalid retention | block | Task 1 tests/reviewer |
| The report invents or drops dialogue turns | confirmed | current loader requires one turn per scenario and does not compare transcript content | multi-turn, empty, altered, duplicate, reordered and missing-turn tests | transcript-owned ordered turn identities and field-by-field binding | block | Task 1 tests/reviewer |
| A blocked provider gate is represented by a fake customer message | confirmed | current scenario attempt requires one actual turn and only PASS/FAIL | zero-turn PASS/non-pass tests | typed gate attempt for `BLOCKED`/valid `EXCLUDED_BY_CLIENT` | block | Task 1 tests/reviewer |
| Crash after send causes an uncounted retry | plausible, concrete | I/O outcome is uncertain between send and journal result | reserved/unknown recovery tests and journal audit | consume quota before I/O; exception-after-dispatch becomes `unknown`; no automatic retry | block | Task 1 + Task 2 |
| Public webhook accepts a malformed or unintended test action | confirmed preflight fact | production Wazzup allowlist is currently empty | exact endpoint/channel/payload preflight and provider correlation | adapter allows only manifest-bound Wazzup-shaped payload and explicit synthetic target | preflight | Task 2 |
| Readback is self-reported by the executor | confirmed architecture gap | public conversation API lacks all audit/tool/side-effect fields | collector producer/receipt tests and source-cursor checks | separate read-only production collector over approved SSH/runtime path | block | Task 2 |
| One recipient contaminates isolated scenarios | confirmed constraint | conversation and memory are keyed by phone; no disjoint authorized identities exist | baseline inventory and scenario starting-state comparison | run only evidence whose starting state is proven; otherwise terminal `BLOCKED`; never direct-DB cleanup | preflight | Task 3 |
| External quote/CRM/Telegram artifact cannot be safely cleaned | confirmed | no complete application-native delete/void/readback authority | permission and terminal-disposition preflight | skip/`BLOCKED`, or pre-authorize retained test evidence with owner, expiry, suppression and final readback | preflight | Task 3 |
| Executor silently edits unrelated code or skips gates | plausible executor error | broad cross-module change and long run | strict write zones, task artifacts, independent review, full gates and CI | one implementer at a time; review full base..head package | monitor | root orchestrator |

### Recovery

1. Before external I/O: abort the run; discard no committed evidence; fix or
   roll back code normally.
2. After reservation but before confirmed send: keep quota consumed, mark
   `unknown`, collect independent provider/DB/audit state, then append either a
   reconciled failure or a confirmed result. Never reuse the permit.
3. After a listed external artifact: apply only its manifest-authorized
   application path. If cleanup is unavailable, retain only when owner,
   expiry/final disposition, follow-up suppression and final readback were
   pre-authorized; otherwise the run stays blocked.
4. After an unlisted artifact or real-customer exposure: stop all branches,
   create a P0 defect, preserve evidence, and do not finalize.
5. A code rollback does not erase attempts, reservations, transcripts or
   side-effect records.

### Preflight checklist

- [ ] Exact main commit is CI-green and canonical remote/worktree checks pass.
- [ ] Deployed release, CI run, endpoint, app version, migration head,
      main/fast models and services match the protected manifest.
- [ ] Recipient, channel and Telegram values match by protected digest without
      entering tracked evidence.
- [ ] Authorization window, executor/source, exact 29 IDs, planned input
      digests, permissions, callback types, quotas, cleanup/retention and
      readbacks validate.
- [ ] Baseline inventory proves no unlisted pending synthetic artifact.
- [ ] Every mutation-capable unit has a terminal disposition plan; otherwise it
      is predeclared `BLOCKED`.
- [ ] Protected raw/anchor roots are mode 0700 with files 0600; tracked output
      passes normalized privacy validation.
- [ ] No unresolved in-scope P0/P1 remains.

## Task 1: Trusted production execution and evidence core

**Owner:** `tj-ee5f.5`

**Files:**

- `scripts/e2e_acceptance/execution.py`
- `scripts/e2e_acceptance/policy.py`
- `scripts/e2e_acceptance/trusted_run.py`
- `scripts/e2e_acceptance/evidence.py`
- focused `tests/test_e2e_acceptance_*.py`
- `.codex/stages/tj-ee5f/artifacts/tj-ee5f.5.md`

**Boundary:** Local trust contracts and protected stores. No network or
production action. Rollback is the task commit range.

**Interfaces:** Consumes approved authorization v1 schema, preflight
validation, policy v2, protected journal and side-effect ledger. Produces an
exact live authorization bridge, request-bound permit, typed executed/gate
attempts, transcript-bound report rows, and computed side-effect closeout.

**Verification lane:** `tdd-required` — the readiness reviewer reproduced
unsafe false acceptance and unrepresentable outcomes.

- [ ] Add focused failing tests for live-manifest/preflight drift; destination,
      payload, permission, unit and expiry drift; permit reuse; exception after
      dispatch; and authorization-scoped quota persistence.
- [ ] Bind protected approved manifest, preflight request/observation,
      execution inputs, adapter/collector IDs, target digests, permissions,
      cleanup/retention and store roots into authorization v2.
- [ ] Extend action reservations with exact request identity and one-use
      validation immediately before adapter I/O; uncertain completion remains
      `unknown` and consumes quota.
- [ ] Add typed executed and gate attempt variants. Permit arbitrary ordered
      turns for executed scenarios and zero turns only for `BLOCKED` or a valid
      Task 1 client exclusion.
- [ ] Materialize report Q/A, timing, model, token/cost, tool, audit and media
      fields only from committed protected transcript artifacts and producer
      receipts.
- [ ] Make trusted finalization validate the typed side-effect ledger against
      independent final inventory and derive, rather than accept,
      `side_effect_closeout`.
- [ ] Run focused RED/GREEN tests, all acceptance tests, Ruff, format, Mypy,
      full Pytest and process verification once at the boundary.
- [ ] Produce a strict stage artifact and full-range independent review.

## Task 2: Production capability adapters, collector, and runnable CLI

**Owner:** follow-up child of `tj-ee5f.5`, blocked by Task 1 acceptance.

**Files:**

- new `scripts/e2e_acceptance/production.py`
- `scripts/e2e_acceptance/runner.py`
- `scripts/run_noor_e2e_acceptance.py`
- focused `tests/test_e2e_acceptance_*.py`
- task artifact under `.codex/stages/tj-ee5f/artifacts/`

**Boundary:** Local adapter code and mocked transports in implementation.
Actual external I/O remains disabled until Task 3 preflight. Rollback is the
adapter commit range; no runtime application endpoint is added.

**Interfaces:** Consumes Task 1 authorization/permit/producer contracts.
Produces an application-native Wazzup webhook adapter, independent read-only
runtime collector, protected run-plan loader, and
`prepare/preflight/execute-resume/record-gate/finalize` CLI.

**Verification lane:** `tdd-required` — external-call ordering, timeout,
uncertain-result and redaction behavior are new high-risk contracts.

- [ ] Add fake HTTP/SSH transports and failure-path tests before production
      implementation.
- [ ] Implement capability dispatch without scenario-ID branches. The webhook
      adapter accepts only an exact permit and protected message file; the
      collector cannot execute mutations.
- [ ] Record exact raw responses only in the protected store; write redacted,
      checksummed transcript/audit/inventory projections to tracked results.
- [ ] Add deterministic run-plan and evaluator configuration digests; preserve
      planned/actual/adaptive turn relationships.
- [ ] Add resumable CLI commands that fail closed on drift, duplicate permits,
      stale readbacks, unknown actions or nonterminal effects.
- [ ] Prove end-to-end with local fake transports, crash/recovery fixtures,
      full repository gates, process verification and independent review.

## Task 3: Exact authorized production execution

**Owner:** root acceptance orchestrator. External steps are sequential.

**Files:**

- protected raw/authorization/journal roots under Git common runtime state
- tracked redacted `.codex/stages/tj-ee5f/results/<run_id>/`
- Beads defects discovered during execution

**Boundary:** One exact commit/release/run/recipient/channel and manifest. No
real customer. Shared conversation, provider, CRM, quotation, escalation and
lifecycle state is never exercised in parallel.

**Interfaces:** Consumes accepted Tasks 1–2 and current user authority.
Produces immutable attempts and terminal outcomes for all 29 execution units.

**Verification lane:** `no-new-test` for the live run; harness behavior is
already proven. Every action is separately reserved and independently read
back.

- [ ] Generate the protected exact authorization from the current user
      authority and approved synthetic identity without printing or tracking
      the raw recipient/channel/Telegram values.
- [ ] Perform fresh preflight and baseline inventory. Abort on any drift.
- [ ] Execute only units with proven starting state and terminal disposition.
      Use the one approved synthetic identity sequentially.
- [ ] Record units requiring disjoint identities, provider-originated ingress,
      unavailable cleanup, or client-owned infrastructure as typed
      non-passing outcomes; never invent a turn.
- [ ] Preserve exact questions, Noor answers, timing, delivery, models, tools,
      audits, media, quotas, attempts and all side effects.
- [ ] Stop the affected branch on unsafe continuation or P0/P1; create Beads,
      fix in an isolated delivery stream, deploy, preflight again, and append a
      new immutable retest.
- [ ] Finalize only when every action and artifact has an independently proven
      terminal disposition.

## Task 4: Report, closeout, and post-acceptance PDF

**Files:**

- tracked report source/results under
  `.codex/stages/tj-ee5f/results/<run_id>/`
- Russian Markdown client report
- stage artifact, summary and handoff updates

**Boundary:** Report is a strict projection of verified run evidence. PDF is a
separate user-content-acceptance gate.

**Verification lane:** `no-new-test` for content assembly; trusted report
rendering was tested in Tasks 1–2. Use privacy, checksum, Markdown completeness,
process and closeout checks.

- [ ] Publish all 30 criteria and 29 executions with honest outcomes and the
      three independent rollups.
- [ ] Include every exact Q/A, timing, runtime/model identity, tools/audits,
      side effects, limitations, defects, fixes and retests.
- [ ] Run normalized PII/secret validation, full trusted-run verification,
      process verification and independent final review.
- [ ] Deliver Markdown to the user and wait for explicit content acceptance.
- [ ] Only after acceptance, use the repository PDF workflow, visually inspect
      every rendered page, and deliver the PDF.
