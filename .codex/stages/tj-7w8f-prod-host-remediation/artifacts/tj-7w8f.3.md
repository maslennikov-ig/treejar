---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-7w8f-prod-host-remediation/stage-manifest.json
stream_owner: prod-polska-jobs-worker
orchestration_level: inner_loop
scope_kind: foundation
immediate_consumer: root-orchestrator-production-remediation
public_facade: polska-systemd-scheduled-jobs
bounded_acceptance: offline-code-and-unit-validation-without-job-execution
non_goals:
  - manual-job-or-timer-start
  - scraper-sync-or-paid-model-call
  - database-write
  - deploy-restart-reload-or-host-file-change
evidence:
  - none
task_id: tj-7w8f.3
epic_id: tj-7w8f
stage_id: tj-7w8f-prod-host-remediation
session_id: prod-polska-jobs-diagnosis
milestone: polska-job-root-cause-and-safe-remediation
milestone_status: replan-required
agent_type: custom
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: Cross-service production diagnosis inherited the orchestrator model and reasoning because no override was authorized.
repo: treejar
branch: codex/prod-polska-jobs-remediation
base_branch: main
base_commit: 25598101f33f47c9d1117499daeb1f4a02928046
worktree: /home/me/code/treejar/.worktrees/prod-polska-jobs
write_zone:
  - .codex/stages/tj-7w8f-prod-host-remediation/artifacts/tj-7w8f.3.md
success_criteria:
  - identify-both-unit-failure-surfaces-and-exact-known-exits
  - identify-owner-runtime-path-and-source-lineage-gap
  - provide-smallest-safe-fix-rollback-and-offline-validation
  - leave-production-host-and-running-sync-untouched
selected_docs:
  - AGENTS.md
  - .codex/orchestrator.toml
  - .codex/handoff.md
  - README.md
  - .codex/stages/tj-7w8f-prod-host-remediation/stage-manifest.json
selected_skills:
  - systematic-debugging
selected_agents:
  - none
catalog_candidates:
  - none
parallel_group: production-host-remediation
depends_on_streams:
  - none
parallel_decision: parallel
status: returned
delivery_method: not accepted
accepted_by_orchestrator: no
cleanup_status: pending
cleanup_notes: Dedicated worktree and branch remain for root review; production was not changed.
risk_level: high
verification_tier: inner
risk_tags:
  - data
  - rollback
  - state-transition
affected_surfaces:
  - backend
  - data
invariants:
  - rollback
  - state-transition
  - test-matrix
docs_impact: ops-deploy
docs_reviewed: no-change-needed
docs_review_notes: This read-only diagnosis changes only its tracked stream artifact; root owns stage and handoff state.
verification:
  - sanitized-systemctl-show-and-cat-for-both-services-and-timers: passed
  - bounded-sanitized-cbosa-application-log-read: passed
  - bounded-journal-read: blocked-by-noor-dev-journal-acl
  - owner-path-git-and-file-metadata-read: passed
  - python-dependency-executable-and-ast-read-only-checks: passed
  - systemd-analyze-verify-current-units: passed-with-unrelated-xray-warning
  - bash-n-current-sync-execstart: passed
  - existing-dry-run-or-offline-job-mode-audit: failed-no-safe-mode-exists
  - current-sync-process-read-only-snapshot: passed-active-and-untouched
  - local-git-object-and-current-tree-provenance-search: passed-zero-matches
  - authenticated-github-code-search-across-configured-account-and-orgs: passed-zero-matches
  - deployment-release-marker-and-reference-search: passed-zero-provenance-markers
  - bounded-live-cbosa-get-with-current-request-construction: confirmed-403-text-html-blocked
  - bounded-live-cbosa-post-comparison: not-run-required-stop-after-get-403
changed_files:
  - .codex/stages/tj-7w8f-prod-host-remediation/artifacts/tj-7w8f.3.md
explicit_defers:
  - canonical-polska-source-repository-and-release-lineage-are-unresolved
  - prior-polska-sync-child-at-timeout-is-unconfirmed-because-journal-is-inaccessible-and-systemd-state-was-overwritten-by-current-run
  - live-source-probes-job-execution-database-validation-paid-calls-and-production-mutation-require-separate-authority
---

# Summary

Read-only production diagnosis found two distinct failures under the Polska
owner at `/opt/polska/app` (system user `vic`), not in the Treejar runtime.
The deployed directory has no `.git` metadata, and no canonical Polska source
checkout or remote was found in accessible host or local paths. Production must
not be edited until that source and rollback lineage are established.

