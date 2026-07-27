---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-ee5f/stage-manifest.json
stream_owner: improvement_reviewer
orchestration_level: slice_acceptance
scope_kind: foundation
immediate_consumer: tj-ee5f implementation plan and execution prompt
public_facade: Noor E2E acceptance design and client report contract
bounded_acceptance: independent read-only design review before implementation planning
non_goals:
  - live execution, paid calls, deployment, production mutation, implementation, or exhaustive backlog review
task_id: tj-ee5f-design-review
epic_id: tj-ee5f
stage_id: tj-ee5f
session_id: tj-ee5f
milestone: agent-driven E2E acceptance design and resolution review
milestone_status: replan-required
agent_type: improvement_reviewer
subagent_model: inherit_orchestrator
reasoning_effort: role_default
model_reasoning_rationale: context-isolated review of a high-risk production acceptance design
repo: treejar
branch: codex/noor-agent-e2e-acceptance-plan
base_branch: main
base_commit: 9e7f2206bc3bbb88e60c428ac229785f9a10c960
worktree: /home/me/code/treejar/.worktrees/noor-agent-e2e-acceptance-plan
write_zone:
  - .codex/stages/tj-ee5f/artifacts/tj-ee5f-design-review.md
success_criteria:
  - identify decision-affecting traceability, isolation, evidence, workflow, reporting, authorization, and feasibility gaps
  - verify the six original findings against revised design commit 103f163
selected_docs:
  - AGENTS.md
  - .codex/orchestrator.toml
  - .codex/handoff.md
  - docs/tz.md
  - docs/01-tz-basic.md through docs/08-manager-evaluation-criteria.md
  - docs/superpowers/specs/2026-07-27-noor-agent-driven-e2e-acceptance-design.md
  - relevant accepted production E2E artifacts and closed Beads
selected_skills:
  - none
selected_agents:
  - improvement_reviewer
catalog_candidates:
  - none
parallel_group: context-isolated-design-review
depends_on_streams:
  - none
parallel_decision: parallel
status: returned
delivery_method: n/a
accepted_by_orchestrator: no
cleanup_status: not_applicable
cleanup_notes: read-only review; no runtime or workspace cleanup was authorized
risk_level: medium
verification_tier: delta
risk_tags:
  - authorization
  - security
  - user-flow
  - data
affected_surfaces:
  - user-flow
  - data
  - backend
invariants:
  - test-matrix
  - idempotency
  - rollback
docs_impact: docs-only
docs_reviewed: updated
docs_review_notes: review artifact records the original findings and revised-design resolution review; source design was intentionally not edited
verification:
  - source design commit 21bebc2 inspected: passed
  - revised design commit 103f163 delta inspected: passed
  - referenced design Beads status audit: passed
  - git diff --check on review artifact: passed
  - scripts/orchestration/validate_artifact.py on review artifact: passed
changed_files:
  - .codex/stages/tj-ee5f/artifacts/tj-ee5f-design-review.md
explicit_defers:
  - source design edits and implementation planning remain with the root orchestrator
---

# Findings

## 1. P1 — Acceptance semantics and requirement traceability are not safe enough

- **Current approach:** Overall acceptance permits a requirement to map to
  evidence, an external gate, or an exclusion, while a missed `<10s` target is
  merely reported. Broad coverage families defer the exact matrix to the plan.
- **Evidence:** Design §8 lines 471-483. Explicit but not precisely represented
  obligations include CRM deal-stage transitions
  (`docs/01-tz-basic.md:37-38`), personalized/order-total behavior
  (`docs/01-tz-basic.md:34-38`), catalog coverage and top-three offer thresholds
  (`docs/07-knowledge-base-spec.md:153-160`), and `<10s`, `99%`, `100+`, and
  30-day backup targets (`docs/tz.md:172-181`).
- **Suggested alternative:** Freeze a `scope-criterion-snapshot/v1` before
  scenario planning. Give every source criterion a stable ID, precedence
  decision, oracle, freshness rule, scenario/evidence block, and one of
  `PASS`, `FAIL`, `BLOCKED`, `EXCLUDED_BY_CLIENT`, or
  `REUSED_EXACT_EVIDENCE`. Report separate rollups for
  `coverage_complete`, `execution_complete`, and `requirements_met`; a gate,
  exclusion, or missed target cannot count as pass.
