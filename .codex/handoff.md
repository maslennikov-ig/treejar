# Orchestrator Handoff

Updated: 2026-07-28
Current branch: `main`
Current stage id: `tj-ee5f`
Current stage status: the reviewed local production trust facade is integrated
and full local gates are green; stage remains open for real Task 3 transports,
exact production execution, client report acceptance, and PDF delivery

## Current Truth

- Canonical runtime: `https://noor.starec.ai`.
- The deployed code release is
  `0dd9615a16fdf4eb17abe156551c53fb77f39c21`.
- `origin/main` is `eab36e32e9bba16270d388cb2683eebca6f402d8`.
  Commits after the runtime release change only the smoke harness, tests, and
  evidence, so CI correctly skipped a second product deploy.
- GitHub Actions run `30330683062` passed lint, type-check, tests, and deploy
  for the runtime release. Run `30331481790` passed lint, type-check, and tests
  for the harness-only commit.
- Run `30332045845` passed lint, type-check, and tests for final `tj-r1f3`
  evidence commit `eab36e3`; deploy was correctly skipped.
- Final local release gate passed Ruff, format, Mypy over 163 source files,
  process verification, and Pytest: `1878 passed, 19 skipped`.
- Production health is `ok`, version `0.4.0`; app, worker, nginx, Redis, and
  PostgreSQL are running. Redis returned `PONG`, PostgreSQL accepts
  connections, and read-only public health/API guard verification passed.
- Production models remain:
  - main: `z-ai/glm-5.2`;
  - fast: `deepseek/deepseek-v4-flash`.
- Production `.env` remains mode `600`, owned by `noor-dev:noor-dev`.
- Wazzup is connected; protected Zoho CRM and Inventory refresh credentials
  survived the deployments.
- Graphify is optional but not configured;
  `graphify-out/GRAPH_REPORT.md` is absent.

## Grounding acceptance

- Beads `tj-r1f3` is closed.
- Deterministic customer-output enforcement and shared evaluator semantics were
  corrected through TDD and accepted independent review.
- Attempts 1–4 remain immutable failed evidence under
  `.codex/stages/tj-r1f3/results/`.
- Attempt 4 on runtime `0dd9615` consumed exactly five paid synthetic calls,
  made zero retries, performed no business mutation, and returned 4/5.
- Diagnosis proved the deployed guard safely repaired the exact failure and
  isolated a smoke-harness prompt-tail mismatch.
- Harness commit `ac55202` aligned the synthetic prompt with the production
  final-tail helper and passed CI.
- A new separately quota-bound attempt 5 consumed exactly five paid synthetic
  calls, made zero retries, performed no business mutation, and passed
  deterministic plus manual semantic review 5/5.
- Exact evidence and disposition:
  `.codex/stages/tj-r1f3/results/postdeploy-verification.md`.

## E2E acceptance preparation

- Epic: `tj-ee5f`.
- Execution task: `tj-ee5f.1`, unblocked by the accepted `tj-r1f3` proof.
- Task 1 immutable contracts and the reviewed generic policy-v2 trust boundary
  are integrated locally.
- Task 2 production trust facade is integrated at `3074999`. It provides the
  exact 29-unit coordinator lifecycle, protected producer recovery, derived
  materialization, criterion-scoped evidence, defect ledger, and local fake
  adapter/collector proof.
- Final Task 2 independent review found `0 P0`, three corrected `P1`, and one
  explicitly deferred non-blocking `P2`. The final acceptance suite passed
  `360`; full Pytest passed `2240` with `19 skipped`; Ruff, format, Mypy over
  163 source files, process verification, artifact validation, diff and privacy
  scans passed.
- Real HTTP/SSH transports and production attempt, gate, reconciliation, and
  inventory producers are not implemented. Fake output is not production E2E
  evidence and cannot be used for the client report.