The follow-up provenance search remained negative and bounded. Both unique
collector filenames and both unit names are absent from every reachable Git
object and current tracked tree under `/home/me/code`. Authenticated GitHub code
search returned `total_count=0` for `collect_cbosa`, `collect_eli_texts`,
`polska-cbosa-night`, `polska-sync.service`, and `polska.starec.ai` across the
configured account and its accessible organizations (78 user repositories, 9
`aidevteam-labs` repositories, and 11 `rechkaai` repositories; the other
configured organization exposed none). `/opt/polska` has no Git directory,
release SHA, commit, revision, deployment manifest, or GitHub/deploy reference;
only the single deployed copies of both collectors exist there. `/home/vic` is
mode `0750`, so an owner-only checkout there cannot be ruled out by `noor-dev`.
The canonical repository, commit, and deployment mechanism therefore remain a
proved access/lineage blocker rather than an unidentified local candidate.

Hashes that can later match an authoritative source or rollback package are:

- `collect_cbosa.py`: `c32bc02bedb3dac37d4e24465a886622d4ab4bc0eb83f3e11fe5d1c3d35e7c06`
- `collect_eli_texts.py`: `e7729e0f828f7323387dd58b4026d7e5c4402fcf11fa575ab6cfb13d4ea50968`
- `polska-cbosa-night.service`: `5a13c89b4b397de59df0cbe882fa1b7c9d6e2f35cb0583b3dee01075e0cfd7db`
- `polska-sync.service`: `f2fa8f3acbc3756e1eaf74c62ecad161e72e747da357b343548bf2ca6a430db9`

`polska-cbosa-night.service` has a confirmed upstream-block failure. Its exact
command is:

`/opt/polska/app/venv/bin/python parser/collectors/collect_cbosa.py --year-from 2026 --year-to 2022 --rps 0.25`

The 2026-08-27 invocation ran from 01:00:49 to 01:56:37 UTC and exited with
`ExecMainCode=1`, `ExecMainStatus=1`, `Result=exit-code`. The bounded application
log ends at `collect_cbosa.py:179`: the initial CBOSA search receives repeated
HTTP 403 responses, with occasional remote disconnects; after ten sleeps
totalling 3,345 seconds, `Cbosa.get()` raises an uncaught `RuntimeError` at line
99. Recreating the same `requests.Session` and User-Agent cannot clear a
source/IP policy block and amplifies it with repeated traffic. Confidence:
high. A disconfirming test would be an explicitly authorized, single bounded
comparison of the required request method/session from an approved source path;
no such request was made during the initial diagnosis.

A later explicitly authorized bounded live diagnostic from the same production
host confirmed the source boundary without crawling. It created the current
collector's exact Session/User-Agent and search fields for one representative
2026-08 monthly window, disabled application-level retries, and issued one GET
to the official `/cbo/search` endpoint. The only recorded response facts were
`status=403`, `content-type=text/html`, `classification=blocked`; no body,
cookies, URL, result count, or identifiers were output. The diagnostic stopped
immediately as required. No POST was sent, so whether POST changes the outcome
is intentionally unknown. Verdict: the live evidence confirms the production
source block and does not confirm a GET-to-POST code fix. Production code/unit
mutation remains NO-GO until source access and canonical ownership are resolved.

`polska-sync.service` is a separate duration and observability defect. Its
single `ExecStart=/bin/bash -c` chains these commands with semicolons:

1. `parser/collectors/sync_eli.py`
2. `parser/collectors/collect_eli_texts.py --workers 2 --rps 2 --limit 5000`
3. `parser/scripts/translate_titles.py --workers 2`
4. `parser/collectors/collect_tk.py`
5. `parser/collectors/collect_kio.py --year-from 2026 --year-to 2026`

The prior failure was reported at 2026-08-26 10:30 UTC, exactly six hours after
the timer's 04:30 UTC schedule, while the unit declares `TimeoutStartSec=6h`.
This is strong evidence that systemd terminated the pipeline for exceeding its
start timeout, rather than a captured child exit. The exact child active at
that earlier timeout and its signal/status are unconfirmed: `noor-dev` cannot
read the system journal, the initial snapshot retained only the final systemd
failure line, and today's timer invocation overwrote the previous execution
state. At the latest 2026-08-27 06:28:29 UTC snapshot, today's natural run had
not completed: `ActiveState=activating`, `SubState=start`, no exit timestamp,
and it remained inside `collect_eli_texts.py` after 1h58m. Its provisional
`Result=success`, `ExecMainCode=0`, and `ExecMainStatus=0` are not a completed
success result. The process was untouched. Confidence: high for the unit timeout,
low for which child consumed the remaining prior budget. The next diagnostic
step is a bounded, sanitized journal read by an account already authorized for
the journal after the current run finishes naturally.

There is also a confirmed independent control-flow defect: shell `;` means an
intermediate collector failure is ignored and the service normally returns only
the last KIO command's status. Raising the six-hour timeout alone would preserve
that masking, extend partial-write exposure, and allow the unbounded translation
step to make paid OpenRouter calls longer. It is not a safe root-cause fix.

# Verification

Normal read-only path:

- Both timers are enabled and active. CBOSA waits for its next natural 01:00 UTC
  schedule; sync is `active/activating` under today's natural 04:30 UTC trigger.
