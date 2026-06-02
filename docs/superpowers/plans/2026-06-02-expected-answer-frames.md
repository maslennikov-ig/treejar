# Expected Answer Frames Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace last-question-only dialogue routing with durable expected-answer frames in the existing Dialogue State Kernel.

**Architecture:** Extend the current LangGraph kernel state with a bounded stack of `ExpectedAnswerFrame` objects. Capture frames when Noor asks a question, match customer turns against active frames before generic verified-policy handoff, keep production in `shadow` until replay and production traces prove safe behavior, and use `enforce` only for explicitly allowlisted flows.

**Tech Stack:** Python 3.12/3.13, Pydantic models, SQLAlchemy conversation metadata, LangGraph `StateGraph`, PydanticAI test models/mocks, pytest, Beads.

---

## File Structure

- Modify `src/dialogue/state.py`: add `ExpectedAnswerFrame`, slot descriptors, match result models, and backward-compatible state loading.
- Modify `src/dialogue/reducer.py`: add pure frame lifecycle reducers.
- Create `src/dialogue/expected_answers.py`: deterministic frame matching, expiry, ambiguity, hard-blocker checks.
- Modify `src/dialogue/runner.py`: add `expire_frames` and `match_expected_answer` graph steps and route decisions.
- Modify `src/llm/engine.py`: capture frames after assistant/customer-visible questions and use frame-aware routing before verified-policy handoff.
- Modify tests: `tests/test_dialogue_state.py`, `tests/test_dialogue_runner.py`, `tests/test_llm_engine.py`, `tests/test_dialogue_replay_fixtures.py`.
- Modify fixtures: `tests/fixtures/dialogue/dialogue_state_kernel_replay.json` or split into focused `tests/fixtures/dialogue/*.json`.
- Update docs/artifacts: `docs/specs/dialogue-state-kernel.md`, `docs/specs/dialogue-state-kernel-evals.md`, `.codex/stages/tj-gh48/*`.

## Parallel Decomposition Matrix

| Stream | Beads | Goal | Owner | Write zone | Dependencies | Verification | Decision |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A | `tj-gh48.2` | State schema and reducers | worker, high reasoning | `src/dialogue/state.py`, `src/dialogue/reducer.py`, state tests | `tj-gh48.1` | `uv run pytest tests/test_dialogue_state.py -v --tb=short` | parallel after spec |
| B | `tj-gh48.4` | Matcher/interruption policy | worker, high reasoning | `src/dialogue/expected_answers.py`, matcher tests | `tj-gh48.2` interface | matcher unit tests | parallel after A interface |
| C | `tj-gh48.3` | Frame capture/proposal | worker, high reasoning | `src/dialogue/runner.py`, runner tests | `tj-gh48.2` | runner tests | parallel after A interface |
| D | `tj-gh48.5` | `process_message` integration | orchestrator sequential | `src/llm/engine.py`, engine tests | B+C | targeted LLM tests | sequential due central routing |
| E | `tj-gh48.6` | Replay/stress suite | worker or orchestrator | fixtures and replay tests | B plus docs | replay fixture tests | parallel after B |
| F | `tj-gh48.7` | Review, delivery, production shadow E2E | orchestrator + reviewer | read-only review, artifacts | D+E | full gates, smoke/E2E | sequential final |

## Task 1: State Schema And Reducers

**Files:**
- Modify: `src/dialogue/state.py`
- Modify: `src/dialogue/reducer.py`
- Test: `tests/test_dialogue_state.py`

- [ ] **Step 1: Write failing state tests**

Add tests that assert:

```python
def test_dialogue_state_loads_expected_answer_frames() -> None:
    metadata = {
        "dialogue_kernel": {
            "state": {
                "version": 1,
                "expected_answer_frames": [
                    {
                        "frame_id": "product_preference:test",
                        "flow": "product_selection",
                        "question_kind": "product_preference",
                        "prompt_key": "workspace_luma_novo_preference",
                        "status": "active",
                        "priority": 80,
                        "expected_slots": [
                            {
                                "slot": "workspace_preference",
                                "required": True,
                                "accepted_values": ["open", "private"],
                                "aliases": {"open": ["more open", "novo"]},
                            }
                        ],
                    }
                ],
            }
        }
    }

    state = DialogueState.load(metadata)

    assert state.expected_answer_frames[0].frame_id == "product_preference:test"
    assert state.expected_answer_frames[0].expected_slots[0].slot == "workspace_preference"
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
OPENROUTER_API_KEY=dummy uv run pytest tests/test_dialogue_state.py::test_dialogue_state_loads_expected_answer_frames -v --tb=short
```