- **Expected value:** Prevents silent scope loss and an unqualified client
  acceptance claim when requirements were not run or did not pass.
- **Tradeoff/cost:** Moderate one-time requirements normalization and a small
  result/report schema expansion.
- **Affected files:** design, implementation plan, criterion snapshot,
  client-report template.
- **Confidence:** High.
- **Classification:** **must-fix**.
- **Promotion target:** **design edit**, then **implementation plan** and
  **client-report template**.

## 2. P1 — Synthetic suffix capsules do not prove real Wazzup provider ingress

- **Current approach:** Unique phone suffixes provide strong scenario isolation,
  but the design can present these capsules as full WhatsApp transport E2E.
- **Evidence:** Design §3.1 lines 67-75 and §4.A lines 106-116.
  `scripts/bot_test.py:196-243` constructs a Wazzup-shaped payload and POSTs it
  directly to Noor's webhook. Prior latency evidence starts at webhook
  submission (`.codex/stages/tj-15m/summary.md:52-55`).
- **Suggested alternative:** Define two evidence tiers:
  (1) application-native synthetic webhook capsules, covering production
  processing and real outbound delivery; and (2) at least one separately
  authorized provider-originated EN/AR canary from the approved real WhatsApp
  identity, or a client-visible limitation that provider ingress was not
  exercised. Tier 1 alone must not be labeled full provider-to-provider E2E.
- **Expected value:** Retains practical isolation without overstating transport
  coverage.
- **Tradeoff/cost:** A true ingress canary is less automatable and may need a
  human send/correlation step.
- **Affected files:** design, implementation plan, client-report template.
- **Confidence:** High.
- **Classification:** **must-fix**.
- **Promotion target:** **design edit**, **implementation plan**, and
  **client-report template**.

## 3. P1 — Cleanup is conversation-centric, not an external side-effect ledger

- **Current approach:** The manifest lists allowed mutation branches and a
  cleanup method; closeout focuses on pending escalations and active workflows.
  It does not define terminal disposition for every Zoho quotation/SaleOrder,
  CRM contact/deal, follow-up schedule, feedback row, Telegram alert, or
  referral artifact.
- **Evidence:** Design §9 lines 487-505. Previous E2E closed conversations but
  retained real Zoho drafts `Fr3306` and `Fr3307`
  (`.codex/stages/tj-m7wz/artifacts/tj-m7wz-production-e2e.md:122-132`);
  another cleanup checked only local active/escalated counts
  (`.codex/stages/tj-mmj8/artifacts/tj-mmj8-production-e2e.md:166-175`).
- **Suggested alternative:** Require a before/after side-effect ledger keyed by
  scenario and subsystem. Each expected mutation records external ID, allowed
  terminal disposition (`voided`, `closed`, `resolved`,
  `retained_as_test_evidence`, etc.), follow-up suppression, cleanup authority,
  and final readback. Unlisted artifacts or missing dispositions block closeout;
  retained external records are reported as limitations, not “cleaned”.
- **Expected value:** Prevents test data from polluting operations or triggering
  later lifecycle actions.
- **Tradeoff/cost:** More readbacks and client-owned disposition decisions;
  destructive deletion remains unnecessary.
- **Affected files:** design, authorization manifest, implementation plan,
  structured results.
- **Confidence:** High.
- **Classification:** **must-fix**.
- **Promotion target:** **design edit** and **implementation plan**.

## 4. P1 — Fix/deploy ownership conflicts with repo boundaries, and one cited risk is still open

- **Current approach:** The same correction stream owns root cause,
  implementation, deployment, retest, and report update. Factual grounding also
  lists `tj-r1f3` as a historical anchor without marking it unresolved.
- **Evidence:** Design lines 448-450 and 170-171. `AGENTS.md:29-35` requires one
  task per branch/worktree and separates runtime triage, deploy drift, and
  product fixes. `bd show tj-r1f3 --json` reports `in_progress`; the defect
  includes a P1 grounding-tail issue, and `.codex/handoff.md:91-100,147-148`
  says its accepted correction is local-only and still awaits authorized
  delivery and runtime proof.
