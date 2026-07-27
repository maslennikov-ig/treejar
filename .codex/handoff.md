# Orchestrator Handoff

Updated: 2026-07-28
Current branch: `codex/tj-ee5f-delivery`
Current stage id: `tj-ee5f`
Current stage status: reviewed local Task 1, policy-v2, privacy cleanup, and
`tj-r1f3` implementation integrated; stage remains open pending canonical
delivery and fresh external `tj-r1f3` proof

## Current Truth

- Canonical runtime: `https://noor.starec.ai`.
- The deployed code release is
  `b8de75c215d2678eb8d2cff06f91a49e48e0e4a9`.
- `origin/main` contains that release plus later documentation/evidence-only
  handoff commits. Those path-ignored commits intentionally did not redeploy
  production.
- GitHub Actions run `30283789902` passed lint, type-check, tests, and deploy.
- Final local release gate passed Ruff, format, Mypy over 162 source files,
  process verification, and Pytest: `1624 passed, 19 skipped`.
- Production health is `ok`, version `0.4.0`; app, worker, nginx, Redis, and
  PostgreSQL are running. Redis returned `PONG`, PostgreSQL accepts
  connections, and public API verification passed `8/8`.
- Production models remain:
  - main: `z-ai/glm-5.2`;
  - fast: `deepseek/deepseek-v4-flash`.
- Production `.env` remains mode `600`, owned by `noor-dev:noor-dev`.
- Wazzup is connected; protected Zoho CRM and Inventory refresh credentials
  survived the deployments.
- Graphify is optional but not configured;
  `graphify-out/GRAPH_REPORT.md` is absent.

## Grounding blocker

- Beads `tj-r1f3` remains `in_progress` and P1.
- Deterministic customer-output enforcement and expanded evaluator semantics
  were corrected through TDD and accepted independent review, then integrated
  locally into `codex/tj-ee5f-delivery`.
- Full local release proof on the reviewed source branch passed Ruff, format,
  Mypy, process verification, and Pytest.
- Canonical integration/delivery, deploy/readback, and one freshly authorized
  bounded provider smoke with manual semantic review remain outstanding.
- Three post-deploy smoke attempts are preserved under
  `.codex/stages/tj-r1f3/results/`.
- Final attempt on `b8de75c` made exactly five paid synthetic calls and no
  customer, Wazzup, Zoho, CRM, quotation, order, or other business mutation.
- Script result was `4/5`: GLM-5.2 again offered experiencing the specific Nova
  chair in the showroom after correctly declining an unsupported medical
  claim.
- Manual evidence review also found a delegated future stock-check promise
  that the deterministic evaluator did not flag; effective semantic result is
  `3/5`.
- Two bounded correction cycles are exhausted. Replan around reliable
  customer-output enforcement and expand delegated-future-check detection;
  do not continue wording-only prompt patches inside the old loop.
- Exact evidence and disposition:
  `.codex/stages/tj-r1f3/results/postdeploy-verification.md`.

## E2E acceptance preparation

- Epic: `tj-ee5f`.
- Execution task: `tj-ee5f.1`, blocked by `tj-r1f3`.
- Task 1 immutable contracts and the reviewed generic policy-v2 trust boundary
  are integrated locally.
- The current tracked tree redacts the protected historical test identity and
  live scripts require an explicit validated destination; Git-history exposure
  remains an explicit destructive-action defer.
- `.codex/stages/tj-ee5f/stage-manifest.json` registers Task 1, policy-v2, and
  the privacy artifact. The stage remains `in_progress`.
- Beads `tj-ee5f.2` and `tj-ee5f.3` are closed after combined-tree acceptance;
  `tj-ee5f` and `tj-ee5f.1` remain open.
- Combined-tree integration gates passed: acceptance `192 passed` with exactly
  two frozen Task 1 source-provenance checks deselected after they were first
  observed failing closed; `tj-r1f3` `612 passed`; privacy slice `92 passed`;
  full Pytest `2069 passed, 19 skipped, 2 deselected`; Ruff, format, Mypy,
  process verification, artifact validation, stage sizing, and stage-ready
  checks passed.
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

Recommended action: finish review and delivery of the integrated local
`tj-r1f3` output-enforcement release, then obtain fresh exact authorization for
deploy/readback and the bounded provider smoke before executing the approved
E2E plan.

- Local preparation for `tj-ee5f.1` may proceed from `main`.
- Mutation-capable E2E cannot begin until `tj-r1f3` closes with a freshly
  deployed passing release and the exact live authorization manifest is
  approved.
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

- `tj-r1f3`: production grounding/output-enforcement blocker for
  mutation-capable E2E.
- `tj-qy7y`: compatible PostCSS/NanoID security update in the trusted frontend
  build chain.
- `tj-n8p6`: pre-existing Ruff drift in orchestration scripts.
- `tj-b93r`: weak-catalog grounding follow-up.
- Referral launch `tj-final27.6`, WABA approval `tj-gh21`, catalog GH #54
  `tj-2pkk`, soft/hard escalation policy `tj-g3f`, delivery-source policy
  `tj-9q0`, and Zoho UTM mapping `tj-hye` remain separate.