- The exact interpreter, Bash, curl, pdftotext, Python modules, and all six
  relevant scripts are present. AST parsing passed without imports or bytecode
  writes. Current units pass `systemd-analyze verify`; its only output concerned
  unrelated `xray.service`. The exact sync shell command passes `bash -n`.
- Unit and script mtimes are 2026-07-12 through 2026-07-15, while the failures
  are from 2026-08-26/27. No recent local code/unit change explains them. The
  July M0 report says CBOSA POST/GET worked then, so the current 403 is consistent
  with external behavior or host-policy drift; changing GET to POST remains a
  hypothesis, not a proven fix.
- The repository search covered current local checkouts and all their reachable
  Git objects, then authenticated GitHub code search for the unique filenames,
  unit names, and product hostname across the configured user and organization
  scope. All searches returned zero candidates. Deployment metadata searches
  found no release/commit marker or repository reference. This is sufficient to
  stop the search safely; scanning owner-private home contents or shell history
  would cross the granted access and secret boundary.

Failure path:

- The CBOSA log proves repeated 403/disconnect handling reaches an uncaught
  exception and status 1 after almost exactly the retry sleep budget.
- One later bounded request from the production host independently reproduced
  `403 text/html` with the current GET construction and no retry. The required
  stop prevented a POST comparison. This confirms recurrence and rejects any
  claim that changing only the method is already proven to restore collection.
- The sync schedule plus failure timestamp and `TimeoutStartSec=6h` prove the
  six-hour failure boundary. The unavailable prior journal prevents claiming a
  specific child or signal as confirmed.

Integration edge and safe acceptance design:

- None of the current jobs has a true `--dry-run`, offline, or no-write mode.
  `--limit` is not safe validation: collectors still connect to production,
  write files/database state, scrape external sources, and the translation step
  may make paid calls. No job, timer, provider call, source probe, database
  query/write, reload, restart, reset, or deploy was performed.
- In the canonical Polska source repository, first add offline tests with fake
  HTTP, fake database, fake filesystem, fake translator, and fake child
  executables. For CBOSA, assert that 403/CAPTCHA opens a circuit immediately,
  preserves the unfinished cursor, performs no upsert, and reports a distinct
  blocked-source result. For sync, assert ordered fail-fast behavior, per-step
  status, a bounded total budget, no later step after failure, and no provider
  invocation in validation mode.
- Stage candidate units/scripts in a temporary non-production directory and run
  AST/unit tests, `bash -n`, and `systemd-analyze verify` there. This is the only
  currently safe focused validation. Root may then separately authorize a
  reversible production install and observe the next natural timer; manual
  collection is not needed for acceptance.

# Delivery / Cleanup

Only this artifact is delivered for root review. No host file, service state,
timer state, process, database, external source, or repository outside the
strict write zone was changed. The naturally running sync process was not
signalled or otherwise interfered with.

# Risks / Follow-ups / Explicit Defers

- **Must-fix, P1, high confidence — CBOSA circuit behavior:** stop retrying 403
  and CAPTCHA as transient network errors. Preserve the cursor and expose a
  distinct source-blocked state. This reduces ban amplification and wasted
  56-minute runs, but does not restore collection. Resolve source access through
  an approved endpoint/allowlist or an evidence-backed request/session change;
  do not guess headers, bypass CAPTCHA, or silently map the block to success.
  Confirmed fix verdict: **no restoring fix is validated yet**. The circuit
  change is a high-value failure-containment fix only; source restoration needs
  an owner-approved access path and a separately bounded acceptance request.
- **Must-fix, P1, high confidence — sync scheduling:** replace the inline
  semicolon chain with a versioned, fail-fast owner script or separate units.
  Give each step an explicit budget and status. Bound text and translation work
  so the whole daily slice finishes inside its timer window; separate backlog
  processing from the daily delta. Do not merely increase `TimeoutStartSec`.
- **Must-fix before mutation, P1, high confidence — ownership:** identify the
  canonical Polska repository, release SHA, deploy mechanism, and owner. The
  current `/opt/polska/app` copy has no Git provenance. Expected risk reduction:
  reviewable changes and deterministic rollback instead of an unowned host hotfix.
- **Rollback:** before any later authorized install, create explicit mode-0600
  backups of every touched owner script and unit, record hashes and metadata,
  and change only one service stream at a time. Roll back by restoring those
  exact files, verifying staged unit syntax, reloading systemd only with separate
  authority, and leaving collection for the next natural schedule. A code-level
  release rollback is preferred once the owner repository is known.
- **Residual risk:** current sync may again reach its six-hour boundary at
  10:30 UTC. It was intentionally left alone. Its paid translation and partial
  database/file commits are existing behavior, not activity initiated here.
  Root should capture its final non-secret result and an authorized sanitized
  journal excerpt before choosing the per-step budget.
