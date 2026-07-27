# tj-ee5f.3 SDD brief — generic acceptance policy v2

Status: approved-lineage implementation brief  
Base: `e9a1888`  
Immediate consumer: the later authorized `tj-ee5f.1` acceptance execution  
Public facade: local manifest compiler, dry-run runner, immutable evidence store,
trusted rollups, typed Russian report serializer, and strictly local CLI  
Non-goals: live/provider/model/customer/production/Wazzup/Zoho/CRM/quotation/
order/callback/deploy/cleanup/PDF actions

## Settled design

Three approaches were considered:

1. Compile a versioned, code-owned typed policy asset against the immutable Task 1
   scope, traceability, and scenario set. This is selected because it makes every
   canonical checkpoint, prohibited outcome, criterion, permission, and readback
   reciprocal and schema-verifiable.
2. Keep Python scenario dictionaries. Rejected because policy and fixtures can
   drift independently and the returned implementation proved that one scenario
   can become a hidden special case.
3. Let a model or caller classify free-form assertions. Rejected because semantic
   safety, commercial, manager, and side-effect decisions would become
   self-authorized and non-reproducible.

`TrustedAcceptanceRegistry` is the only public trust center. It opens the exact
Task 1 files, versioned execution-policy manifest, authorization/preflight
binding, evidence index, and protected external anchors itself. It exposes
immutable compiled-policy and verified-run views only after exact-set equality,
integrity, and reciprocal binding pass for all 20 scenarios, 9 evidence blocks,
and 30 criteria. Rollup/report APIs never accept caller scope IDs, planned
execution IDs, result rows, evidence roots, verified flags, or self-described
final readbacks.

The compiler validates an explicit typed DSL against a code-owned
capability/oracle registry. It never derives semantics from free text and never
branches on scenario ID. Typed oracle primitives distinguish text supplements
from structured event, tool, audit, classifier, and independent-readback
evidence. Production classifiers are named evidence dependencies; fixtures
cannot replace them with regexes, literals, `hard_safety`, or caller allowlists.

The runner validates the Task 1 authorization/preflight bundle, exact compiled
scenario plan, every planned/actual/adaptive turn, structured evidence, separate
baseline and final typed observations, post-action timestamps, and cumulative
immutable attempt quotas. The final observation must come from an independent
collector bound by preflight, exactly reconcile the baseline/final inventory,
and occur after the maximum delivered, final-visible, and action timestamp.
Evidence is raw/private outside Git and recursively redacted in Git, with
descriptor-relative no-follow reads/writes and an external protected anchor.
Rollups derive their scope only through the registry. The report accepts a
registry-issued strict typed payload, validates privacy after final
serialization, and creates a new file only through a no-follow descriptor chain.

## Invariant gate and focused matrix

- Canonical policy: exact 20 scenario IDs, 9 evidence-block IDs, 30 criterion IDs,
  and exact Task 1 evidence modes; no caller-supplied subset can redefine scope.
- Semantic safety: manager additions, commercial facts, prohibited outcomes, and
  side effects require structured evidence and named production classifiers where
  applicable; text checks are supplemental only.
- Temporal readback: baseline precedes actions; final readback is independently
  bound by source/timestamp/digest and follows every `final_visible_at`,
  `delivered_at`, and action timestamp.
- Attempt integrity: prior tracked bytes, index, checksums, quota totals, and
  retest chain match a protected external `O_EXCL` anchor before append. Every
  adapter action first enters protected `reserved`; quota is consumed for
  `reserved`, `failed`, and `unknown`, and `unknown` blocks closeout. Attempts
  use protected intent → raw → tracked → commit, with recovery recording an
  explicit aborted disposition instead of silently deleting partial state.
- Execution causality: the protected phase machine is exactly
  `prepared → baseline_sealed → executing → final_turn_anchored →
  final_readback_sealed → evaluated → attempt_committed`. Each transition binds
  the prior event digest and monotonic cursor; timestamps alone never prove
  order.
