# Orchestrator Handoff

Updated: 2026-07-28
Current branch: `codex/tj-r1f3-release-candidate`
Current stage id: `tj-r1f3`
Current stage status: accepted and closed after exact deployment/readback,
failed attempt preservation, isolated fix, and passing 5/5 provider retest

## Current Truth

- Canonical runtime: `https://noor.starec.ai`.
- The deployed code release is
  `0dd9615a16fdf4eb17abe156551c53fb77f39c21`.
- `origin/main` is `ac552023a647656777734f2109e0a93b8fa453d8`.
  Its one later commit changes only the smoke harness, tests, and evidence, so
  CI correctly skipped a second product deploy.
- GitHub Actions run `30330683062` passed lint, type-check, tests, and deploy
  for the runtime release. Run `30331481790` passed lint, type-check, and tests
  for the harness-only commit.
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

Recommended action: integrate the accepted policy-v2/provenance delivery
candidate, refresh its frozen Beads provenance after the `tj-r1f3` closure,
then execute the approved E2E plan from its exact authorization manifest.

- Local preparation for `tj-ee5f.1` may proceed from `main`.
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