- The current tracked tree redacts the protected historical test identity and
  live scripts require an explicit validated destination; Git-history exposure
  remains an explicit destructive-action defer.
- `.codex/stages/tj-ee5f/stage-manifest.json` registers Task 1, policy-v2, and
  the privacy artifact. The stage remains `in_progress`.
- Beads `tj-ee5f.2` and `tj-ee5f.3` are closed after combined-tree acceptance;
  `tj-ee5f` and `tj-ee5f.1` remain open.
- The two frozen Task 1 provenance checks first failed closed on the expected
  source drift, then passed after exact Beads/source-digest refresh and the
  versioned closed-dependency transition.
- Current combined-tree gates pass acceptance `194` with no deselections,
  manifest contracts `43`, and full Pytest `2072 passed, 19 skipped`; Ruff,
  format over 315 files, Mypy over 163 source files, and process verification
  also pass.
- Current-tree exact and separator-normalized privacy scans found zero matches,
  and none of the six commits unique to the contaminated returned Task 2 branch
  is present in delivery ancestry.
- Accepted design:
  `docs/superpowers/specs/2026-07-27-noor-agent-driven-e2e-acceptance-design.md`.
- Accepted independent design review:
  `.codex/stages/tj-ee5f/artifacts/tj-ee5f-design-review.md`.
- Implementation plan:
  `docs/superpowers/plans/2026-07-27-noor-agent-driven-e2e-acceptance.md`.
- English orchestrator prompt:
  `.codex/stages/tj-ee5f/orchestrator-prompt.md`.
- Prompt validation passed:
  `orch-prompts prompt-check --runtime codex --profile gpt-5.6 --kind fallback`.
- Architecture: isolated application-native scenario capsules, one
  longitudinal customer journey, separately authorized EN/AR provider-ingress
  canaries, immutable failed evidence, separate fix/deploy/retest streams, and
  a full external side-effect disposition ledger.
- Client evidence must retain every exact question/answer, timing, runtime and
  model identity, tools/audits, failures, fixes, and retests. Protected raw
  evidence stays outside Git; tracked evidence is redacted and checksummed.

## Next recommended

Next stage id: `tj-ee5f.1`

Recommended action: deliver `main@3074999`, add only the minimal real Task 3
HTTP/SSH and producer boundary from the accepted repair plan, bind the exact
runtime/test identities into the protected authorization manifest, then execute
the approved E2E sequentially.

- Task 3 implementation and execution proceed from `main@3074999`.
- Mutation-capable E2E remains gated by its own exact live authorization
  manifest, preflight, quota reservations, and side-effect policy.
- Acceptance execution never edits product code in place. A failure creates a
  Beads defect and isolated fix/delivery stream; the acceptance owner records
  a new immutable retest attempt against the new release.
- The future orchestrator decides whether subagents materially help; no agent
  count is prescribed.

## Starter prompt for next orchestrator

Use $orchestrator-stage with the complete English prompt in
`.codex/stages/tj-ee5f/orchestrator-prompt.md`.

## Approval gates

- The user's authorization in the completed turn covered the pushes, deploys,
  production readbacks, and bounded synthetic provider calls recorded above.
- A new agent/task must obtain current exact authorization before any live or
  paid call, customer-visible send, provider canary, production/CRM/Zoho/
  quotation/order mutation, callback, cleanup, deploy, destructive action, or
  permission expansion.
- Preserve protected credentials and unrelated user files.

## Explicit defers

- `tj-qy7y`: compatible PostCSS/NanoID security update in the trusted frontend
  build chain.
- `tj-n8p6`: pre-existing Ruff drift in orchestration scripts.
- `tj-b93r`: weak-catalog grounding follow-up.
- Referral launch `tj-final27.6`, WABA approval `tj-gh21`, catalog GH #54
  `tj-2pkk`, soft/hard escalation policy `tj-g3f`, delivery-source policy
  `tj-9q0`, and Zoho UTM mapping `tj-hye` remain separate.
