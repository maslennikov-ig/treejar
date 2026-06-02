# Stage tj-gh48: Expected Answer Frames

Updated: 2026-06-02
Status: planning package prepared; `tj-gh48.1` closed
Branch: `codex/tj-gh48-expected-answer-frames`
Base: `origin/main` at `428deed` or later current `main`
Beads: `tj-gh48`, `tj-gh48.1` through `tj-gh48.7`

## Goal

Replace narrow last-question-only routing with durable expected-answer frames in
the existing Dialogue State Kernel. This is the fundamental follow-up to the
GitHub #47 hotfix: Noor should remember what answer it is waiting for across a
bounded number of turns and interruptions, while still preserving hard
escalation paths and legacy fallback.

## Routing Result

- Documentation: prior docs research used first-party LangGraph memory and
  persistence docs, Rasa Forms slot-filling/unhappy paths, Microsoft Bot
  Framework dialog state/waterfall dialogs, and OpenAI Structured Outputs. No
  additional version-sensitive lookup was needed for this planning-only pass.
- Knowledge Graph: not configured/not relevant - no `graphify-out/GRAPH_REPORT.md`
  or `[knowledge_graph]` configuration is present.
- Selected skills: `orchestrator-stage`, `task-router`, `writing-plans`,
  `senior-prompt-engineer`, `verification-before-completion`.
- Selected agents/personas for the next executor: built-in `worker` for state,
  matcher, runner, and eval streams; orchestrator sequential owner for
  `src/llm/engine.py`; read-only `correctness_reviewer` and
  `improvement_reviewer` after local green.
- Catalog candidates: none - installed repo skills and built-in roles are
  sufficient.

## Parallel Decomposition Matrix

| Stream | Beads | Goal | Owner | Write zone | Dependencies | Verification | Decision |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A | `tj-gh48.2` | State schema and reducers | worker high reasoning | `src/dialogue/state.py`, `src/dialogue/reducer.py`, state tests | `tj-gh48.1` | `tests/test_dialogue_state.py` | parallel after spec |
| B | `tj-gh48.4` | Matcher/interruption policy | worker high reasoning | `src/dialogue/expected_answers.py`, matcher tests | A interface | matcher tests | parallel after A |
| C | `tj-gh48.3` | Frame capture/proposals | worker high reasoning | `src/dialogue/runner.py`, runner tests | A interface | runner tests | parallel after A |
| D | `tj-gh48.5` | `process_message` integration | orchestrator sequential | `src/llm/engine.py`, engine tests | B+C | targeted LLM tests | sequential due central routing |
| E | `tj-gh48.6` | Replay/stress suite | worker/local | fixtures and replay tests | B plus docs | replay tests | parallel after B |
| F | `tj-gh48.7` | Review, delivery, shadow E2E decision | orchestrator + reviewers | artifacts, handoff, read-only review | D+E | full gates, smoke/E2E if approved | sequential final |

## Documentation Updated

- `docs/specs/dialogue-state-kernel.md`: added `ExpectedAnswerFrame` durable
  state, frame lifecycle, matcher contract, graph steps, route contract,
  side-effect policy, #47 coverage, and rollout gates.
- `docs/specs/dialogue-state-kernel-evals.md`: added #47 delayed-answer replay,
  ambiguity, expiry, hard-blocker override, and long-dialog expected-frame
  acceptance requirements.
- `docs/superpowers/plans/2026-06-02-expected-answer-frames.md`: implementation
  plan for the next agent.

## Beads Created

- `tj-gh48`: epic.
- `tj-gh48.1`: spec/eval/docs planning, closed.
- `tj-gh48.2`: state schema and reducers.
- `tj-gh48.3`: frame capture from assistant decisions.
- `tj-gh48.4`: answer matcher and interruption policy.
- `tj-gh48.5`: legacy bridge / `process_message` integration.
- `tj-gh48.6`: replay fixtures and stress suite.
- `tj-gh48.7`: review, delivery, production shadow E2E, decision report.

Dependency chain:

- `tj-gh48.2` depends on `tj-gh48.1`.
- `tj-gh48.3` and `tj-gh48.4` depend on `tj-gh48.2`.
- `tj-gh48.5` depends on `tj-gh48.3` and `tj-gh48.4`.
- `tj-gh48.6` depends on `tj-gh48.1` and `tj-gh48.4`.
- `tj-gh48.7` depends on `tj-gh48.5` and `tj-gh48.6`.

## Constraints

- Do not remove the legacy runtime.
- Keep production `dialogue_kernel_mode=shadow` unless explicit approval enables
  a narrow enforce rollout.
- Do not close #11; it remains blocked on policy answers.
- No deploy, production mutation, live WhatsApp test, or production config change
  without explicit current-task approval.

## Verification

Completed for this planning branch:

- `python3 -m json.tool tests/fixtures/dialogue/dialogue_state_kernel_replay.json`
  passed.
- `uv run python scripts/orchestration/validate_artifact.py .codex/stages/tj-gh48/artifacts/tj-gh48.1-planning.md`
  passed.
- `bd dep cycles` passed, no dependency cycles detected.
- `scripts/orchestration/run_process_verification.sh` passed.
- `git diff --check` passed.
