# Orchestrator Handoff

Updated: 2026-07-27
Current branch: `main`
Current stage id: `tj-ee5f`
Current stage status: design, independent review, implementation plan, Beads
execution task, and launcher prompt prepared; live execution blocked by
`tj-r1f3`

## Current Truth

- Canonical runtime: `https://noor.starec.ai`.
- Local `main`, `origin/main`, and the deployed release are
  `b8de75c215d2678eb8d2cff06f91a49e48e0e4a9`.
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
- Prompt-tail assembly, grounding language, and deterministic smoke semantics
  were corrected through TDD and an accepted independent delta review.
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

Recommended action: recover `tj-r1f3`, replan it around reliable
customer-output enforcement and delegated-future-check detection, then close
its deploy/smoke gate before implementing and executing the approved E2E plan.

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