- **Suggested alternative:** Keep acceptance execution immutable and read-only
  after evidence capture. A failure creates a child Bead and isolated fix
  branch/worktree; delivery closes separately; the acceptance owner then opens
  a new retest run against the new release identity. Split inputs into
  `accepted_regressions` and `open_known_risks`, and require no unresolved
  in-scope P0/P1 on the target release. Deliver `tj-r1f3` first or mark affected
  scenarios as known failures that cannot support acceptance.
- **Expected value:** Preserves chain of custody, rollback clarity, and avoids a
  broad run rediscovering a known deployed-runtime gap.
- **Tradeoff/cost:** Extra task transitions and possibly sequencing `tj-ee5f`
  behind one bounded delivery.
- **Affected files:** design, implementation plan, Beads dependency graph.
- **Confidence:** High.
- **Classification:** **must-fix**.
- **Promotion target:** **design edit**, **implementation plan**, and **Beads**.

## 5. P1 — Authorization and evidence retention are not drift-proof

- **Current approach:** The manifest binds recipient/channel, aggregate limits,
  allowed branches, cleanup, readbacks, and stop conditions. Raw evidence is
  outside Git with mode `600`.
- **Evidence:** Design lines 337-348, 370-382, and 487-501. The repo requires
  exact evidence identity (`.codex/orchestrator.toml:273-278`), while the
  current handoff requires fresh approval for deploy/provider/live actions
  (`.codex/handoff.md:130-140`). The prior latency stage names a protected
  location, but the new design has no owner, retention, backup, redaction
  validation, or deletion contract.
- **Suggested alternative:** Pre-bind expected release SHA/migration/model
  routes, endpoint, authorization issuer/expiry, executor/source, exact Wazzup
  and Telegram targets, per-subsystem mutation/message quotas, permitted
  callbacks, and abort-on-drift rules. Add an evidence-retention manifest with
  protected locator, owner/access, created/expiry timestamps, raw/redacted
  hashes, redaction-validation result, backup policy, and final disposition.
- **Expected value:** Makes approval least-privilege and preserves auditable
  evidence through client review without leaking restricted paths or data.
- **Tradeoff/cost:** Additional manifest fields and preflight bookkeeping; most
  identities are already collected after the run.
- **Affected files:** design, authorization manifest, implementation plan,
  report inputs.
- **Confidence:** High.
- **Classification:** **must-fix**.
- **Promotion target:** **design edit** and **implementation plan**.

## 6. P2 — Evidence reuse and adaptive-agent reproducibility are underspecified

- **Current approach:** The design reads as a fresh comprehensive run for every
  block and records evaluator judgment, but does not define exact-identity reuse
  or tester/judge configuration.
- **Evidence:** `.codex/orchestrator.toml:229-234,273-278` permits reuse only for
  unchanged exact identity. Design lines 329-331 and 350-364 require seeded
  prompts but omit tester/judge model, prompt, rubric, and translation
  provenance.
- **Suggested alternative:** Mark each criterion `fresh`, `reused_exact`, or
  `external_gate` with dependency identity; always collect fresh release,
  route, health, and customer-flow evidence, while reusing unchanged
  load/security/backup/admin evidence when identity matches. Hash/version the
  persona/scenario prompt, seed, tester model, judge model, rubric, tools, and
  translation prompt; retain planned versus actual turns and use bounded
  repeats only for high-risk disagreement/nondeterminism.
- **Expected value:** Avoids risky redundant production work and makes
  agent-driven conclusions reproducible without turning the run into a broad
  model battle.
- **Tradeoff/cost:** A freshness audit, extra metadata, and limited repeat calls.
- **Affected files:** implementation plan and evidence schema.
- **Confidence:** Medium-high.
- **Classification:** **high-value improvement** worth tracking in **Beads** if
  not completed in planning.
- **Promotion target:** **implementation plan**.

# Evidence

## Verification

- Inspected the design at exact commit `21bebc2`.
- Read `AGENTS.md`, `.codex/orchestrator.toml`, `.codex/handoff.md`,
  `.codex/project-index.md`, `docs/tz.md`, and
  `docs/01-tz-basic.md` through `docs/08-manager-evaluation-criteria.md`.