Expected: fail because `expected_answer_frames` and related models are not defined.

- [ ] **Step 3: Implement minimal schema**

Add Pydantic models:

```python
class ExpectedSlot(BaseModel):
    slot: str
    required: bool = True
    accepted_values: list[str] = Field(default_factory=list)
    aliases: dict[str, list[str]] = Field(default_factory=dict)
    validator: str | None = None


class ExpectedAnswerFrame(BaseModel):
    frame_id: str
    flow: str
    question_kind: str
    prompt_key: str
    status: str = "active"
    priority: int = 50
    asked_at: str | datetime | None = None
    expires_at: str | datetime | None = None
    max_customer_turns: int | None = None
    turns_seen: int = 0
    expected_slots: list[ExpectedSlot] = Field(default_factory=list)
    source_refs: list[dict[str, Any]] = Field(default_factory=list)
    filled_slots: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
```

Add `expected_answer_frames: list[ExpectedAnswerFrame] = Field(default_factory=list)` to `DialogueState`.

- [ ] **Step 4: Add reducer tests and functions**

Add tests for `push_expected_answer_frame`, `mark_frame_fulfilled`, `expire_expected_answer_frames`, and bounded history.

Reducer behavior:

```python
def push_expected_answer_frame(state: DialogueState, frame: ExpectedAnswerFrame) -> DialogueState:
    frames = [existing for existing in state.expected_answer_frames if existing.frame_id != frame.frame_id]
    frames.append(frame)
    frames = sorted(frames, key=lambda item: item.priority, reverse=True)[:8]
    return state.model_copy(update={"active_flow": frame.flow, "expected_answer_frames": frames}, deep=True)
```

- [ ] **Step 5: Verify state tests**

Run:

```bash
OPENROUTER_API_KEY=dummy uv run pytest tests/test_dialogue_state.py -v --tb=short
```

Expected: pass.

## Task 2: Matcher And Interruption Policy

**Files:**
- Create: `src/dialogue/expected_answers.py`
- Test: `tests/test_dialogue_expected_answers.py`

- [ ] **Step 1: Write matcher tests**

Cover these cases:

- product preference frame + `I prefer more open for team` -> high-confidence slot `workspace_preference=open`;
- same frame + `Can delivery be arranged?` -> interruption, frame remains active;
- preference frame + refund/manager complaint -> blocker;
- two active frames + `the second one` -> ambiguous clarify;
- expired frame is ignored.

- [ ] **Step 2: Implement matcher result model**

Use a local model in `src/dialogue/expected_answers.py`:

```python
class ExpectedAnswerMatch(BaseModel):
    matched: bool = False
    frame_id: str | None = None
    confidence: str = "none"
    filled_slots: dict[str, Any] = Field(default_factory=dict)
    route: str = "legacy_fallback"
    interruption: bool = False
    ambiguous_frame_ids: list[str] = Field(default_factory=list)
    blocker: str | None = None
```

- [ ] **Step 3: Implement deterministic matching**

Implement exact/alias matching first. Do not call live LLMs. Hard blockers run before frame filling.

- [ ] **Step 4: Verify matcher tests**

Run:

```bash
OPENROUTER_API_KEY=dummy uv run pytest tests/test_dialogue_expected_answers.py -v --tb=short
```

Expected: pass.

## Task 3: Runner Frame Capture And Graph Steps

**Files:**
- Modify: `src/dialogue/runner.py`
- Test: `tests/test_dialogue_runner.py`

- [ ] **Step 1: Add RED runner tests**

Tests must prove:

- shadow mode writes expected-answer match traces with no side effects;
- enforce mode handles only allowlisted `product_preference_answer`;
- unallowlisted matches fall back to legacy;
- frame capture proposals are bounded.

- [ ] **Step 2: Add graph nodes**

Extend graph shape from one `decide` node to explicit pure steps:

