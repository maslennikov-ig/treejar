# Executor handoff: tj-uvld

Target: `/home/me/code/treejar`, Beads `tj-uvld`; implement in a dedicated
`codex/tj-uvld-*` worktree based on current main. Audit base was36c8613;
refresh ancestry/ownership first. Preserve the dirty primary checkout.
Audience: a new Codex executor in this repository; native model/effort controls
remain unchanged. Do not create a new chat or goal automatically.

## Goal

Implement and immediately test the owner-approved Zoho stock optimization:
changed-item reads every10min, one daily full reconciliation, and explicit
fresh selected-item reads before actual quotation creation. Complete the
cohesive local implementation, tests, review and local commits; prepare live
coverage/activation evidence at the authorized boundary.

## Context

Read AGENTS.md, .codex/orchestrator.toml and .codex/handoff.md first, then:

- `/home/me/code/treejar/docs/specs/zoho-stock-sync-optimization/spec.md`;
- `bd show tj-uvld`, related `bd show tj-4kot`;
- `docs/reports/2026-10-03-zoho-api-statistics.json` and the2026-10-03
  Zoho/monitoring code-review report named in the handoff.

The approved spec is the outcome/acceptance contract, AC01–AC12. Beads owns
status. Main/live was36c8613 at audit; no delivery approval was granted by the
planning request. Existing local cooldown fix07591b8b1dba05c2124af0468a089adc26efa717
is on codex/tj-4kot-zoho-cooldown. Reuse if absent; do not duplicate or close
the outside account-load incident. Monitoring tj-535g is a separate stream.

Baseline:13 pages every5min =3744 nominal calls/day.157/day is only the
single-page-delta + daily-full model.343 catalog products,306 snapshot matches
and250 stored IDs were measured; validate mapping completeness before narrowing scope. Current cache
expires in1h and quotation get_stock_bulk can serve cached data.

Official API sources and unresolved provider checks are in spec section2.
Modified-since and bulk interfaces are documented; stock-operation coverage
and actual bulk size are unverified. An earlier live preflight respected an
active cooldown and made no API calls. Do not invent results or endpoint limits.

## Success criteria

- Deliver AC01–AC12, with paged idempotent merge, atomic data/cursor publication,
  lock fencing, restart/cache lifecycle, unknown-vs-zero and stock lifecycle.
- Integrate real cache-bypass reads at the quotation path without changing
  consent, already-sent guards, business POST idempotency or deferral policy.
- Prove local user-path behavior and request counts, including fresh2 vs
  cached10, page2 failure, lost lease and429; mocks intercept all side effects.
- Run the spec's focused acceptance plus real disposable local Redis race
  tests; use repo stage closeout when a stage is opened. Reuse matching passing
  evidence; full suite/CI is for release. No disabled failing tests.
- Before optimized activation, prove provider coverage for stock-affecting
  operations. A local stub is not that proof. Keep proven full mode behind the
  eligibility gate when live evidence is unavailable; report the exact gap.

## Constraints

Write zone: spec section9. Preserve unrelated changes, catalog/price/embedding
ownership and test0665 isolation. No new paid service, model/prompt rewrite,
webhook setup, monitoring activation or production data cleanup.

Local edits, tests, read-only checks and local commits are authorized. Honor
cooldown; cached-token GET probes stop on429/401 without OAuth refresh.
Merge/deploy, stock test transactions in external organizations, access changes,
paid calls and real-user sends need current permission. Prepare runnable local
work and a concrete bounded diagnostic/activation packet before requesting it.

Do not treat preparing this handoff as implementation. Choose proportionate
skills and ownership under repo rules. Ask on material missing business facts
or authority, while continuing independent local work. Explicit user instructions
outrank skill guidelines; if a skill requires stopping, identify the exact rule.

## Output

Commit locally and write `docs/reports/<completion-date>-zoho-stock-sync-optimization.md`
with exact SHA, commands/results, request-count evidence, provider coverage,
measured batch limit, user behavior on normal/error paths and rollback.
Update Beads and current handoff (<=200lines), repin mutable-source digests,
trigger enrolled GitHub sync. Preserve task status while required gates remain.
Copy the approved spec/prompt into your owned branch if needed; the primary
checkout contains these newly authored files and unrelated untracked work.
The planning files are also retained on `codex/tj-uvld-spec`; reuse that
documentation commit when it is absent from your implementation base.

Final response in Russian: behavior delivered, how verified, exact remaining
gate and concrete next action. Separate local_verified, provider_coverage_verified,
live_activated and live_24h_measured. Do not claim deployed savings from a fixture.

## Stop

Stop at genuinely missing external authority/input after finishing independent
local work. Do not silently substitute a less complete design or close the
task on an unverified coverage assumption. Otherwise continue through the
complete local implementation and focused acceptance, not just a plan.