- Reviewed relevant production evidence from `tj-gh12`, `tj-gh23`, `tj-m7wz`,
  `tj-mmj8`, `tj-e2e26`, and `tj-15m`.
- Queried only Beads needed to validate design claims. All cited IDs resolved
  as closed except the current goal and `tj-r1f3`; `tj-r1f3` is in progress.
- No live, remote, paid, production, secret, customer, deployment, or cleanup
  action was performed.

# Recommendations

## Top 3 recommended next improvements

1. Freeze the criterion snapshot and separate coverage/execution completion
   from actual requirements acceptance.
2. Separate synthetic webhook evidence from true provider ingress and add the
   external side-effect/disposition ledger.
3. Keep fixes/deployments outside the immutable acceptance stream, resolve or
   gate `tj-r1f3`, and bind a drift-proof authorization/evidence manifest.

Findings 1-5 are required design changes. Finding 6 is high-value planning work
and should be implemented now or tracked in Beads with a bounded reason.

# Positive Patterns

- Isolated capsules plus one longitudinal journey is the right architecture for
  regression isolation and memory acceptance.
- Failed attempts are preserved and fixes require deployment plus exact retest;
  code-only “fixed” claims are rejected.
- Binary commercial-safety gates, P0/P1 stop behavior, outbound audit
  expectations, and application-path cleanup are strong foundations.
- Protected raw plus tracked redacted evidence and Markdown-first/PDF-after-
  review are practical choices.
- Preparation correctly authorizes no live, paid, customer, deployment, or
  business mutation.

# Original Verdict (21bebc2)

## Summary

**REVISE.** The architecture is strong, but findings 1-5 materially affect the
truth of the client acceptance claim or the safety of execution and must be
corrected before implementation planning.

# Docs Reviewed

`docs-reviewed: updated` — this review artifact records required design
corrections. The source design was intentionally not edited.

# Graph Reviewed

`graph-reviewed: no-change-needed` — Graphify is not configured and
`graphify-out/GRAPH_REPORT.md` is absent.

# Risks / Follow-ups / Explicit Defers

- Design edits, implementation planning, prompt authoring, Beads dependency
  changes, and client-report template work remain with the root orchestrator.
- Historical protected raw evidence was not accessed; tracked redacted
  artifacts and Beads state were sufficient for this review.
- No dependency or library recommendation is made; documentation lookup was not
  applicable.

# Resolution Review (103f163)

## New P0-P2 Findings

### P1 — The immutable scope anchor is overloaded with mutable evidence state

- **Current revised approach:** Design lines 63-75 require the goal-level
  `scope-criterion-snapshot/v1` to retain oracle, freshness, owner, and one
  final result disposition. Lines 566-600 then use a separate evidence-mode
  vocabulary but count `REUSED_EXACT_EVIDENCE` as a passing result, while line
  74 says a reused result is coverage information rather than a pass.
- **Repository evidence:** `.codex/scope-criterion-snapshot-template.json`
  defines the anchor as criterion ID/text/digest from Beads.
  `scripts/orchestration/lint_stage_sizing.py:269-279` requires the anchor to
  remain byte-identical to its Git creation blob for material replans. Final
  dispositions are necessarily learned after that immutable snapshot is
  created.
- **Impact:** An implementation following the design literally must either
  mutate an immutable scope anchor and fail repo validation, or pre-populate
  unknown results. It also conflates three independent axes—criterion identity,
  evidence mode, and outcome—so a reused failed result could be treated as
  requirements met.
- **Required correction:** Keep the goal snapshot immutable and limited to the
  exact criterion identity/text/digest contract. Put source provenance,
  precedence, oracle, freshness, and scenario ownership in a separate
  traceability manifest; put final `PASS`/`FAIL`/`BLOCKED`/`EXCLUDED_BY_CLIENT`
  in run results. `fresh`/`reused_exact`/`external_gate` remains a separate
  evidence mode, and reused evidence counts only when its preserved outcome is
  `PASS`.
- **Promotion target:** **design edit** before implementation planning.
- **Confidence/classification:** High; **must-fix design blocker**.