```python
graph.add_node("expire_frames", _expire_frames_node)
graph.add_node("match_expected_answer", _match_expected_answer_node)
graph.add_node("decide", _decide_node)
graph.set_entry_point("expire_frames")
graph.add_edge("expire_frames", "match_expected_answer")
graph.add_edge("match_expected_answer", "decide")
graph.set_finish_point("decide")
```

- [ ] **Step 3: Verify runner tests**

Run:

```bash
OPENROUTER_API_KEY=dummy uv run pytest tests/test_dialogue_runner.py -v --tb=short
```

Expected: pass.

## Task 4: Engine Integration

**Files:**
- Modify: `src/llm/engine.py`
- Test: `tests/test_llm_engine.py`

- [ ] **Step 1: Add RED integration tests**

Add tests for:

- #47 immediate answer remains green;
- #47 delayed answer after delivery interruption routes to product handling;
- true blockers still escalate;
- old last-question heuristic remains fallback when no frame exists.

- [ ] **Step 2: Capture frames after assistant questions**

Persist frames when the engine returns customer-facing questions for:

- product preference;
- SKU/quantity clarification;
- quotation details;
- post-quotation approval;
- name gate.

- [ ] **Step 3: Use frame-aware routing before verified-policy handoff**

At the existing verified-policy branch, check `DialogueKernelResult` or active frame match first. Only bypass handoff when the match has no hard blocker and the route is allowlisted or delegated safely to legacy.

- [ ] **Step 4: Verify targeted engine tests**

Run:

```bash
OPENROUTER_API_KEY=dummy uv run pytest tests/test_llm_engine.py -v --tb=short -k "dialogue_kernel or product_preference or pending_quote or name_gate"
```

Expected: pass.

## Task 5: Replay Fixtures And Stress Suite

**Files:**
- Modify/Create: `tests/fixtures/dialogue/*.json`
- Modify: `tests/test_dialogue_replay_fixtures.py`
- Test: `tests/test_dialogue_replay_fixtures.py`

- [ ] **Step 1: Add fixtures**

Add machine-readable fixtures for #36, #37, #39, #40, #47 immediate, #47 delayed, #11 hold, ambiguity, expiry, blocker override, and long-dialog stress.

- [ ] **Step 2: Validate JSON**

Run:

```bash
python3 -m json.tool tests/fixtures/dialogue/dialogue_state_kernel_replay.json >/dev/null
```

Expected: no output and exit code 0.

- [ ] **Step 3: Verify replay tests**

Run:

```bash
OPENROUTER_API_KEY=dummy uv run pytest tests/test_dialogue_replay_fixtures.py -v --tb=short
```

Expected: pass.

## Task 6: Review, Full Gates, Shadow Delivery Decision

**Files:**
- Modify: `.codex/stages/tj-gh48/summary.md`
- Create/Modify: `.codex/stages/tj-gh48/artifacts/*.md`
- Modify: `.codex/handoff.md`

- [ ] **Step 1: Run targeted suite**

Run:

```bash
OPENROUTER_API_KEY=dummy uv run pytest tests/test_dialogue_state.py tests/test_dialogue_expected_answers.py tests/test_dialogue_runner.py tests/test_dialogue_replay_fixtures.py tests/test_llm_engine.py -v --tb=short
```

- [ ] **Step 2: Run full gates**

Run:

```bash
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy src/
env DYLD_FALLBACK_LIBRARY_PATH="${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}" OPENROUTER_API_KEY=dummy uv run pytest tests/ -v --tb=short
scripts/orchestration/run_process_verification.sh
scripts/orchestration/run_stage_closeout.py --stage tj-gh48
```

- [ ] **Step 3: Delivery policy**

Do not deploy or switch production enforce mode without explicit current-task approval. If deploy is approved, deploy with `dialogue_kernel_mode=shadow`, run production smoke, and run synthetic E2E against the approved test identity only.

## Self-Review

- Spec coverage: maps to Beads `tj-gh48.2` through `tj-gh48.7`.
- Placeholder scan: no `TBD`/`TODO` placeholders.
- Type consistency: `ExpectedAnswerFrame`, `ExpectedSlot`, and `ExpectedAnswerMatch` names are used consistently.
- Scope: focused on dialogue state/routing; does not remove legacy or close #11.