- Authorization v2: the executor rejects v1 and binds the policy digest,
  compiler identity, compiled-plan digest, exact canonical 29 execution IDs,
  adapter IDs, evidence-store IDs, quotas, and protected registry identity.
- Criterion lattice: explicit `CriterionPlan` obligations retain all canonical
  owners and use `all_required`; unavailable owners remain `BLOCKED`, and only a
  valid Task 1 exclusion gate may produce `EXCLUDED_BY_CLIENT`. Authorization
  cannot shrink the canonical execution set.
- Filesystem/privacy: every parent is opened with `O_DIRECTORY|O_NOFOLLOW`; raw
  mode is `0600`; tracked payloads and final report are recursively redacted;
  existing or symlink output is refused.
- Outcome semantics: `BLOCKED` and `EXCLUDED_BY_CLIENT` never become `PASS`;
  `fresh`, `reused_exact`, and `external_gate` retain their Task 1 rules.

Every DSL assertion also binds the SHA-256 of its exact canonical source text
and states `structured_required=true`; text supplements can never satisfy it.

Mandatory RED matrix covers all returned-review bypasses: all 19 non-opening
scenarios, manager-draft semantic addition, stale final readback, 1-of-30 and
partial-execution rollups, intermediate-parent symlink, authorization/preflight
drift, actual/plan/oracle drift, all quota dimensions and cumulative retests,
anchor/index/checksum tampering, recursive redaction, side-effect closeout, and
exclusive report output. It additionally covers pre-action reservation,
unknown-action closeout, multi-owner criterion lattice, v1 authorization
rejection, exact 29-ID binding, event-cursor causality, text-only structured
assertion rejection, and interrupted two-phase attempt recovery.

## Technical premortem

Verdict: **GO WITH CONDITIONS**. The change is local and reversible, but it
crosses authorization, file-format, privacy, and immutable-evidence boundaries.

| Failure symptom | Evidence | Mechanism / affected surface | Detection | Mitigation / disposition |
|---|---|---|---|---|
| One scenario bypasses policy | confirmed by returned Task 2 | scenario-specific code path | exact-set compiler tests | generic compilation; block |
| Unsafe manager/commercial claim passes | confirmed by final review | text-only oracle or self-declared safety | semantic-addition RED | structured evidence plus named classifier; block |
| Old state is presented as final | confirmed by final review | pre-run readback reused after turns | timestamp-order RED | separate baseline/final documents; block |
| Partial run reports complete | confirmed by final review | caller-selected scope | 1-of-30 and partial-ID RED | canonical scope loaders only; block |
| Symlink escapes output root | confirmed by final review | only leaf checked | intermediate-parent RED | descriptor chain; block |
| Append rewrites history or resets quotas | confirmed by prior corrections | Git-tracked evidence trusted alone | tamper/retest RED | protected external anchor and cumulative ledger; block |
| Executor drifts into live systems | plausible, material | CLI gains adapter/network path | CLI contract and import scan | local fixtures only; preflight |

Recovery is branch deletion or reverting atomic commits; no external state is
created. A failed invariant test stops delivery. Environment proof remains a
later, separately authorized stream.

## Execution decomposition

| Stream | Write zone | Dependency | Verification | Decision |
|---|---|---|---|---|
| Policy/contracts | policy asset, schemas, compiler, tests | Task 1 immutable inputs | schema and compiler RED/GREEN | sequential local |
| Runner/evidence | runner, evidence, tests | compiled policy types | runner/evidence RED/GREEN | sequential local |
| Rollup/report/CLI | report, CLI, tests/docs | trusted evidence outputs | report/CLI RED/GREEN | sequential local |

All streams share public types, fixtures, and one release verification boundary,
so parallel writes would create contract conflicts and duplicate broad
verification. No subagent is used.