### P1 — `blocked` is not a safe terminal side-effect disposition

- **Current revised approach:** Design lines 473-480 allow side-effect ledger
  disposition `blocked`, while lines 602-613 require only a terminal
  disposition and no unlisted artifact for overall acceptance.
- **Impact:** Cleanup/readback can be blocked while a quotation, CRM deal,
  scheduled follow-up, or callback remains active or unknown. Treating that as
  terminal can satisfy the written acceptance gate without proving operational
  safety.
- **Required correction:** Limit safe terminal dispositions to verified states
  such as `voided`, `closed`, `resolved`, or pre-authorized
  `retained_as_test_evidence` with follow-up suppression, owner, and expiry.
  Keep `blocked` as a nonterminal ledger/result state that blocks closeout and
  overall acceptance until resolved or explicitly re-authorized under a new
  run boundary.
- **Promotion target:** **design edit** before implementation planning.
- **Confidence/classification:** High; **must-fix design blocker**.

No other new P0-P2 issue was found in the bounded delta.

## Six Original Finding Dispositions

1. **Acceptance semantics and traceability — PARTIALLY RESOLVED.** The revised
   design adds explicit original criteria, three honest rollups, and non-passing
   gate/exclusion behavior. The remaining blocker is the new schema/state
   conflation above, not the rollup intent.
2. **Provider ingress evidence tiers — RESOLVED.** Lines 81-124 and 151-164
   correctly label synthetic webhook capsules and require separately authorized
   EN/AR provider-originated canaries or a client-visible `BLOCKED` limitation.
3. **External side-effect ledger — PARTIALLY RESOLVED.** Lines 461-480 and
   646-648 cover the required subsystems, baseline, ownership, suppression, and
   readback. The `blocked` terminal-state defect above must still be removed.
4. **Immutable acceptance evidence, isolated fix/delivery/retest ownership, and
   `tj-r1f3` gate — RESOLVED.** Lines 138-149, 535-554 separate open risks,
   preserve failed evidence, isolate fixes, authorize delivery separately, and
   create a new release-bound retest attempt.
5. **Drift-proof authorization and retention — RESOLVED.** Lines 398-413,
   449-459, and 621-648 bind expected/actual identity, expiry, executor, quotas,
   abort-on-drift, retention ownership, hashes, redaction validation, and
   lifecycle disposition.
6. **Exact evidence reuse and adaptive-agent reproducibility — RESOLVED.**
   Lines 378-392 and 566-577 version tester/judge/harness inputs, preserve
   adaptive deviations, bound repeats, require fresh release/core-flow proof,
   and restrict reuse to exact-identity evidence.

## Delta Verification Evidence

- Exact target: `git rev-parse HEAD` =
  `103f163b825b001d8554f063570d64cdba329937`.
- Exact design delta inspected:
  `git diff 21bebc2..103f163 --
  docs/superpowers/specs/2026-07-27-noor-agent-driven-e2e-acceptance-design.md`.
- Revised design lines inspected: 63-75, 81-164, 355-480, 502-648, and
  675-685.
- Repository contract evidence inspected:
  `.codex/scope-criterion-snapshot-template.json`,
  `.codex/stage-manifest-template.json`, and
  `scripts/orchestration/lint_stage_sizing.py:148-192,216-280`.
- No protected raw evidence, live/remote system, provider, deployment, product
  code, Beads mutation, or broader backlog review was needed.

## Final Verdict

**REVISE.** Four original findings are resolved; findings 1 and 3 are
substantively improved but remain blocked by the two new P1 state-model errors.
Both corrections are narrow design edits. No product-code change or wider
investigation is required before implementation planning can resume.

## Docs Reviewed

`docs-reviewed: updated` — the artifact now records the exact revised-design
delta, six dispositions, and two narrow required corrections. The design itself
was not edited by this reviewer.

## Graph Reviewed

`graph-reviewed: no-change-needed` — Graphify remains unconfigured and
`graphify-out/GRAPH_REPORT.md` is absent.

## Explicit Defers

- The two required design edits, implementation plan, Beads dependency changes,
  and any artifact generation remain with the root orchestrator.
- Review stops at the bounded delta; no wider requirements or backlog audit was
  performed.
